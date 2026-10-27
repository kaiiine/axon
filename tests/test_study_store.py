"""Persistance des suivis/ressources/échéances — src/agents/study/store.py.

Même esprit que tests/test_chemins_etat.py : jamais le vrai `~/.axon`, toujours
`AXON_STATE_DIR` redirigé vers un `tmp_path`. `store.py` lit `_chemins.etudes()`
une fois à l'IMPORT (constante de module `FICHIER`) : la surcharge doit donc
être posée avant l'import — d'où le rechargement du module dans chaque test.
"""
from __future__ import annotations

import importlib
import json

import pytest


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path))
    import src.infra.chemins as chemins
    import src.agents.study.store as module

    importlib.reload(chemins)
    importlib.reload(module)
    return module


# ── suivis ───────────────────────────────────────────────────────────────

def test_un_suivi_frais_na_ni_echeance_ni_ressource(store):
    s = store.creer_suivi("Deux PDF de cours", "ponctuel")

    assert s["id"].startswith("suivi_")
    assert s["echeances"] == [] and s["ressources"] == [] and s["exercices"] == []


def test_un_suivi_ponctuel_ne_force_aucune_date(store):
    """§1 : travailler sur deux PDF ne doit jamais créer artificiellement un
    contrôle — un suivi sans la moindre échéance doit rester utilisable."""
    s = store.creer_suivi("Travail ponctuel", "ponctuel")

    assert s["echeances"] == []
    assert store.obtenir_suivi(s["id"]) is not None


def test_lister_suivis_separe_actifs_et_archives(store):
    s1 = store.creer_suivi("Actif", "matiere")
    s2 = store.creer_suivi("À archiver", "matiere")
    store.archiver_suivi(s2["id"], True)

    assert [s["id"] for s in store.lister_suivis(archives=False)] == [s1["id"]]
    assert [s["id"] for s in store.lister_suivis(archives=True)] == [s2["id"]]


def test_rien_nest_ecrit_sur_le_disque_avant_le_premier_suivi(store, tmp_path):
    assert not (tmp_path / "etudes.json").exists()


def test_obtenir_suivi_inconnu_renvoie_none(store):
    assert store.obtenir_suivi("suivi_inexistant") is None


# ── ressources : partage sans duplication ─────────────────────────────

def test_une_ressource_partagee_entre_deux_suivis_nest_pas_dupliquee(store):
    s1 = store.creer_suivi("Matière", "matiere")
    s2 = store.creer_suivi("Projet", "projet")
    ressource = store.ajouter_ressource("document", "sujet.pdf", "copie", "sujet.pdf")

    store.associer_ressource(s1["id"], ressource["id"])
    store.associer_ressource(s2["id"], ressource["id"])

    assert len(store.lister_ressources()) == 1
    assert {s["id"] for s in store.suivis_utilisant(ressource["id"])} == {s1["id"], s2["id"]}


def test_retirer_une_association_ne_touche_pas_lautre_suivi(store):
    s1 = store.creer_suivi("Matière", "matiere")
    s2 = store.creer_suivi("Projet", "projet")
    ressource = store.ajouter_ressource("document", "sujet.pdf", "copie", "sujet.pdf")
    store.associer_ressource(s1["id"], ressource["id"])
    store.associer_ressource(s2["id"], ressource["id"])

    store.retirer_ressource(s2["id"], ressource["id"])

    assert ressource["id"] not in store.obtenir_suivi(s2["id"])["ressources"]
    assert ressource["id"] in store.obtenir_suivi(s1["id"])["ressources"]
    assert store.obtenir_ressource(ressource["id"]) is not None  # jamais supprimée


def test_associer_est_idempotent(store):
    s = store.creer_suivi("S", "ponctuel")
    r = store.ajouter_ressource("document", "x.pdf", "copie", "x.pdf")

    store.associer_ressource(s["id"], r["id"])
    store.associer_ressource(s["id"], r["id"])

    assert store.obtenir_suivi(s["id"])["ressources"] == [r["id"]]


