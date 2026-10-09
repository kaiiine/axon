"""Les rattrapages de réponse fautive, exercés pour de vrai.

Ces règles existaient, mesurées et justifiées, mais elles étaient enfouies dans
une closure de 365 lignes au milieu du nœud `chatbot` — impossibles à appeler
depuis un test. `test_clarify_reask_guard.py` le dit sans détour dans ses
propres docstrings : « La condition telle que `graph.py` la pose désormais »,
suivi d'une RÉIMPLÉMENTATION locale de la condition. Ces tests-là passaient donc
même si le vrai code cassait.

Extraites dans `modele/corrections.py`, les mêmes règles s'appellent directement. Ce
fichier les exerce ; l'autre peut rester tel quel, il documente le raisonnement.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.orchestrator.modele.corrections import (
    Contexte,
    appel_ecrit_en_texte,
    appliquer,
    demande_de_precision,
    garde_actif,
    garde_du_domaine,
    question_deja_repondue,
    question_en_texte_libre,
)


class _Outil:
    def __init__(self, name):
        self.name = name


def _reponse_de_clarification(question: str, reponse: str) -> ToolMessage:
    import json
    return ToolMessage(
        content=json.dumps({"answers": {question: reponse}}),
        name="ask_clarification",
        tool_call_id="x",
    )


def _demande(questions: list[str]) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": "ask_clarification", "id": "1",
                     "args": {"questions": [{"question": q} for q in questions]}}],
    )


# ── le mécanisme lui-même ──────────────────────────────────────────────────────

def test_les_correcteurs_s_appliquent_en_chaine():
    """Le comportement d'origine : chacun examine la réponse telle que le
    précédent l'a laissée — pas un premier-qui-gagne."""
    vus = []

    def premier(response, ctx):
        vus.append(response.content)
        return ("un", "consigne un")

    def second(response, ctx):
        vus.append(response.content)
        return None

    appliquer(AIMessage(content="départ"), Contexte(),
              invoquer=lambda msgs: AIMessage(content="corrigé"),
              correcteurs=[premier, second])

    assert vus == ["départ", "corrigé"], "le second n'a pas vu le travail du premier"


def test_une_correction_qui_plante_garde_la_reponse_d_origine():
    """Mieux vaut une réponse imparfaite qu'un tour perdu."""
    def casse(messages):
        raise RuntimeError("le modèle est tombé")

    sortie = appliquer(AIMessage(content="origine"), Contexte(),
                       invoquer=casse,
                       correcteurs=[lambda r, c: ("x", "y")])

    assert sortie.content == "origine"


def test_sans_faute_le_modele_n_est_pas_rappele():
    appels = []
    sortie = appliquer(AIMessage(content="très bien"), Contexte(),
                       invoquer=lambda m: appels.append(m) or AIMessage(content="?"),
                       correcteurs=[lambda r, c: None])

    assert not appels, "un tour sans faute a coûté un appel modèle"
    assert sortie.content == "très bien"


# ── question déjà répondue ─────────────────────────────────────────────────────

def test_une_question_deja_repondue_est_detectee():
    ctx = Contexte(working=[_reponse_de_clarification("Quel sport ?", "tennis")])
    assert question_deja_repondue(_demande(["Quel sport ?"]), ctx) is not None


def test_une_question_neuve_passe():
    ctx = Contexte(working=[_reponse_de_clarification("Quel sport ?", "tennis")])
    assert question_deja_repondue(_demande(["Quelle période ?"]), ctx) is None


def test_la_synthese_forcee_desactive_la_detection():
    """`force_text` veut dire « plus d'outils, réponds » : reposer la question
    n'est plus possible, la corriger n'a pas de sens."""
    ctx = Contexte(working=[_reponse_de_clarification("Quel sport ?", "tennis")],
                   force_text=True)
    assert question_deja_repondue(_demande(["Quel sport ?"]), ctx) is None


# ── appel d'outil écrit en texte ───────────────────────────────────────────────

def test_un_appel_ecrit_en_texte_est_detecte():
    """La forme balisée : le modèle ÉCRIT l'appel au lieu de l'émettre, donc
    rien ne s'exécute et l'utilisateur reçoit du balisage."""
    faux = AIMessage(
        content='<shell:tool_call>{"command": "ls"}</shell:tool_call>')
    verdict = appel_ecrit_en_texte(faux, Contexte(selected_tools=[_Outil("shell_run")]))
    assert verdict is not None
    assert "function calling" in verdict[1]


