"""src/plugins — la marketplace : catalogue, installation, registre, `/plugin`."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from src.plugins import catalogue, commandes, installateur, registre
from src.plugins.catalogue import Source
from src.plugins.manifeste import ErreurPlugin, Manifeste

TOUTES = ("linux-wayland", "linux", "macos", "windows")


@pytest.fixture(autouse=True)
def etat(tmp_path, monkeypatch):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path / "etat"))
    monkeypatch.setattr(catalogue, "CATALOGUE_AXON", tmp_path / "aucun-catalogue.json")
    return tmp_path


def _plugin(dossier, ident="demo", version="1.0.0", etapes=None, capacites=("ile",), plateformes=TOUTES):
    dossier.mkdir(parents=True, exist_ok=True)
    etapes = etapes if etapes is not None else [[sys.executable, "-c", "open('construit', 'w').write('ok')"]]
    (dossier / "plugin.json").write_text(json.dumps({
        "id": ident, "name": ident.title(), "version": version, "description": "un plugin de test",
        "capacites": list(capacites),
        "platforms": {p: {"toggle": "basculer.sh", "installation": etapes} for p in plateformes},
    }), encoding="utf-8")
    (dossier / "basculer.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    return dossier


def _oui(_manifeste, _plateforme):
    return True


def _non(_manifeste, _plateforme):
    return False


# ── le contrat ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brut, message", [
    ({"id": "Pas Bon", "version": "1", "platforms": {"linux": {}}}, "identifiant invalide"),
    ({"id": "ok", "platforms": {"linux": {}}}, "version manquante"),
    ({"id": "ok", "version": "1", "capacites": ["teleportation"], "platforms": {"linux": {}}}, "capacités inconnues"),
    ({"id": "ok", "version": "1", "platforms": {}}, "aucune plateforme"),
    ({"id": "ok", "version": "1", "platforms": {"linux": {"installation": ["npm ci && rm -rf ~"]}}},
     "listes d'arguments"),
])
def test_un_manifeste_invalide_est_refuse_avant_tout(brut, message):
    with pytest.raises(ErreurPlugin, match=message):
        Manifeste.depuis(brut)


def test_le_manifeste_de_l_overlay_respecte_le_contrat():
    """L'île vit dans son propre dépôt (github.com/kaiiine/axon-overlay) : ce
    contrat ne se vérifie que si une copie est présente à côté d'Axon."""
    from pathlib import Path
    import pytest
    dossier = Path(__file__).resolve().parents[1] / "axon-overlay"
    if not (dossier / "plugin.json").is_file():
        pytest.skip("axon-overlay n'est plus dans ce dépôt")
    manifeste = Manifeste.lire(dossier)
    assert manifeste.capacites == {"ile", "notifications"}
    assert manifeste.pour("linux-wayland").installation == (("npm", "ci"), ("npm", "run", "build"))


# ── l'installation ───────────────────────────────────────────────────────────

def test_installer_depuis_un_dossier_lance_les_etapes_et_enregistre(tmp_path):
    source = _plugin(tmp_path / "source")
    (source / "node_modules").mkdir()
    installe = installateur.installer(Source(local=str(source)), confirmer=_oui)

    dossier = registre.dossier_plugin("demo")
    assert (dossier / "construit").read_text() == "ok"
    assert not (dossier / "node_modules").exists()
    assert installe.version == "1.0.0"
    assert registre.avec_capacite("ile") == ["demo"]
    assert not (registre.dossier() / ".travail").exists() or not any((registre.dossier() / ".travail").iterdir())


def test_refuser_les_etapes_n_installe_rien(tmp_path):
    with pytest.raises(installateur.InstallationAnnulee):
        installateur.installer(Source(local=str(_plugin(tmp_path / "source"))), confirmer=_non)
    assert registre.installes() == {}
    assert not registre.dossier_plugin("demo").exists()


def test_une_etape_qui_echoue_garde_la_version_installee(tmp_path):
    installateur.installer(Source(local=str(_plugin(tmp_path / "v1"))), confirmer=_oui)
    casse = _plugin(tmp_path / "v2", version="2.0.0", etapes=[[sys.executable, "-c", "raise SystemExit(3)"]])
    with pytest.raises(ErreurPlugin, match="échec"):
        installateur.installer(Source(local=str(casse)), confirmer=_oui)
    assert registre.installes()["demo"].version == "1.0.0"
    assert (registre.dossier_plugin("demo") / "construit").exists()


def test_une_mise_a_jour_remplace_l_ancienne_version(tmp_path):
    source = _plugin(tmp_path / "source")
    installateur.installer(Source(local=str(source)), confirmer=_oui)
    _plugin(source, version="1.1.0")
    assert installateur.mettre_a_jour("demo", confirmer=_oui).version == "1.1.0"


def test_un_plugin_qui_ignore_la_plateforme_est_refuse(tmp_path):
    source = _plugin(tmp_path / "source", plateformes=("plan9",))
    with pytest.raises(ErreurPlugin, match="ne prend pas en charge"):
        installateur.installer(Source(local=str(source)), confirmer=_oui)


def test_le_catalogue_ne_peut_pas_installer_un_autre_plugin_que_celui_annonce(tmp_path):
    with pytest.raises(ErreurPlugin, match="pas « autre »"):
        installateur.installer(Source(local=str(_plugin(tmp_path / "source"))), confirmer=_oui,
                               id_attendu="autre")