def test_une_ressource_inaccessible_reste_et_explique_le_probleme(store):
    r = store.ajouter_ressource("depot_git", "repo", "chemin_externe", "/chemin/disparu")

    store.marquer_ressource(r["id"], False, "chemin introuvable")

    maj = store.obtenir_ressource(r["id"])
    assert maj["accessible"] is False
    assert maj["message_erreur"] == "chemin introuvable"


# ── échéances : plusieurs par suivi, ciblant des ressources différentes ─

def test_deux_echeances_de_la_meme_matiere_sur_des_chapitres_differents(store):
    s = store.creer_suivi("ML", "matiere", matiere="Machine Learning")
    e1 = store.ajouter_echeance(s["id"], "Partiel 1", "partiel", "2026-11-25", chapitres=["Régression"])
    e2 = store.ajouter_echeance(s["id"], "Partiel 2", "partiel", "2026-12-15", chapitres=["Réseaux"])

    titres = [e["titre"] for e in store.obtenir_suivi(s["id"])["echeances"]]
    assert titres == ["Partiel 1", "Partiel 2"]
    assert e1["id"] != e2["id"]


def test_ajouter_echeance_sur_suivi_inconnu_renvoie_none(store):
    assert store.ajouter_echeance("suivi_inexistant", "X", "devoir", "2026-01-01") is None


def test_lister_echeances_trie_toutes_matieres_confondues(store):
    s1 = store.creer_suivi("Maths", "matiere")
    s2 = store.creer_suivi("ML", "matiere")
    store.ajouter_echeance(s1["id"], "Devoir", "devoir", "2026-12-01")
    store.ajouter_echeance(s2["id"], "Partiel", "partiel", "2026-11-25")

    paires = store.lister_echeances(a_venir_seulement=False)

    assert [e["titre"] for _, e in paires] == ["Partiel", "Devoir"]


def test_a_venir_seulement_exclut_le_passe(store):
    s = store.creer_suivi("S", "matiere")
    store.ajouter_echeance(s["id"], "Vieux", "devoir", "2000-01-01")
    store.ajouter_echeance(s["id"], "Futur", "partiel", "2099-01-01")

    paires = store.lister_echeances(a_venir_seulement=True)

    assert [e["titre"] for _, e in paires] == ["Futur"]


