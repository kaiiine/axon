"""Résolution des types de tickets Jira vers les noms RÉELS du projet.

Le bug vécu : « crée mes user stories » échouait en boucle parce que le projet
KAN n'a ni « Story » ni « Task » mais « Feature », « Tâche », « Sous-task ».
L'outil envoyait le nom figé « Story » → l'API Jira refusait, et rien ne
permettait de découvrir les vrais noms. On teste ici que le type demandé est
traduit vers un nom que le projet accepte vraiment.
"""
from __future__ import annotations

import pytest

from src.agents.jira import tools

#: Les types RÉELS du projet KAN de l'utilisateur (français + custom).
_KAN = (
    {"name": "Feature", "subtask": False},
    {"name": "Tâche", "subtask": False},
    {"name": "Sous-task", "subtask": True},
)


@pytest.fixture
def projet_kan(monkeypatch):
    """Simule la découverte des types du projet KAN, sans réseau."""
    monkeypatch.setattr(tools, "_project_issue_types", lambda _key: _KAN)


# ── _match_requested_type : la correspondance pure ──────────────────────────

def test_nom_identique_insensible_a_la_casse():
    assert tools._match_requested_type("feature", ("Feature", "Tâche")) == "Feature"


def test_story_trouve_feature_par_synonyme():
    """La raison d'être du fix : Story et Feature sont la même famille."""
    assert tools._match_requested_type("Story", ("Feature", "Tâche")) == "Feature"


def test_task_trouve_tache_par_synonyme():
    assert tools._match_requested_type("Task", ("Feature", "Tâche")) == "Tâche"


def test_aucune_correspondance_rend_none():
    assert tools._match_requested_type("Epic", ("Feature", "Tâche")) is None


# ── _resolve_issue_type : la traduction de bout en bout ─────────────────────

def test_story_se_resout_en_feature(projet_kan):
    assert tools._resolve_issue_type("KAN", "Story") == "Feature"


def test_task_se_resout_en_tache(projet_kan):
    assert tools._resolve_issue_type("KAN", "Task") == "Tâche"


def test_subtask_se_resout_dans_la_bonne_categorie(projet_kan):
    """Une sous-tâche ne doit JAMAIS se résoudre en type standard, ni l'inverse."""
    assert tools._resolve_issue_type("KAN", "Subtask", subtask=True) == "Sous-task"
    # un type standard demandé ne doit pas tomber sur la sous-tâche
    assert tools._resolve_issue_type("KAN", "Story", subtask=False) != "Sous-task"


def test_type_inconnu_retombe_sur_le_premier_standard(projet_kan):
    """« Epic » n'existe pas dans KAN : on crée avec un type valide plutôt que
    d'échouer — le premier type standard du projet."""
    assert tools._resolve_issue_type("KAN", "Epic") == "Feature"


def test_decouverte_vide_rend_le_type_demande_tel_quel(monkeypatch):
    """Si la découverte échoue (projet inconnu, API muette), on ne bloque pas :
    comportement d'avant, jamais plus mauvais."""
    monkeypatch.setattr(tools, "_project_issue_types", lambda _key: ())
    assert tools._resolve_issue_type("ZZZ", "Story") == "Story"


# ── _create_single : le câblage de bout en bout ─────────────────────────────

def test_la_creation_envoie_le_type_resolu_a_lapi(projet_kan, monkeypatch):
    """Le scénario exact du bug : « Story » demandé → « Feature » envoyé à Jira."""
    envoye = {}

    def faux_post(_path, body):
        envoye["type"] = body["fields"]["issuetype"]["name"]
        return {"key": "KAN-99"}

    monkeypatch.setattr(tools, "_post", faux_post)
    tools._create_single("KAN", {"summary": "x", "issue_type": "Story"})

    assert envoye["type"] == "Feature"