def test_installer_depuis_un_depot_git_et_son_sous_dossier(tmp_path):
    depot = tmp_path / "depot"
    _plugin(depot / "plugins" / "demo")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(depot)]
    subprocess.run(git + ["init", "-q", "-b", "stable"], check=True)
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "plugin"], check=True)

    installe = installateur.installer(
        Source(git=depot.as_uri(), ref="stable", dossier="plugins/demo"), confirmer=_oui)

    assert len(installe.commit) == 40
    assert installe.source == {"git": depot.as_uri(), "ref": "stable", "dossier": "plugins/demo"}
    assert (registre.dossier_plugin("demo") / "construit").exists()
    assert not (registre.dossier_plugin("demo") / ".git").exists()


def test_un_sous_dossier_qui_sort_du_depot_est_refuse():
    with pytest.raises(ErreurPlugin, match="sous-dossier invalide"):
        Source(git="https://exemple.fr/depot.git", dossier="../../etc")


def test_desinstaller_retire_le_dossier_et_la_capacite(tmp_path):
    installateur.installer(Source(local=str(_plugin(tmp_path / "source"))), confirmer=_oui)
    installateur.desinstaller("demo")
    assert registre.avec_capacite("ile") == []
    assert not registre.dossier_plugin("demo").exists()


# ── la commande /plugin ──────────────────────────────────────────────────────

def _catalogue_utilisateur(source):
    fichier = registre.dossier() / "catalogue.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps({"plugins": [{
        "id": "demo", "nom": "Démo", "description": "pour les tests",
        "source": {"local": str(source)}}]}), encoding="utf-8")


def test_la_marketplace_installe_le_plugin_choisi_apres_confirmation(tmp_path):
    _catalogue_utilisateur(_plugin(tmp_path / "source"))
    reponses = iter(["Démo — disponible · pour les tests", "Installer", "Lancer ces étapes"])
    vus = []
    texte = commandes.handle_plugin([], choisir=lambda options, titre: next(reponses), annoncer=vus.append)
    assert texte.startswith("✓ demo 1.0.0 installé")
    assert "ouvrir / masquer" in texte
    assert any("construit" in v for v in vus)        # l'étape a été montrée avant de tourner
    assert "installé 1.0.0" in commandes.handle_plugin(["list"], choisir=lambda *_: None)


def test_annuler_dans_la_marketplace_n_installe_rien(tmp_path):
    _catalogue_utilisateur(_plugin(tmp_path / "source"))
    reponses = iter(["Démo — disponible · pour les tests", "Installer", "Annuler"])
    texte = commandes.handle_plugin([], choisir=lambda options, titre: next(reponses))
    assert texte.startswith("✗") and registre.installes() == {}


def test_install_accepte_un_dossier_et_remove_desinstalle(tmp_path):
    source = _plugin(tmp_path / "source")
    choisir = lambda options, titre: "Lancer ces étapes"
    assert commandes.handle_plugin(["install", str(source)], choisir=choisir).startswith("✓")
    assert commandes.handle_plugin(["remove", "demo"], choisir=choisir) == "demo désinstallé."


def test_une_cible_inconnue_le_dit():
    texte = commandes.handle_plugin(["install", "nimporte-quoi"], choisir=lambda *_: None)
    assert texte.startswith("✗") and "ni dans le catalogue" in texte


# ── le cœur suit les capacités ───────────────────────────────────────────────

def test_sans_plugin_de_notifications_un_rappel_reste_une_notification_systeme(monkeypatch):
    from src.infra import notifications
    envois, systeme = [], []
    monkeypatch.setattr(notifications.canal_overlay, "envoyer_une_fois", lambda *a, **k: envois.append(a) or True)
    monkeypatch.setattr(notifications, "notifier_systeme", lambda *a: systeme.append(a))
    notifications.notifier("Axon", "Rendu demain")
    assert envois == [] and systeme == [("Axon", "Rendu demain")]


def test_avec_un_plugin_de_notifications_le_rappel_part_dans_l_ile(tmp_path, monkeypatch):
    from src.infra import notifications
    installateur.installer(Source(local=str(_plugin(tmp_path / "source", capacites=("notifications",)))),
                           confirmer=_oui)
    envois = []
    monkeypatch.setattr(notifications.canal_overlay, "envoyer_une_fois", lambda *a, **k: envois.append(a) or True)
    notifications.notifier("Axon", "Rendu demain")
    assert envois and envois[0][1]["type"] == "rappel"


def test_le_contexte_d_un_rappel_arrive_jusqu_a_l_ile(tmp_path, monkeypatch):
    from src.infra import notifications
    installateur.installer(Source(local=str(_plugin(tmp_path / "source", capacites=("notifications",)))),
                           confirmer=_oui)
    envois = []
    monkeypatch.setattr(notifications.canal_overlay, "envoyer_une_fois", lambda *a, **k: envois.append(a) or True)
    notifications.notifier("Axon · Rendu", "Dans 3 jours",
                           {"genre": "echeance", "suivi_id": "s1", "echeance_id": "e1", "type": "piege"})
    message = envois[0][1]
    assert message["type"] == "rappel"                      # le contexte n'écrase pas le type
    assert (message["genre"], message["suivi_id"], message["echeance_id"]) == ("echeance", "s1", "e1")