def test_un_vrai_appel_d_outil_n_est_pas_corrige():
    vrai = AIMessage(content="", tool_calls=[{"name": "shell_run", "id": "1",
                                              "args": {"command": "ls"}}])
    assert appel_ecrit_en_texte(vrai, Contexte(selected_tools=[_Outil("shell_run")])) is None


def test_une_reponse_en_prose_n_est_pas_prise_pour_un_appel():
    texte = AIMessage(content="J'ai listé le dossier, il contient trois fichiers.")
    assert appel_ecrit_en_texte(texte, Contexte(selected_tools=[_Outil("shell_run")])) is None


# ── question en texte libre ────────────────────────────────────────────────────

def test_une_question_en_prose_est_detectee():
    q = AIMessage(content="Quel dossier veux-tu que je regarde ?")
    assert question_en_texte_libre(q, Contexte()) is not None


def test_une_vraie_reponse_finissant_par_une_question_passe():
    """Le défaut historique : une réponse complète terminée par « Tu veux que je
    détaille ? » déclenchait un questionnaire APRÈS coup, sans objet."""
    longue = AIMessage(content=(
        "J'ai parcouru le dossier et corrigé les trois appels fautifs : le premier "
        "passait `content=` au lieu de `texte=`, le deuxième et le troisième "
        "faisaient la même chose un peu plus bas dans le fichier. Les tests passent "
        "tous, y compris les trois que j'ai ajoutés pour couvrir chacune des issues. "
        "Rien d'autre n'a bougé dans le module. Tu veux que je détaille ?"))
    # Le seuil est une mesure, pas un jugement : ce qui compte est la substance
    # HORS questions, et elle doit dépasser 240 caractères.
    assert question_en_texte_libre(longue, Contexte()) is None


def test_le_mode_plan_desactive_la_correction():
    q = AIMessage(content="Quel dossier veux-tu que je regarde ?")
    assert question_en_texte_libre(q, Contexte(plan_mode=True)) is None


def test_les_reponses_deja_donnees_sont_rappelees_au_modele():
    q = AIMessage(content="Quel sport veux-tu suivre ?")
    ctx = Contexte(working=[_reponse_de_clarification("Quel sport ?", "tennis")])
    verdict = question_en_texte_libre(q, ctx)

    assert verdict is not None
    assert "tennis" in verdict[1], "la réponse déjà donnée n'est pas rappelée"


# ── le garde-fou et son exclusion ──────────────────────────────────────────────

def test_un_outil_de_flow_lie_par_ricochet_ne_desactive_pas_le_garde():
    """Mesuré sur 142 requêtes réelles : 33 tours liaient `slack_send_message`
    ou `git_commit`, 29 n'avaient rien à voir avec Slack ni un commit."""
    assert garde_actif([_Outil("slack_send_message")], "quant", working=[])


def test_un_vrai_tour_slack_garde_son_exclusion():
    assert not garde_actif([_Outil("slack_send_message")], "slack", working=[])
    assert not garde_actif([_Outil("git_commit")], "git", working=[])


def test_des_reponses_deja_donnees_rallument_le_garde():
    assert garde_actif([_Outil("slack_send_message")], "slack",
                       working=[_reponse_de_clarification("Quel canal ?", "#general")])


# ── la mesure de substance ─────────────────────────────────────────────────────

def test_une_reclamation_seche_est_une_demande():
    assert demande_de_precision("Quel fichier ?")


def test_une_affirmation_n_en_est_pas_une():
    assert not demande_de_precision("Le fichier a été créé dans /tmp/essai.")


# ── le garde de domaine ────────────────────────────────────────────────────────

def test_un_tour_avec_appels_d_outils_traverse_le_garde():
    """Le garde juge une réponse finale ; un tour qui appelle encore des outils
    n'en est pas une."""
    avec_outils = AIMessage(content="", tool_calls=[{"name": "x", "id": "1", "args": {}}])
    assert garde_du_domaine(avec_outils, working=[]) is avec_outils
