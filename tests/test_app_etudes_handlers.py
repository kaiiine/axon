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
