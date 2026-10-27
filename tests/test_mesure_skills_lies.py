"""outils/mesure_skills_lies.py et son jeu de requêtes.

Le jeu est écrit une fois et jamais relu pendant le réglage : encore faut-il qu'il
soit sain. Une faute de nom de groupe ferait planter la mesure après dix minutes
de construction d'index ; une requête en double fausserait les taux.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mesure_skills_lies as mesure  # noqa: E402
from corpus_skills_lies import ACTIONS, AMBIGUES, SKILLS  # noqa: E402


def test_chaque_groupe_du_jeu_existe_dans_le_routeur():
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

    groupes = {g for _, g in ACTIONS} | {g for _, _, gs in AMBIGUES for g in gs}
    assert groupes <= set(TOOL_GROUPS)


def test_chaque_skill_attendu_est_routable_par_l_orchestrateur():
    from src.skills import skills_routables

    routables = {nom for nom, _ in skills_routables("orchestrator")}
    attendus = {famille.split(" — ")[0] for famille in SKILLS} | {s for _, s, _ in AMBIGUES}
    assert attendus <= routables


def test_aucune_requete_en_double_ni_vide():
    requetes = mesure._requetes()
    assert all(q.strip() for q in requetes)
    assert len(requetes) == len(set(requetes))


def test_la_redaction_est_mesuree_avec_et_sans_le_mot_mail():
    avec = [q for q in SKILLS["redaction — avec « mail »"]]
    sans = [q for q in SKILLS["redaction — sans « mail »"]]
    assert all("mail" in q.lower() for q in avec)
    assert not any("mail" in q.lower() for q in sans)


def _reponse(*appels):
    return SimpleNamespace(tool_calls=[{"name": n, "args": a, "id": str(i)} for i, (n, a) in enumerate(appels)])


@pytest.mark.parametrize("appels, attendu, verdict", [
    ([("load_skill", {"stack": "redaction"})], "redaction", "CHARGE"),
    ([("load_skill", {"stack": " Redaction "})], "redaction", "CHARGE"),
    ([("load_skill", {"stack": "pentest"})], "redaction", "AUTRE SKILL"),
    ([("gmail_send_email", {})], "redaction", "SANS SKILL"),
    ([], "redaction", "TEXTE"),
    ([("ask_clarification", {}), ("load_skill", {"stack": "redaction"})], "redaction", "CHARGE"),
])
def test_le_classement_des_reponses_du_modele(appels, attendu, verdict):
    assert mesure.classer(_reponse(*appels), attendu) == verdict


def test_une_action_pure_ne_doit_charger_aucun_skill():
    assert mesure.classer(_reponse(("gmail_send_email", {})), "-") == "SANS SKILL"
    assert mesure.classer(_reponse(("load_skill", {"stack": "redaction"})), "-") == "AUTRE SKILL"


def test_les_pourcentages_se_lisent_en_fraction_et_en_taux():
    assert mesure._pct(11, 15) == "11/15   73.3 %"


def test_un_ecart_est_un_outil_d_action_lie_avant_et_perdu_apres():
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

    requete, groupe = ACTIONS[0]
    outil = sorted(TOOL_GROUPS[groupe].tools)[0]
    noms_avant = {q: set() for q in mesure._requetes()}
    noms_apres = {q: set() for q in mesure._requetes()}
    noms_avant[requete] = {outil}
    perdus = mesure._ecarts({"noms": noms_avant}, {"noms": noms_apres})
    assert len(perdus) == 1 and outil in perdus[0]
    noms_apres[requete] = {outil}
    assert mesure._ecarts({"noms": noms_avant}, {"noms": noms_apres}) == []
