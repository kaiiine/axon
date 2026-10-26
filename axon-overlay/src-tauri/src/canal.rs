//! Les deux canaux locaux de l'île, côté serveur — contrat identique à
//! `src/infra/canal_overlay.py` et à l'île GTK :
//!
//! - `overlay` : la session CLI, un seul client (une nouvelle connexion
//!   remplace la précédente) ;
//! - `controle` : messages ponctuels, seuls `rappel` et `basculer` acceptés.
//!
//! Une ligne JSON par message. Socket Unix `<dossier>/<nom>.sock` (0600) sous
//! Linux et macOS ; TCP 127.0.0.1 sous Windows, l'adresse et le jeton publiés
//! dans `<dossier>/<nom>.json`, le jeton exigé en première ligne.

use std::io::{self, BufRead, BufReader, Write};
use std::net::{Shutdown, TcpListener, TcpStream};
use std::path::PathBuf;
use std::sync::Mutex;
use std::thread;

use serde_json::{json, Value};
use tauri::{AppHandle, Manager};

#[cfg(unix)]
use std::os::unix::net::{UnixListener, UnixStream};

use crate::ile;

pub const OVERLAY: &str = "overlay";
pub const CONTROLE: &str = "controle";
const TYPES_CONTROLE: [&str; 2] = ["rappel", "basculer"];

/// Le dossier d'exécution partagé avec Axon.
pub fn dossier() -> PathBuf {
    if cfg!(windows) {
        let base = std::env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .unwrap_or_else(|| home().join("AppData").join("Local"));
        base.join("axon").join("run")
    } else if cfg!(target_os = "macos") {
        std::env::var_os("TMPDIR")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir)
            .join("axon")
    } else {
        std::env::var_os("XDG_RUNTIME_DIR")
            .map(PathBuf::from)
            .unwrap_or_else(std::env::temp_dir)
            .join("axon")
    }
}

fn home() -> PathBuf {
    std::env::var_os("USERPROFILE")
        .or_else(|| std::env::var_os("HOME"))
        .map(PathBuf::from)
        .unwrap_or_default()
}

/// Une connexion acceptée, quel que soit le transport.
enum Liaison {
    #[cfg(unix)]
    Unix(UnixStream),
    Tcp(TcpStream),
}

impl Liaison {
    fn try_clone(&self) -> io::Result<Liaison> {
        Ok(match self {
            #[cfg(unix)]
            Liaison::Unix(s) => Liaison::Unix(s.try_clone()?),
            Liaison::Tcp(s) => Liaison::Tcp(s.try_clone()?),
        })
    }

    fn ecrire(&mut self, octets: &[u8]) -> io::Result<()> {
        match self {
            #[cfg(unix)]
            Liaison::Unix(s) => s.write_all(octets),
            Liaison::Tcp(s) => s.write_all(octets),
        }
    }

    fn fermer(&self) {
        let _ = match self {
            #[cfg(unix)]
            Liaison::Unix(s) => s.shutdown(Shutdown::Both),
            Liaison::Tcp(s) => s.shutdown(Shutdown::Both),
        };
    }

    fn lignes(self) -> Box<dyn Iterator<Item = io::Result<String>> + Send> {
        match self {
            #[cfg(unix)]
            Liaison::Unix(s) => Box::new(BufReader::new(s).lines()),
            Liaison::Tcp(s) => Box::new(BufReader::new(s).lines()),
        }
    }
}

/// Un serveur à l'écoute, et le jeton qu'il exige (TCP seulement).
enum Ecoute {
    #[cfg(unix)]
    Unix(UnixListener),
    Tcp(TcpListener, String),
}

impl Ecoute {
    fn accepter(&self) -> io::Result<(Liaison, Option<String>)> {
        Ok(match self {
            #[cfg(unix)]
            Ecoute::Unix(l) => (Liaison::Unix(l.accept()?.0), None),
            Ecoute::Tcp(l, jeton) => (Liaison::Tcp(l.accept()?.0), Some(jeton.clone())),
        })
    }
}