def test_trouver_echeance_cherche_dans_tous_les_suivis(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01")

    trouve = store.trouver_echeance(e["id"])

    assert trouve is not None
    assert trouve[0]["id"] == s["id"] and trouve[1]["id"] == e["id"]
    assert store.trouver_echeance("ech_inexistant") is None


def test_maj_echeance_reporte_la_date(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01")

    maj = store.maj_echeance(s["id"], e["id"], date="2026-02-01", statut="reportee")

    assert maj["date"] == "2026-02-01" and maj["statut"] == "reportee"


def test_maj_echeance_ignore_les_champs_non_fournis(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01", notes="initial")

    maj = store.maj_echeance(s["id"], e["id"], date="2026-02-01")

    assert maj["notes"] == "initial"


# ── exercices ────────────────────────────────────────────────────────────

def test_exercice_garde_lhistorique_de_ses_tentatives_et_le_compteur_dindices(store):
    s = store.creer_suivi("S", "matiere")
    x = store.ajouter_exercice(s["id"], "TD1")

    store.maj_exercice(s["id"], x["id"], tentative="premier essai, raté")
    store.maj_exercice(s["id"], x["id"], indice=True)
    maj = store.maj_exercice(s["id"], x["id"], statut="termine", tentative="deuxième essai, ok")

    assert maj["statut"] == "termine"
    assert [t["texte"] for t in maj["tentatives"]] == ["premier essai, raté", "deuxième essai, ok"]
    assert maj["indices_donnes"] == 1


def test_un_exercice_termine_ne_deduit_rien_dans_lhistorique(store):
    """Rien dans le store ne touche à `historique` quand un exercice passe à
    "termine" — la distinction maîtrise/exercice-fait vient de l'appelant."""
    s = store.creer_suivi("S", "matiere")
    x = store.ajouter_exercice(s["id"], "TD1")

    store.maj_exercice(s["id"], x["id"], statut="termine")

    assert store.obtenir_suivi(s["id"])["historique"] == []


def test_ajouter_exercice_sur_suivi_inconnu_renvoie_none(store):
    assert store.ajouter_exercice("suivi_inexistant", "X") is None


# ── tâches ───────────────────────────────────────────────────────────────

def test_tache_distincte_dun_exercice(store):
    s = store.creer_suivi("S", "matiere")
    t = store.ajouter_tache(s["id"], "Relire le chapitre 3")

    assert t["statut"] == "a_faire"
    maj = store.maj_tache(s["id"], t["id"], "fait")
    assert maj["statut"] == "fait"


# ── historique ───────────────────────────────────────────────────────────

def test_point_avancement_peut_viser_une_echeance_precise_ou_le_suivi_entier(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01")

    store.ajouter_point_avancement(s["id"], "point général")
    store.ajouter_point_avancement(s["id"], "point ciblé", echeance_id=e["id"])

    historique = store.obtenir_suivi(s["id"])["historique"]
    assert historique[0]["echeance_id"] is None
    assert historique[1]["echeance_id"] == e["id"]
    assert historique[0]["origine"] == "utilisateur"


# ── rappels ──────────────────────────────────────────────────────────────

def test_rappel_echeance_ajoute_puis_retire(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01")

    store.ajouter_rappel_echeance(s["id"], e["id"], "cron_abc", "2025-12-28T09:00:00")
    assert len(store.trouver_echeance(e["id"])[1]["rappels"]) == 1

    retire = store.retirer_rappel_echeance(s["id"], e["id"], "cron_abc")
    assert retire is True
    assert store.trouver_echeance(e["id"])[1]["rappels"] == []


def test_rappel_suivi_recurrent_ajoute_puis_retire(store):
    s = store.creer_suivi("S", "matiere")

    store.ajouter_rappel_suivi(s["id"], "cron_xyz", "2026-01-08T09:00:00", 7)
    assert len(store.obtenir_suivi(s["id"])["rappels"]) == 1

    retire = store.retirer_rappel_suivi(s["id"], "cron_xyz")
    assert retire is True
    assert store.obtenir_suivi(s["id"])["rappels"] == []


def test_retirer_un_rappel_absent_renvoie_false(store):
    s = store.creer_suivi("S", "matiere")
    e = store.ajouter_echeance(s["id"], "X", "devoir", "2026-01-01")

    assert store.retirer_rappel_echeance(s["id"], e["id"], "cron_jamais_ajoute") is False
    assert store.retirer_rappel_suivi(s["id"], "cron_jamais_ajoute") is False


# ── résultats : existent sans suivi, se rattachent après coup ─────────

def test_un_resultat_de_travail_rapide_nest_rattache_a_rien(store):
    gen = store.ajouter_resultat("fiche", "fiche_rapide.html", ressources_utilisees=["res_x"])

    assert gen["suivi_id"] is None
    assert gen in store.lister_resultats()


def test_rattacher_un_resultat_apres_coup(store):
    s = store.creer_suivi("S", "matiere")
    gen = store.ajouter_resultat("fiche", "f.html")

    rattache = store.rattacher_resultat(gen["id"], s["id"])

    assert rattache["suivi_id"] == s["id"]
    assert [r["id"] for r in store.lister_resultats(suivi_id=s["id"])] == [gen["id"]]


def test_rattacher_vers_un_suivi_inconnu_echoue_sans_rien_changer(store):
    gen = store.ajouter_resultat("fiche", "f.html")

    assert store.rattacher_resultat(gen["id"], "suivi_inexistant") is None
    assert store.obtenir_resultat(gen["id"])["suivi_id"] is None


def test_lister_resultats_trie_du_plus_recent(store):
    store.ajouter_resultat("fiche", "a.html")
    store.ajouter_resultat("exo", "b.html")

    fichiers = [r["fichier"] for r in store.lister_resultats()]
    assert fichiers == ["b.html", "a.html"]


# ── identifiants stables ──────────────────────────────────────────────

def test_les_identifiants_sont_stables_et_distincts(store):
    s1 = store.creer_suivi("A", "matiere")
    s2 = store.creer_suivi("B", "matiere")

    assert s1["id"] != s2["id"]
    assert store.obtenir_suivi(s1["id"])["titre"] == "A"


# ── fichier corrompu ──────────────────────────────────────────────────

def test_un_fichier_corrompu_redevient_un_store_vide_sans_lever(store, tmp_path):
    fichier = tmp_path / "etudes.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text("{ceci n'est pas du json")

    assert store.lister_suivis() == []


# ── migration v1 → v2 ──────────────────────────────────────────────────

def test_migration_v1_vers_v2_ne_perd_aucune_donnee(store, tmp_path):
    ancien = {
        "version": 1,
        "echeances": [{
            "id": "ech_ancien1",
            "type": "partiel", "matiere": "Machine Learning", "titre": "Partiel",
            "date": "2026-11-25", "chapitres": ["Régression"], "documents": ["fiche_ml.html"],
            "notes": "", "created_at": "2026-10-01T10:00:00", "updated_at": "2026-10-01T10:00:00",
            "exercices": [{
                "id": "exo_ancien1", "titre": "TD1", "description": "", "statut": "termine",
                "tentatives": [{"date": "2026-10-02T10:00:00", "texte": "ok"}], "difficultes": [],
                "created_at": "2026-10-01T10:00:00", "updated_at": "2026-10-02T10:00:00",
            }],
            "historique": [{"date": "2026-10-02T10:00:00", "texte": "Je bloque sur les arbres"}],
            "rappels": [{"cron_id": "cron_old", "offset_jours": 3, "quand": "2026-11-22T09:00:00"}],
        }],
    }
    fichier = tmp_path / "etudes.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps(ancien))

    suivis = store.lister_suivis()

    assert len(suivis) == 1
    s = suivis[0]
    assert s["matiere"] == "Machine Learning" and s["type"] == "matiere"
    assert len(s["echeances"]) == 1 and s["echeances"][0]["titre"] == "Partiel"
    assert len(s["exercices"]) == 1
    assert s["exercices"][0]["echeance_id"] == "ech_ancien1"
    assert s["historique"][0]["texte"] == "Je bloque sur les arbres"
    assert s["historique"][0]["origine"] == "utilisateur"
    ressource = store.obtenir_ressource(s["ressources"][0])
    assert ressource["nom"] == "fiche_ml.html" and ressource["provenance"] == "copie"
    # réécrite tout de suite en v2 sur disque — la migration n'arrive qu'une fois
    assert json.loads(fichier.read_text())["version"] == 2


# ── générations (fiche/exo) en cours — §1, lot 3 ───────────────────────

def test_un_fichier_v2_sans_generations_est_complete_pas_vide(store, tmp_path):
    """`generations` est arrivée après coup sur le schéma v2 — un fichier déjà
    écrit par une version antérieure du store ne doit jamais être traité
    comme invalide (ce qui le viderait silencieusement)."""
    fichier = tmp_path / "etudes.json"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_text(json.dumps({
        "version": 2,
        "suivis": [{"id": "suivi_x", "titre": "Gardé", "type": "matiere", "matiere": "", "description": "",
                    "archive": False, "ressources": [], "echeances": [], "exercices": [], "taches": [],
                    "historique": [], "rappels": [], "verifications": [],
                    "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"}],
        "ressources": [], "resultats": [],
    }))

    assert [s["titre"] for s in store.lister_suivis()] == ["Gardé"]
    assert store.generation_active(None, "fiche") is None


def test_demarrer_puis_terminer_une_generation(store):
    gen = store.demarrer_generation(None, "fiche", parametres={"filename": "algo"})

    assert gen["statut"] == "en_cours"
    assert gen["id"].startswith("task_")

    termine = store.terminer_generation(gen["id"], "gen_resultat123")
    assert termine["statut"] == "terminee"
    assert termine["resultat_id"] == "gen_resultat123"
    assert termine["finished_at"] is not None


def test_echouer_une_generation_garde_le_message_derreur(store):
    gen = store.demarrer_generation("suivi_x", "exo")

    echouee = store.echouer_generation(gen["id"], "aucun fournisseur n'a répondu")

    assert echouee["statut"] == "echouee"
    assert echouee["erreur"] == "aucun fournisseur n'a répondu"
    assert echouee["resultat_id"] is None


def test_generation_active_distingue_suivi_et_type(store):
    """Le verrou anti-doublon (§1) est spécifique à (suivi_id, type) — un
    exo en cours sur un suivi ne doit jamais bloquer une fiche sur ce même
    suivi, ni une génération sur un AUTRE suivi."""
    store.demarrer_generation("suivi_a", "exo")

    assert store.generation_active("suivi_a", "exo") is not None
    assert store.generation_active("suivi_a", "fiche") is None
    assert store.generation_active("suivi_b", "exo") is None
    assert store.generation_active(None, "exo") is None


def test_une_generation_terminee_ne_bloque_plus_rien(store):
    """Il doit rester possible de relancer volontairement une nouvelle
    génération après que la précédente a fini (§1) — le verrou ne porte que
    sur ce qui est RÉELLEMENT en cours."""
    gen = store.demarrer_generation("suivi_a", "fiche")
    store.terminer_generation(gen["id"], "gen_x")

    assert store.generation_active("suivi_a", "fiche") is None


def test_derniere_generation_renvoie_la_plus_recente(store):
    premiere = store.demarrer_generation("suivi_a", "fiche")
    store.terminer_generation(premiere["id"], "gen_1")
    seconde = store.demarrer_generation("suivi_a", "fiche")

    derniere = store.derniere_generation("suivi_a", "fiche")
    assert derniere["id"] == seconde["id"]
    assert derniere["statut"] == "en_cours"


def test_purger_generations_bloquees_echoue_les_en_cours(store):
    """Simule un redémarrage pendant une génération (§1) : au prochain
    démarrage, toute génération restée `en_cours` doit être explicitement
    marquée en échec — jamais laissée `en_cours` pour toujours, ce qui
    bloquerait silencieusement tout nouveau lancement."""
    bloquee = store.demarrer_generation("suivi_a", "fiche")
    terminee = store.demarrer_generation("suivi_b", "exo")
    store.terminer_generation(terminee["id"], "gen_ok")

    purgees = store.purger_generations_bloquees()

    assert purgees == 1
    assert store.obtenir_generation(bloquee["id"])["statut"] == "echouee"
    assert store.obtenir_generation(terminee["id"])["statut"] == "terminee"  # pas touchée
    assert store.generation_active("suivi_a", "fiche") is None  # débloqué


# ── suppression définitive d'un suivi ─────────────────────────────────

def test_supprimer_un_suivi_garde_ses_resultats_et_les_ressources_partagees(store):
    gardee = store.creer_suivi("Gardé", "projet")
    supprime = store.creer_suivi("À supprimer", "projet")
    partagee = store.ajouter_ressource("depot_git", "back", "chemin_externe", "/p/back")
    exclusive = store.ajouter_ressource("dossier", "brouillon", "chemin_externe", "/p/brouillon")
    store.associer_ressource(gardee["id"], partagee["id"])
    store.associer_ressource(supprime["id"], partagee["id"])
    store.associer_ressource(supprime["id"], exclusive["id"])
    resultat = store.ajouter_resultat("fiche", "fiche.html", suivi_id=supprime["id"])

    assert store.supprimer_suivi(supprime["id"])["titre"] == "À supprimer"

    assert [s["id"] for s in store.lister_suivis()] == [gardee["id"]]
    assert store.obtenir_resultat(resultat["id"])["suivi_id"] is None  # fiche gardée, détachée
    assert store.obtenir_ressource(partagee["id"]) is not None          # encore utilisée ailleurs
    assert store.obtenir_ressource(exclusive["id"]) is None             # ne servait qu'à lui


def test_supprimer_un_suivi_inconnu_renvoie_none(store):
    assert store.supprimer_suivi("suivi_inexistant") is None
