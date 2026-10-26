//! L'île : son état, ses formats et le dialogue avec la page — le même
//! comportement que l'île GTK (`overlay.py`).
//!
//! Les messages d'Axon attendent dans une file tant que la page n'a pas dit
//! `pret`, puis partent par lots avec l'état ouvert/fermé. La fenêtre n'est
//! montrée qu'après : jamais de page vide à l'écran.

use std::sync::Mutex;

use serde_json::{json, Value};
use tauri::{AppHandle, LogicalPosition, LogicalSize, Manager, WebviewWindow};

use crate::canal::ClientOverlay;

pub const FENETRE: &str = "ile";

const LARGEUR: f64 = 780.0;
const LARGEUR_NOTIF: f64 = 620.0;
const HAUTEUR_NOTIF: (f64, f64) = (120.0, 340.0);
const PASTILLE: f64 = 44.0;
const MARGE_HAUT: f64 = 14.0;
const MARGE_HAUT_PASTILLE: f64 = 6.0;

/// Les messages de la page relayés tels quels au CLI.
const VERS_AXON: [&str; 16] = [
    "commande",
    "reponse_demande",
    "decision",
    "demander_commandes",
    "raccourci",
    "joindre",
    "detacher",
    "demander_picker",
    "creer_suivi",
    "creer_echeance",
    "maj_echeance",
    "archiver_suivi",
    "lier_ressource",
    "supprimer_suivi",
    "demander_flux",
    "planifier_rappels",
];

#[derive(Clone, Copy, PartialEq, Debug)]
enum Mode {
    Accueil,
    Detail,
    Notif,
    Bulle,
    Pastille,
}

impl Mode {
    /// La pastille et la bulle ne font qu'annoncer : elles ne prennent pas le
    /// clavier au terminal. Leurs boutons restent cliquables.
    fn sans_clavier(self) -> bool {
        matches!(self, Mode::Pastille | Mode::Bulle)
    }

    fn depuis(nom: &str) -> Mode {
        match nom {
            "accueil" => Mode::Accueil,
            "notif" => Mode::Notif,
            "bulle" => Mode::Bulle,
            "pastille" => Mode::Pastille,
            _ => Mode::Detail,
        }
    }
}

struct Etat {
    ouvert: bool,
    visible: bool,
    page_prete: bool,
    attente: Vec<Value>,
    mode: Mode,
    hauteur_notif: f64,
}

impl Default for Etat {
    fn default() -> Self {
        Etat {
            ouvert: false,
            visible: false,
            page_prete: false,
            attente: Vec::new(),
            mode: Mode::Accueil,
            hauteur_notif: 152.0,
        }
    }
}

#[derive(Default)]
pub struct Ile(Mutex<Etat>);

impl Ile {
    fn avec<R>(&self, f: impl FnOnce(&mut Etat) -> R) -> R {
        f(&mut self.0.lock().unwrap())
    }
}

fn taille(mode: Mode, hauteur_notif: f64) -> (f64, f64) {
    match mode {
        Mode::Accueil => (LARGEUR, 280.0),
        Mode::Detail => (LARGEUR, 500.0),
        Mode::Notif | Mode::Bulle => (LARGEUR_NOTIF, hauteur_notif),
        Mode::Pastille => (PASTILLE, PASTILLE),
    }
}

fn fenetre(app: &AppHandle) -> Option<WebviewWindow> {
    app.get_webview_window(FENETRE)
}

/// Un message venu d'Axon (canal `overlay` ou `controle`), ou de l'hôte.
pub fn depuis_axon(app: &AppHandle, message: Value) {
    let genre = message
        .get("type")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned();
    match genre.as_str() {
        "basculer" => return basculer(app),
        "selecteur_fichier" => {
            return ceder_au_selecteur(app, message.get("ouvert") == Some(&Value::Bool(true)));
        }
        "connexion" if message.get("connecte") == Some(&Value::Bool(false)) => {
            ceder_au_selecteur(app, false);
        }
        _ => {}
    }
    // Île fermée : un rappel s'ouvre en bulle (Axon vient le dire), une
    // demande en pastille que le survol déplie.
    let ouverture = match genre.as_str() {
        "rappel" => Some(Mode::Bulle),
        "demande" | "confirmation" => Some(Mode::Pastille),
        _ => None,
    };
    let a_ouvrir = app.state::<Ile>().avec(|etat| {
        etat.attente.push(message);
        let ouvre = ouverture.is_some() && !etat.ouvert;
        etat.ouvert |= ouvre;
        ouvre
    });
    if let (true, Some(mode)) = (a_ouvrir, ouverture) {
        definir_mode(app, mode, None);
    }
    synchroniser(app);
}

/// Un message de la page (`invoke("depuis_page")`).
pub fn depuis_page(app: &AppHandle, message: Value) {
    let genre = message
        .get("type")
        .and_then(Value::as_str)
        .unwrap_or_default();
    match genre {
        "pret" => {
            app.state::<Ile>().avec(|etat| etat.page_prete = true);
            synchroniser(app);
        }
        "ouvrir" => {
            let voulu = message.get("ouvert") == Some(&Value::Bool(true));
            if voulu != app.state::<Ile>().avec(|etat| etat.ouvert) {
                basculer(app);
            }
        }
        "mode" => {
            let mode = Mode::depuis(
                message
                    .get("mode")
                    .and_then(Value::as_str)
                    .unwrap_or("accueil"),
            );
            definir_mode(app, mode, message.get("hauteur").and_then(Value::as_f64));
        }
        g if VERS_AXON.contains(&g) && !app.state::<ClientOverlay>().envoyer(&message) => {
            depuis_axon(app, json!({ "type": "connexion", "connecte": false }));
            depuis_axon(
                app,
                json!({ "type": "etat", "etat": "erreur", "texte": "Axon n’est pas connecté" }),
            );
        }
        _ => {}
    }
}

