"""src/agents/study/rappels.py — notifications d'études hors conversation :
rappel manqué avec son vrai contenu, et récapitulatif du jour (échéances
proches + état des dépôts Git liés). Store isolé, vrai dépôt Git temporaire.
"""
from __future__ import annotations

import importlib
import subprocess
from datetime import date, timedelta

import pytest


@pytest.fixture
def etudes(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path / "etat"))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.agents.study.rappels as rappels
    for module in (chemins, store, rappels):
        importlib.reload(module)
    return store, rappels


def _dans(jours: int) -> str:
    return (date.today() + timedelta(days=jours)).isoformat()


def _depot(chemin):
    chemin.mkdir(parents=True)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(chemin)]
    subprocess.run(git + ["init", "-q", "-b", "main"], check=True)
    (chemin / "a.txt").write_text("x")
    subprocess.run(git + ["add", "a.txt"], check=True)
    subprocess.run(git + ["commit", "-q", "-m", "init"], check=True)
    (chemin / "b.txt").write_text("non commité")
    return chemin


def test_le_recap_liste_les_echeances_proches_et_l_etat_des_depots(etudes, tmp_path):
    store, rappels = etudes
    suivi = store.creer_suivi("Projet Compilateur", "projet")
    store.ajouter_echeance(suivi["id"], "Rendu final", "rendu_projet", _dans(3))
    store.ajouter_echeance(suivi["id"], "Soutenance", "autre", _dans(40))      # trop loin
    annulee = store.ajouter_echeance(suivi["id"], "TP noté", "devoir", _dans(2))
    store.maj_echeance(suivi["id"], annulee["id"], statut="annulee")
    depot = _depot(tmp_path / "back")
    ressource = store.ajouter_ressource("depot_git", "back", "chemin_externe", str(depot))
    store.associer_ressource(suivi["id"], ressource["id"])

    titre, corps = rappels.recap_du_jour()

    assert titre == "Axon · Études"
    lignes = corps.splitlines()
    assert lignes[0] == "• Rendu final (Projet Compilateur) — dans 3 jours"
    assert lignes[1].startswith("• back : main, dernier commit il y a ")
    assert lignes[1].endswith(", 1 fichier(s) non commité(s)")
    assert len(lignes) == 2      # ni l'échéance lointaine, ni l'annulée


def test_rien_a_dire_pas_de_recap(etudes):
    store, rappels = etudes
    store.creer_suivi("Vide", "autre")

    assert rappels.recap_du_jour() is None


def test_un_rappel_manque_garde_son_contenu_tant_que_l_echeance_est_a_venir(etudes):
    store, rappels = etudes
    suivi = store.creer_suivi("ML", "matiere")
    echeance = store.ajouter_echeance(suivi["id"], "Partiel", "partiel", _dans(3))
    store.ajouter_rappel_echeance(suivi["id"], echeance["id"], "cron_j7", "x", 7)

    trouve = rappels.echeance_du_rappel("cron_j7")
    titre, corps = rappels.texte_rappel_manque(*trouve)

    assert titre == "Axon · Partiel"
    assert corps.startswith("ML — dans 3 jours")


def test_un_rappel_d_une_echeance_passee_ou_annulee_ne_dit_plus_rien(etudes):
    store, rappels = etudes
    suivi = store.creer_suivi("ML", "matiere")
    passee = store.ajouter_echeance(suivi["id"], "Ancien", "partiel", _dans(-1))
    annulee = store.ajouter_echeance(suivi["id"], "Annulé", "partiel", _dans(5))
    store.maj_echeance(suivi["id"], annulee["id"], statut="annulee")
    store.ajouter_rappel_echeance(suivi["id"], passee["id"], "cron_passe", "x", 1)
    store.ajouter_rappel_echeance(suivi["id"], annulee["id"], "cron_annule", "x", 1)

    assert rappels.echeance_du_rappel("cron_passe") is None
    assert rappels.echeance_du_rappel("cron_annule") is None
    assert rappels.echeance_du_rappel("cron_inconnu") is None


def test_le_recap_signale_une_echeance_en_retard_jamais_rendue(etudes):
    """Une échéance passée encore « à venir » sortait du récap en silence : PC
    éteint le jour J, plus jamais rien ne la mentionnait."""
    store, rappels = etudes
    suivi = store.creer_suivi("Conseil des Sages", "projet")
    store.ajouter_echeance(suivi["id"], "Suivi de projet", "rendu_projet", _dans(-5))
    faite = store.ajouter_echeance(suivi["id"], "Ancien rendu", "rendu_projet", _dans(-3))
    store.maj_echeance(suivi["id"], faite["id"], statut="passee")
    store.ajouter_echeance(suivi["id"], "Préhistoire", "rendu_projet", _dans(-90))

    titre, corps = rappels.recap_du_jour()
    assert corps == "• Suivi de projet (Conseil des Sages) — en retard de 5 j"


def test_le_demon_donne_son_genre_a_chaque_tache(etudes, monkeypatch):
    store, rappels = etudes
    import src.cron_daemon as cron_daemon
    suivi = store.creer_suivi("CDS", "projet")
    echeance = store.ajouter_echeance(suivi["id"], "Rendu", "rendu_projet", _dans(3))
    store.ajouter_rappel_echeance(suivi["id"], echeance["id"], "cron_rendu", "x", 3)
    assert cron_daemon._contexte_de_tache("cron_rendu") == {
        "genre": "echeance", "suivi_id": suivi["id"], "echeance_id": echeance["id"]}
    assert cron_daemon._contexte_de_tache("cron_meteo") == {"genre": "tache"}