fn ecouter(nom: &str) -> io::Result<Ecoute> {
    let dossier = dossier();
    std::fs::create_dir_all(&dossier)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&dossier, std::fs::Permissions::from_mode(0o700))?;
        let chemin = dossier.join(format!("{nom}.sock"));
        let _ = std::fs::remove_file(&chemin);
        let ecoute = UnixListener::bind(&chemin)?;
        std::fs::set_permissions(&chemin, std::fs::Permissions::from_mode(0o600))?;
        Ok(Ecoute::Unix(ecoute))
    }
    #[cfg(not(unix))]
    ecouter_tcp(nom, &dossier)
}

#[cfg_attr(unix, allow(dead_code))]
fn ecouter_tcp(nom: &str, dossier: &std::path::Path) -> io::Result<Ecoute> {
    let ecoute = TcpListener::bind(("127.0.0.1", 0))?;
    let jeton = nouveau_jeton()?;
    let adresse = json!({ "port": ecoute.local_addr()?.port(), "jeton": jeton });
    std::fs::write(dossier.join(format!("{nom}.json")), adresse.to_string())?;
    Ok(Ecoute::Tcp(ecoute, jeton))
}

fn nouveau_jeton() -> io::Result<String> {
    let mut octets = [0u8; 32];
    getrandom::fill(&mut octets).map_err(|e| io::Error::other(e.to_string()))?;
    Ok(octets.iter().map(|o| format!("{o:02x}")).collect())
}

/// Vrai si la première ligne présente le jeton attendu (ou si aucun n'est exigé).
fn authentifier(lignes: &mut dyn Iterator<Item = io::Result<String>>, jeton: Option<&str>) -> bool {
    let Some(attendu) = jeton else { return true };
    let Some(Ok(ligne)) = lignes.next() else {
        return false;
    };
    serde_json::from_str::<Value>(&ligne)
        .ok()
        .and_then(|v| v.get("jeton").and_then(Value::as_str).map(|j| j == attendu))
        .unwrap_or(false)
}

/// Le client CLI du canal `overlay`, pour écrire vers lui.
#[derive(Default)]
pub struct ClientOverlay {
    liaison: Mutex<Option<(u64, Liaison)>>,
}

impl ClientOverlay {
    /// Envoie un message au CLI. Faux s'il n'est pas connecté.
    pub fn envoyer(&self, message: &Value) -> bool {
        let mut garde = self.liaison.lock().unwrap();
        let Some((_, liaison)) = garde.as_mut() else {
            return false;
        };
        let mut ligne = message.to_string();
        ligne.push('\n');
        liaison.ecrire(ligne.as_bytes()).is_ok()
    }

    fn remplacer(&self, numero: u64, liaison: Liaison) {
        if let Some((_, ancienne)) = self.liaison.lock().unwrap().replace((numero, liaison)) {
            ancienne.fermer();
        }
    }

    /// Oublie la liaison `numero` si c'est encore la courante.
    fn perdre(&self, numero: u64) -> bool {
        let mut garde = self.liaison.lock().unwrap();
        if garde.as_ref().is_some_and(|(n, _)| *n == numero) {
            *garde = None;
            return true;
        }
        false
    }
}

/// Lance les deux serveurs. L'app doit gérer un `ClientOverlay`.
pub fn demarrer(app: &AppHandle) -> io::Result<()> {
    let overlay = ecouter(OVERLAY)?;
    let controle = ecouter(CONTROLE)?;

    let handle = app.clone();
    thread::spawn(move || {
        let mut numero = 0u64;
        while let Ok((liaison, jeton)) = overlay.accepter() {
            numero += 1;
            let (handle, n) = (handle.clone(), numero);
            thread::spawn(move || servir_overlay(&handle, n, liaison, jeton));
        }
    });

    let handle = app.clone();
    thread::spawn(move || {
        while let Ok((liaison, jeton)) = controle.accepter() {
            let handle = handle.clone();
            thread::spawn(move || servir_controle(&handle, liaison, jeton));
        }
    });
    Ok(())
}