pub fn basculer(app: &AppHandle) {
    app.state::<Ile>().avec(|etat| etat.ouvert = !etat.ouvert);
    synchroniser(app);
}

fn definir_mode(app: &AppHandle, mode: Mode, hauteur: Option<f64>) {
    let (change, dimensions) = app.state::<Ile>().avec(|etat| {
        if let (Mode::Notif | Mode::Bulle, Some(h)) = (mode, hauteur) {
            etat.hauteur_notif = h.clamp(HAUTEUR_NOTIF.0, HAUTEUR_NOTIF.1);
        }
        let avant = taille(etat.mode, etat.hauteur_notif);
        let change = etat.mode != mode || hauteur.is_some();
        etat.mode = mode;
        (
            change || avant != taille(mode, etat.hauteur_notif),
            taille(mode, etat.hauteur_notif),
        )
    });
    if change {
        if let Some(fenetre) = fenetre(app) {
            placer(&fenetre, mode, dimensions);
        }
    }
}

/// En haut au centre de l'écran, sous la barre des menus (macOS) — la zone de
/// travail exclut déjà la barre.
fn placer(fenetre: &WebviewWindow, mode: Mode, (largeur, hauteur): (f64, f64)) {
    // La pastille n'est qu'un signal : elle ne prend pas le clavier au terminal.
    let _ = fenetre.set_focusable(!mode.sans_clavier());
    let _ = fenetre.set_size(LogicalSize::new(largeur, hauteur));
    let Ok(Some(ecran)) = fenetre
        .current_monitor()
        .or_else(|_| fenetre.primary_monitor())
    else {
        return;
    };
    let echelle = ecran.scale_factor();
    let zone = ecran.work_area();
    let x = zone.position.x as f64 / echelle + (zone.size.width as f64 / echelle - largeur) / 2.0;
    let marge = if mode == Mode::Pastille {
        MARGE_HAUT_PASTILLE
    } else {
        MARGE_HAUT
    };
    let y = zone.position.y as f64 / echelle + marge;
    let _ = fenetre.set_position(LogicalPosition::new(x, y));
}

/// Envoie la file à la page avec l'état ouvert/fermé, puis montre ou cache.
fn synchroniser(app: &AppHandle) {
    let Some(fenetre) = fenetre(app) else { return };
    let Some((messages, ouvert, apparait, mode, dimensions)) = app.state::<Ile>().avec(|etat| {
        if !etat.page_prete {
            return None;
        }
        let apparait = etat.ouvert && !etat.visible;
        etat.visible = etat.ouvert;
        Some((
            std::mem::take(&mut etat.attente),
            etat.ouvert,
            apparait,
            etat.mode,
            taille(etat.mode, etat.hauteur_notif),
        ))
    }) else {
        return;
    };
    let script = format!(
        "(() => {{ if (!window.axon) return; {}.forEach(m => window.axon.recevoir(m)); window.axon.ouvrir({ouvert}); }})()",
        Value::Array(messages)
    );
    let _ = fenetre.eval(script);
    if !ouvert {
        let _ = fenetre.hide();
    } else if apparait {
        placer(&fenetre, mode, dimensions);
        let _ = fenetre.show();
        if !mode.sans_clavier() {
            let _ = fenetre.set_focus();
        }
        let _ = fenetre.eval("window.axon?.entree()");
    }
}

/// Le sélecteur de fichiers natif ouvert par le CLI doit passer devant l'île.
fn ceder_au_selecteur(app: &AppHandle, ouvert: bool) {
    if let Some(fenetre) = fenetre(app) {
        let _ = fenetre.set_always_on_top(!ouvert);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn chaque_mode_a_la_taille_de_l_ile_gtk() {
        assert_eq!(taille(Mode::Accueil, 0.0), (780.0, 280.0));
        assert_eq!(taille(Mode::Detail, 0.0), (780.0, 500.0));
        assert_eq!(taille(Mode::Notif, 200.0), (620.0, 200.0));
        assert_eq!(taille(Mode::Bulle, 180.0), (620.0, 180.0));
        assert_eq!(taille(Mode::Pastille, 0.0), (44.0, 44.0));
    }

    #[test]
    fn un_mode_inconnu_vaut_la_vue_detaillee() {
        assert_eq!(Mode::depuis("accueil"), Mode::Accueil);
        assert_eq!(Mode::depuis("pastille"), Mode::Pastille);
        assert_eq!(Mode::depuis("n'importe quoi"), Mode::Detail);
    }

    #[test]
    fn seules_la_pastille_et_la_bulle_ne_prennent_pas_le_clavier() {
        assert!(Mode::Pastille.sans_clavier() && Mode::Bulle.sans_clavier());
        assert!(!Mode::Notif.sans_clavier() && !Mode::Detail.sans_clavier());
    }
}
