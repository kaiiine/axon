"""src/ui/app.py — handlers des actions Études envoyées par l'île.

`run_cli` enregistre ces handlers comme closures sur le singleton `pont` ;
on le lance avec un `stream_once` qui s'arrête aussitôt, puis on appelle
chaque handler avec les VRAIS outils `etude_*` sur un état isolé. Le socket
est redirigé vers un dossier vide (rien n'atteint une île réellement
lancée) et `pont.envoyer` est remplacé par un enregistreur.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def app(monkeypatch, tmp_path):
    return _demarrer_cli(monkeypatch, tmp_path)


def _demarrer_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path / "etat"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "runtime"))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.agents.cron.store as cron_store
    import src.agents.study.tools_suivi as tools_suivi
    import src.agents.study.tools_echeance as tools_echeance
    import src.agents.study.tools as tools
    for module in (chemins, store, cron_store, tools_suivi, tools_echeance, tools):
        importlib.reload(module)

    import src.ui.app as app_module
    import src.ui.streaming as streaming
    from src.ui.pont_overlay import pont

    envois: list[dict] = []
    monkeypatch.setattr(pont, "envoyer", lambda **m: envois.append(m) or True)
    monkeypatch.setattr(app_module.console, "clear", lambda: None)
    monkeypatch.setattr(app_module, "load_last_thread", lambda: None)
    monkeypatch.setattr(app_module, "save_last_thread", lambda _t: None)
    monkeypatch.setattr(app_module, "save_thread_cwd", lambda *_a: None)

    def arret_immediat(*_a, **_k):
        raise KeyboardInterrupt
    monkeypatch.setattr(streaming, "stream_once", arret_immediat)

    app_module.run_cli(graph=None)
    return pont, store, envois


def _reponses(envois, type_):
    return [e for e in envois if e["type"] == type_]


def test_creer_suivi_confirme_l_id_et_rafraichit_la_liste(app):
    pont, store, envois = app

    pont.sur_creer_suivi("s1", "Machine Learning", "matiere", "ML")

    assert [s["titre"] for s in store.lister_suivis()] == ["Machine Learning"]
    assert _reponses(envois, "creer_suivi_resultat") == [{"type": "creer_suivi_resultat", "id": "s1"}]
    rafraichi = _reponses(envois, "raccourci_resultat")[-1]
    assert rafraichi["action"] == "etudes_suivis" and rafraichi["rows"][0]["title"] == "Machine Learning"


def test_creer_suivi_invalide_repond_une_erreur_sans_rien_creer(app):
    pont, store, envois = app

    pont.sur_creer_suivi("s2", "X", "type_inexistant", "")

    assert store.lister_suivis() == []
    erreur = _reponses(envois, "creer_suivi_erreur")
    assert len(erreur) == 1 and erreur[0]["id"] == "s2" and "Type inconnu" in erreur[0]["message"]


def test_creer_puis_reporter_puis_annuler_une_echeance(app):
    pont, store, envois = app
    suivi = store.creer_suivi("ML", "matiere")

    pont.sur_creer_echeance("e1", suivi["id"], "Partiel", "partiel", "2099-11-25")
    echeance = store.lister_suivis()[0]["echeances"][0]
    assert echeance["titre"] == "Partiel"
    assert {"type": "etudes_action_resultat", "id": "e1"} in envois

    pont.sur_maj_echeance("e2", suivi["id"], echeance["id"], "2099-12-02", None)
    assert store.trouver_echeance(echeance["id"])[1]["date"] == "2099-12-02"
    assert {"type": "etudes_action_resultat", "id": "e2"} in envois

    pont.sur_maj_echeance("e3", suivi["id"], echeance["id"], None, "annulee")
    assert store.trouver_echeance(echeance["id"])[1]["statut"] == "annulee"
    assert {"type": "etudes_action_resultat", "id": "e3"} in envois

    actions_rafraichies = {e["action"] for e in _reponses(envois, "raccourci_resultat")}
    assert {"etudes_suivis", "etudes_echeances"} <= actions_rafraichies


def test_echeance_sur_un_suivi_inconnu_repond_une_erreur(app):
    pont, _store, envois = app

    pont.sur_creer_echeance("e4", "suivi_inexistant", "Partiel", "partiel", "2099-11-25")

    erreur = _reponses(envois, "etudes_action_erreur")
    assert len(erreur) == 1 and erreur[0]["id"] == "e4" and "introuvable" in erreur[0]["message"]


def test_archiver_un_suivi_le_retire_des_suivis_actifs(app):
    pont, store, envois = app
    suivi = store.creer_suivi("À archiver", "matiere")

    pont.sur_archiver_suivi("a1", suivi["id"])

    assert store.lister_suivis() == []
    assert [s["id"] for s in store.lister_suivis(archives=True)] == [suivi["id"]]
    assert {"type": "etudes_action_resultat", "id": "a1"} in envois


def test_le_demarrage_purge_une_generation_restee_en_cours(monkeypatch, tmp_path):
    """Redémarrage pendant une génération (§1) : `run_cli` doit la marquer
    échouée dès le démarrage, sinon elle bloquerait tout nouveau lancement."""
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path / "etat"))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    importlib.reload(chemins)
    importlib.reload(store)
    bloquee = store.demarrer_generation(None, "fiche")

    _demarrer_cli(monkeypatch, tmp_path)

    assert store.obtenir_generation(bloquee["id"])["statut"] == "echouee"


def _attendre_reponse(envois, id_, delai=3.0):
    """`sur_lier_ressource` travaille dans un thread (le sélecteur natif
    bloque) : on attend sa réponse pour CET id."""
    import time
    fin = time.time() + delai
    while time.time() < fin:
        for e in envois:
            if e.get("id") == id_ and e["type"] in ("etudes_action_resultat", "etudes_action_erreur"):
                return e
        time.sleep(0.02)
    raise AssertionError(f"pas de réponse pour {id_}")


def test_lier_un_depot_git_l_associe_au_suivi_comme_depot(app, monkeypatch, tmp_path):
    pont, store, envois = app
    depot = tmp_path / "compilateur"
    (depot / ".git").mkdir(parents=True)
    import src.ui.attachments as attachments
    monkeypatch.setattr(attachments, "open_file_picker", lambda dossier=False: str(depot) if dossier else None)
    suivi = store.creer_suivi("Projet Compilateur", "projet")

    pont.sur_lier_ressource("l1", suivi["id"], "dossier")

    assert _attendre_reponse(envois, "l1")["type"] == "etudes_action_resultat"
    ressources = [store.obtenir_ressource(rid) for rid in store.obtenir_suivi(suivi["id"])["ressources"]]
    assert [(r["type"], r["chemin"], r["provenance"]) for r in ressources] == [("depot_git", str(depot), "chemin_externe")]
    ligne = next(e for e in envois if e["type"] == "raccourci_resultat" and e["action"] == "etudes_suivis")["rows"][0]
    assert "1 ressource" in ligne["meta"]


def test_annuler_le_selecteur_ne_lie_rien_mais_repond(app, monkeypatch):
    pont, store, envois = app
    import src.ui.attachments as attachments
    monkeypatch.setattr(attachments, "open_file_picker", lambda dossier=False: None)
    suivi = store.creer_suivi("ML", "matiere")

    pont.sur_lier_ressource("l2", suivi["id"], "fichier")

    assert _attendre_reponse(envois, "l2")["type"] == "etudes_action_resultat"
    assert store.obtenir_suivi(suivi["id"])["ressources"] == []


def test_un_depot_choisi_sans_suivi_cree_un_projet_a_son_nom(app, monkeypatch, tmp_path):
    """Bouton « Dossier ou dépôt » de la zone de dépôt : pas de suivi visé,
    le dépôt devient un suivi « projet » à son nom, avec le dépôt lié."""
    pont, store, envois = app
    depot = tmp_path / "compilateur"
    (depot / ".git").mkdir(parents=True)
    import src.ui.attachments as attachments
    monkeypatch.setattr(attachments, "open_file_picker", lambda dossier=False: str(depot))

    pont.sur_lier_ressource("l3", "", "dossier")

    assert _attendre_reponse(envois, "l3")["type"] == "etudes_action_resultat"
    [suivi] = store.lister_suivis()
    assert (suivi["titre"], suivi["type"]) == ("compilateur", "projet")
    assert store.obtenir_ressource(suivi["ressources"][0])["type"] == "depot_git"


def test_glisser_un_dossier_sur_l_ile_cree_un_suivi_au_lieu_d_une_piece_jointe(app, tmp_path):
    import time
    pont, store, envois = app
    dossier = tmp_path / "cours-reseaux"
    dossier.mkdir()

    pont.sur_joindre(str(dossier))

    fin = time.time() + 3
    while not store.lister_suivis() and time.time() < fin:
        time.sleep(0.02)
    [suivi] = store.lister_suivis()
    assert (suivi["titre"], suivi["type"]) == ("cours-reseaux", "autre")
    assert store.obtenir_ressource(suivi["ressources"][0])["type"] == "dossier"
    from src.ui.attachments import attachments as pieces
    assert all(a.name != "cours-reseaux" for a in pieces.items)


def test_supprimer_un_suivi_depuis_l_ile(app):
    pont, store, envois = app
    suivi = store.creer_suivi("be-cds", "projet")

    pont.sur_supprimer_suivi("d1", suivi["id"])

    assert store.lister_suivis() == []
    assert {"type": "etudes_action_resultat", "id": "d1"} in envois


def test_supprimer_un_suivi_inconnu_repond_une_erreur(app):
    pont, _store, envois = app

    pont.sur_supprimer_suivi("d2", "suivi_inexistant")

    assert _reponses(envois, "etudes_action_erreur")[0]["id"] == "d2"


def test_la_cloche_programme_les_rappels_d_une_echeance(app):
    pont, store, envois = app
    from src.agents.cron.store import get_tasks
    suivi = store.creer_suivi("P", "projet")
    echeance = store.ajouter_echeance(suivi["id"], "Rendu", "rendu_projet", "2099-12-10")

    pont.sur_planifier_rappels("c1", suivi["id"], echeance["id"])

    assert {"type": "etudes_action_resultat", "id": "c1"} in envois
    assert len([t for t in get_tasks() if t["active"]]) == 3