fn servir_overlay(app: &AppHandle, numero: u64, liaison: Liaison, jeton: Option<String>) {
    let Ok(ecriture) = liaison.try_clone() else {
        return;
    };
    let mut lignes = liaison.lignes();
    if !authentifier(&mut lignes, jeton.as_deref()) {
        ecriture.fermer();
        return;
    }
    let client = app.state::<ClientOverlay>();
    client.remplacer(numero, ecriture);
    ile::depuis_axon(app, json!({ "type": "connexion", "connecte": true }));
    for ligne in lignes.map_while(Result::ok) {
        if let Ok(message) = serde_json::from_str::<Value>(&ligne) {
            ile::depuis_axon(app, message);
        }
    }
    if client.perdre(numero) {
        ile::depuis_axon(app, json!({ "type": "connexion", "connecte": false }));
    }
}

fn servir_controle(app: &AppHandle, liaison: Liaison, jeton: Option<String>) {
    let mut lignes = liaison.lignes();
    if !authentifier(&mut lignes, jeton.as_deref()) {
        return;
    }
    for ligne in lignes.map_while(Result::ok) {
        let Ok(message) = serde_json::from_str::<Value>(&ligne) else {
            continue;
        };
        let genre = message
            .get("type")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if TYPES_CONTROLE.contains(&genre) {
            ile::depuis_axon(app, message);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lignes(texte: &str) -> Box<dyn Iterator<Item = io::Result<String>>> {
        Box::new(
            texte
                .lines()
                .map(|l| Ok(l.to_owned()))
                .collect::<Vec<_>>()
                .into_iter(),
        )
    }

    #[test]
    fn sans_jeton_exige_tout_client_passe() {
        assert!(authentifier(&mut *lignes(""), None));
    }

    #[test]
    fn le_bon_jeton_ouvre_le_canal() {
        assert!(authentifier(
            &mut *lignes("{\"jeton\":\"abc\"}\n{\"type\":\"basculer\"}"),
            Some("abc")
        ));
    }

    #[test]
    fn un_mauvais_jeton_ou_un_message_direct_est_refuse() {
        assert!(!authentifier(
            &mut *lignes("{\"jeton\":\"faux\"}"),
            Some("abc")
        ));
        assert!(!authentifier(
            &mut *lignes("{\"type\":\"basculer\"}"),
            Some("abc")
        ));
        assert!(!authentifier(&mut *lignes(""), Some("abc")));
    }

    #[test]
    fn un_jeton_fait_64_caracteres_hexadecimaux() {
        let jeton = nouveau_jeton().unwrap();
        assert_eq!(jeton.len(), 64);
        assert!(jeton.chars().all(|c| c.is_ascii_hexdigit()));
        assert_ne!(jeton, nouveau_jeton().unwrap());
    }

    #[test]
    fn l_adresse_tcp_publiee_permet_de_se_connecter() {
        let dossier = std::env::temp_dir().join(format!("axon-test-{}", std::process::id()));
        std::fs::create_dir_all(&dossier).unwrap();
        let Ecoute::Tcp(ecoute, jeton) = ecouter_tcp("controle", &dossier).unwrap() else {
            unreachable!()
        };
        let adresse: Value =
            serde_json::from_str(&std::fs::read_to_string(dossier.join("controle.json")).unwrap())
                .unwrap();
        assert_eq!(adresse["jeton"], jeton);
        let port = adresse["port"].as_u64().unwrap() as u16;
        assert!(TcpStream::connect(("127.0.0.1", port)).is_ok());
        drop(ecoute);
        std::fs::remove_dir_all(dossier).unwrap();
    }
}
