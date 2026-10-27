"""src/orchestrator/routage/skills_lies.py — `load_skill` lié hors du classement.

Vécu : « rédige un mail à mon patron » n'a jamais proposé `load_skill`. Le groupe
« skills », moyenne de tous les skills, perdait face à `gmail`, et rien d'autre
n'ajoutait l'outil à la sélection.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.orchestrator.routage import skills_lies


def _outil(nom: str):
    return SimpleNamespace(name=nom, description=f"outil {nom}")


@pytest.fixture
def reglage(monkeypatch):
    """Le drapeau, sans dépendre du `.env` de la machine."""
    from src.infra.settings import settings

    def poser(valeur: bool):
        monkeypatch.setattr(settings, "skills_toujours_lies", valeur, raising=False)
    return poser


@pytest.fixture
def skills(monkeypatch):
    """Un catalogue réduit, sans index sémantique ni Ollama."""
    fabrique = []

    def faux_make(portee, requete=""):
        fabrique.append((portee, requete))
        return _outil("load_skill")

    monkeypatch.setattr("src.skills.tools.make_load_skill", faux_make)
    monkeypatch.setattr("src.skills.skills_routables", lambda portee=None: [("redaction", "d")])
    return fabrique


def test_le_drapeau_est_actif_par_defaut():
    from src.infra.settings import Settings

    assert Settings.model_fields["skills_toujours_lies"].default is True


def test_le_groupe_moyenne_est_neutralise_seulement_quand_le_drapeau_est_actif(reglage):
    reglage(True)
    assert skills_lies.groupes_neutralises() == {"skills"}
    reglage(False)
    assert skills_lies.groupes_neutralises() == frozenset()


def test_load_skill_est_ajoute_meme_si_aucun_groupe_ne_l_a_elu(reglage, skills):
    reglage(True)
    gmail = [_outil("gmail_send_email"), _outil("gmail_summarize")]
    lies = skills_lies.appliquer_les_skills(gmail, "rédige un mail à mon patron", "orchestrator")
    assert [o.name for o in lies] == ["gmail_send_email", "gmail_summarize", "load_skill"]
    assert skills == [("orchestrator", "rédige un mail à mon patron")]


def test_les_autres_outils_ne_sont_ni_retires_ni_reordonnes(reglage, skills):
    reglage(True)
    avant = [_outil(n) for n in ("a", "b", "c")]
    assert [o.name for o in skills_lies.appliquer_les_skills(avant, "x", "orchestrator")][:3] == ["a", "b", "c"]


def test_un_load_skill_deja_elu_n_est_pas_double(reglage, skills):
    reglage(True)
    lies = skills_lies.appliquer_les_skills([_outil("load_skill"), _outil("git_status")], "x", "orchestrator")
    assert [o.name for o in lies].count("load_skill") == 1
    assert lies[-1].name == "load_skill"


def test_sans_skill_routable_load_skill_est_retire_plutot_que_lie_vide(reglage, monkeypatch):
    reglage(True)
    monkeypatch.setattr("src.skills.skills_routables", lambda portee=None: [])
    lies = skills_lies.appliquer_les_skills([_outil("load_skill"), _outil("git_status")], "x", "orchestrator")
    assert [o.name for o in lies] == ["git_status"]


def test_un_echec_de_construction_laisse_la_selection_telle_quelle(reglage, monkeypatch):
    reglage(True)
    monkeypatch.setattr("src.skills.skills_routables", lambda portee=None: [("redaction", "d")])

    def casse(*_a, **_k):
        raise RuntimeError("index illisible")

    monkeypatch.setattr("src.skills.tools.make_load_skill", casse)
    selection = [_outil("git_status")]
    assert skills_lies.appliquer_les_skills(selection, "x", "orchestrator") is selection


def test_drapeau_desactive_l_ancien_routage_ne_lie_rien_de_plus(reglage, skills):
    reglage(False)
    sans = [_outil("gmail_send_email")]
    assert skills_lies.appliquer_les_skills(sans, "rédige un mail", "orchestrator") is sans
    assert skills == []


def test_drapeau_desactive_restreint_le_load_skill_deja_elu(reglage, skills):
    reglage(False)
    lies = skills_lies.appliquer_les_skills([_outil("load_skill"), _outil("git_status")], "un site", "coding")
    assert [o.name for o in lies] == ["load_skill", "git_status"]
    assert skills == [("coding", "un site")]


def test_ancienne_restriction_requete_vide_ou_sans_load_skill_rend_la_liste_intacte():
    outils = [_outil("git_status")]
    assert skills_lies.restreindre_les_skills(outils, "un site", "coding") is outils
    avec = [_outil("load_skill")]
    assert skills_lies.restreindre_les_skills(avec, "   ", "coding") is avec


def test_le_nom_historique_reste_importable_depuis_le_noeud_de_chat():
    from src.orchestrator.noeuds.chat import _restreindre_les_skills

    assert _restreindre_les_skills is skills_lies.restreindre_les_skills


# ── le groupe « skills » dans le routeur d'outils ─────────────────────────────

def _retriever_factice(monkeypatch, classes):
    """Un `ToolRetriever` sans base vectorielle : le classement des groupes est
    imposé, l'élection et le budget sont les vrais."""
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS, ToolRetriever

    retriever = object.__new__(ToolRetriever)
    retriever._tools = [_outil(nom) for groupe in classes for nom in TOOL_GROUPS[groupe].tools]
    monkeypatch.setattr(retriever, "_rank_groups_detaille",
                        lambda requete: (list(classes), {g: i for i, g in enumerate(classes, 1)}),
                        raising=False)
    monkeypatch.setattr(retriever, "_tools_of", lambda groupe, requete: list(TOOL_GROUPS[groupe].tools),
                        raising=False)
    return retriever


def test_le_groupe_skills_n_est_pas_indexe_quand_les_skills_sont_toujours_lies(reglage):
    from src.orchestrator.routage.tool_retriever import _GROUP_SOURCE, _build_documents

    def groupes():
        docs = _build_documents([_outil("load_skill")])
        return {d.metadata["group"] for d in docs if d.metadata["source"] == _GROUP_SOURCE}

    reglage(False)
    assert "skills" in groupes()
    reglage(True)
    assert "skills" not in groupes()


def test_le_groupe_skills_n_est_jamais_elu_ni_tete_quand_les_skills_sont_toujours_lies(reglage, monkeypatch):
    reglage(True)
    retriever = _retriever_factice(monkeypatch, ["skills", "gmail"])
    noms = {t.name for t in retriever.get("rédige un mail")}
    assert "load_skill" not in noms and "gmail_send_email" in noms
    assert retriever.groupe_de_tete == "gmail"


def test_ancien_routage_le_groupe_skills_concourt_toujours(reglage, monkeypatch):
    reglage(False)
    retriever = _retriever_factice(monkeypatch, ["skills", "gmail"])
    assert "load_skill" in {t.name for t in retriever.get("réécris ce texte")}
    assert retriever.groupe_de_tete == "skills"