def test_la_sous_tache_tente_le_nom_decouvert_en_premier(projet_kan, monkeypatch):
    """`_create_subtask` essaie d'abord le nom résolu dans le projet, pas un
    alias figé — sinon on multiplie les appels qui échouent."""
    essais = []

    def faux_post(_path, body):
        essais.append(body["fields"]["issuetype"]["name"])
        return {"key": "KAN-100"}

    monkeypatch.setattr(tools, "_post", faux_post)
    tools._create_single(
        "KAN", {"summary": "x", "issue_type": "Subtask", "parent_key": "KAN-1"})

    assert essais[0] == "Sous-task"


# ── Modification en masse : jira_update_issues_bulk ─────────────────────────

def test_update_single_envoie_les_champs_fournis(monkeypatch):
    envoye = {}
    monkeypatch.setattr(tools, "_put", lambda path, body: envoye.update(path=path, body=body))

    champs = tools._update_single("KAN-8", summary="Nouveau nom", priority="High")

    assert set(champs) == {"summary", "priority"}
    assert envoye["path"] == "issue/KAN-8"
    assert envoye["body"]["fields"]["summary"] == "Nouveau nom"
    assert envoye["body"]["fields"]["priority"] == {"name": "High"}


def test_update_single_resout_le_type(projet_kan, monkeypatch):
    """Le changement de type est corrigé comme la création : Story→Feature."""
    envoye = {}
    monkeypatch.setattr(tools, "_put", lambda path, body: envoye.update(body=body))

    tools._update_single("KAN-8", issue_type="Story")

    assert envoye["body"]["fields"]["issuetype"] == {"name": "Feature"}


def test_update_single_sans_champ_leve():
    with pytest.raises(ValueError):
        tools._update_single("KAN-8")


def test_epic_seul_range_sans_toucher_aux_champs(monkeypatch):
    appels = []
    monkeypatch.setattr(tools, "_update_single",
                        lambda *a, **k: appels.append("update") or [])
    monkeypatch.setattr(tools, "_link_to_epic_single",
                        lambda issue, epic: appels.append(("link", issue, epic)))

    champs = tools._apply_one_update({"key": "KAN-14", "epic_key": "KAN-30"})

    assert "update" not in appels               # aucun champ → pas de mise à jour
    assert ("link", "KAN-14", "KAN-30") in appels
    assert champs == ["epic"]


def test_champs_et_epic_combines(monkeypatch):
    monkeypatch.setattr(tools, "_update_single", lambda *a, **k: ["summary"])
    lies = []
    monkeypatch.setattr(tools, "_link_to_epic_single",
                        lambda issue, epic: lies.append((issue, epic)))

    champs = tools._apply_one_update(
        {"key": "KAN-14", "summary": "x", "epic_key": "KAN-30"})

    assert champs == ["summary", "epic"]
    assert lies == [("KAN-14", "KAN-30")]


def test_bulk_modifie_plusieurs_tickets_en_un_appel(monkeypatch):
    monkeypatch.setattr(tools, "_auth", lambda: ("https://jira.test", None))
    monkeypatch.setattr(tools, "_put", lambda path, body: None)

    res = tools.jira_update_issues_bulk.invoke({"updates": [
        {"key": "KAN-14", "summary": "Backend : table role"},
        {"key": "KAN-25", "summary": "Front : inscription", "epic_key": "KAN-32"},
    ]})

    assert res["status"] == "ok"
    assert res["updated_count"] == 2


def test_bulk_rapporte_les_echecs_sans_tout_arreter(monkeypatch):
    monkeypatch.setattr(tools, "_auth", lambda: ("https://jira.test", None))

    def faux_put(path, _body):
        if "KAN-99" in path:
            raise RuntimeError("404 introuvable")

    monkeypatch.setattr(tools, "_put", faux_put)

    res = tools.jira_update_issues_bulk.invoke({"updates": [
        {"key": "KAN-14", "summary": "ok"},
        {"key": "KAN-99", "summary": "boom"},
    ]})

    assert res["status"] == "partial"
    assert res["updated_count"] == 1
    assert res["errors"][0]["key"] == "KAN-99"
