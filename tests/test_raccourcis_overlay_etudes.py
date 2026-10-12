"""src/ui/raccourcis_overlay.py — statut de génération exposé aux panneaux
Études de l'île (§1, lot 3) : `_etudes_suivis` (par suivi) et
`_etudes_fiches_recentes` (travail rapide, `suivi_id=None`).

Isolation identique à tests/test_study_store.py : `AXON_STATE_DIR` redirigé
vers un `tmp_path`, modules rechargés après la surcharge (store.py lit
`_chemins.etudes()` une fois à l'import).
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def etudes(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.ui.raccourcis_overlay as raccourcis

    for module in (chemins, store, raccourcis):
        importlib.reload(module)
    return raccourcis, store


def test_un_suivi_sans_generation_na_aucun_champ_generation(etudes):
    """Jamais lancée = aucune clé (pas `None` partout) — le frontend
    distingue ainsi "jamais lancé" d'un statut qu'il ne reconnaîtrait pas."""
    raccourcis, store = etudes
    store.creer_suivi("ML", "matiere")

    resultat = raccourcis.executer("etudes_suivis")

    row = resultat["rows"][0]
    assert "generationFicheStatut" not in row
    assert "generationFicheFichier" not in row


def test_une_generation_en_cours_apparait_sur_la_ligne_du_suivi(etudes):
    raccourcis, store = etudes
    suivi = store.creer_suivi("ML", "matiere")
    store.demarrer_generation(suivi["id"], "fiche")

    resultat = raccourcis.executer("etudes_suivis")

    row = next(r for r in resultat["rows"] if r["id"] == suivi["id"])
    assert row["generationFicheStatut"] == "en_cours"
    assert "generationFicheFichier" not in row


def test_une_generation_terminee_porte_le_nom_du_fichier(etudes):
    raccourcis, store = etudes
    suivi = store.creer_suivi("ML", "matiere")
    generation = store.demarrer_generation(suivi["id"], "exo")
    resultat_cree = store.ajouter_resultat("exo", "exo_ml.html", suivi_id=suivi["id"])
    store.terminer_generation(generation["id"], resultat_cree["id"])

    resultat = raccourcis.executer("etudes_suivis")

    row = next(r for r in resultat["rows"] if r["id"] == suivi["id"])
    assert row["generationExoStatut"] == "terminee"
    assert row["generationExoFichier"] == "exo_ml.html"


def test_une_generation_echouee_napporte_aucun_fichier(etudes):
    raccourcis, store = etudes
    suivi = store.creer_suivi("ML", "matiere")
    generation = store.demarrer_generation(suivi["id"], "fiche")
    store.echouer_generation(generation["id"], "panne LLM")

    resultat = raccourcis.executer("etudes_suivis")

    row = next(r for r in resultat["rows"] if r["id"] == suivi["id"])
    assert row["generationFicheStatut"] == "echouee"
    assert "generationFicheFichier" not in row


def test_deux_suivis_ne_melangent_pas_leurs_statuts(etudes):
    """Le verrou/statut est bien PAR suivi — une génération sur l'un ne doit
    jamais apparaître sur la ligne d'un autre."""
    raccourcis, store = etudes
    a = store.creer_suivi("A", "matiere")
    b = store.creer_suivi("B", "matiere")
    store.demarrer_generation(a["id"], "fiche")

    resultat = raccourcis.executer("etudes_suivis")

    ligne_a = next(r for r in resultat["rows"] if r["id"] == a["id"])
    ligne_b = next(r for r in resultat["rows"] if r["id"] == b["id"])
    assert ligne_a["generationFicheStatut"] == "en_cours"
    assert "generationFicheStatut" not in ligne_b


def test_le_travail_rapide_sans_suivi_apparait_sur_le_panneau_recents(etudes):
    """`suivi_id=None` (§3, travail rapide) : le statut vit sur le panneau
    `etudes_fiches_recentes`, pas sur une ligne de suivi puisqu'il n'y en a
    pas pour un travail rapide."""
    raccourcis, store = etudes
    store.demarrer_generation(None, "fiche")

    resultat = raccourcis.executer("etudes_fiches_recentes")

    assert resultat["generationFicheStatut"] == "en_cours"


def test_le_detail_d_un_suivi_se_deplie_depuis_l_ile(etudes):
    """Le dépliage d'une ligne de suivi passe par le tool `etude_detail_suivi`
    — un import resté sur l'ancien `tools.py` l'avait cassé sans bruit."""
    raccourcis, store = etudes
    suivi = store.creer_suivi("ML", "matiere")
    store.ajouter_echeance(suivi["id"], "Partiel", "partiel", "2099-11-25")

    resultat = raccourcis.executer("etudes_detail_suivi", suivi["id"])

    assert "ML" in resultat["text"] and "Partiel" in resultat["text"]


def test_les_lignes_affichent_des_libelles_lisibles_pas_les_cles_internes(etudes):
    raccourcis, store = etudes
    suivi = store.creer_suivi("Compilateur", "projet")
    store.ajouter_echeance(suivi["id"], "Rendu final", "rendu_projet", "2099-11-25")

    ligne_suivi = raccourcis.executer("etudes_suivis")["rows"][0]
    ligne_echeance = raccourcis.executer("etudes_echeances")["rows"][0]

    assert ligne_suivi["tag"] == "Projet"
    assert ligne_suivi["meta"] == "Rendu final le 25 nov."
    assert ligne_echeance["tag"] == "Rendu"
    assert ligne_echeance["meta"].startswith("Compilateur · 25 nov., dans ")


def test_une_echeance_annulee_disparait_des_prochaines(etudes):
    """Annuler depuis l'île doit retirer l'échéance de la liste, pas la
    laisser affichée parmi les prochaines."""
    raccourcis, store = etudes
    suivi = store.creer_suivi("ML", "matiere")
    gardee = store.ajouter_echeance(suivi["id"], "Partiel", "partiel", "2099-11-25")
    annulee = store.ajouter_echeance(suivi["id"], "TP noté", "devoir", "2099-11-20")
    store.maj_echeance(suivi["id"], annulee["id"], statut="annulee")

    ids = [r["id"] for r in raccourcis.executer("etudes_echeances")["rows"]]

    assert ids == [gardee["id"]]


def test_la_page_projet_rassemble_tout_et_alimente_le_calendrier(etudes):
    raccourcis, store = etudes
    suivi = store.creer_suivi("Compilateur", "projet")
    echeance = store.ajouter_echeance(suivi["id"], "Rendu final", "rendu_projet", "2099-12-10")
    store.ajouter_rappel_echeance(suivi["id"], echeance["id"], "cron_x", "2099-12-03T09:00:00+01:00", 7)
    store.ajouter_tache(suivi["id"], "Parser")
    store.ajouter_resultat("fiche", "fiche_compil.html", suivi_id=suivi["id"])

    page = raccourcis.executer("etudes_page_suivi", suivi["id"])["page"]

    assert (page["titre"], page["type"]) == ("Compilateur", "Projet")
    assert page["echeances"][0]["dateCourte"] == "10 déc." and page["echeances"][0]["rappels"] == 1
    assert page["taches"][0]["titre"] == "Parser"
    assert page["resultats"][0]["fichier"] == "fiche_compil.html"
    genres = {ev["genre"] for ev in page["calendrier"]}
    assert {"echeance", "rappel", "resultat"} <= genres


def test_la_page_d_un_suivi_inconnu_leve(etudes):
    raccourcis, _store = etudes
    with pytest.raises(ValueError):
        raccourcis.executer("etudes_page_suivi", "suivi_inexistant")
