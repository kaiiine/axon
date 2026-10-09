# src/orchestrator/graph.py
"""Le graphe : dix nœuds, leurs arêtes, et rien d'autre.

Chaque nœud vit dans son fichier. Ce qui se lit ici est la STRUCTURE — qui suit
qui, et à quelle condition — pas ce que chaque étape fabrique.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import tools_condition

from src.infra.checkpoint import build_checkpointer
from src.orchestrator.state import GlobalState
from src.orchestrator.noeuds.chat import _chat_node_factory
from src.orchestrator.noeuds.outils import CachedToolNode
from src.orchestrator.noeuds.clarification import (
    appel_clarification, appels_en_attente, apres_les_outils, clarifier, clarifier_appel,
)
from src.orchestrator.noeuds.confirmation import apres_confirmation, confirmer
from src.orchestrator.noeuds.envoi import envoyer
from src.orchestrator.noeuds.plan import plan_a_valider, valider
from src.orchestrator.noeuds.revision import reviser, revision_attendue
from src.agents.coding.noeud import coder
from src.agents.deep.noeud import approfondir


def build_orchestrator():
    chatbot, tools = _chat_node_factory()

    g = StateGraph(GlobalState)
    g.add_node("chatbot", chatbot)
    g.add_node("tools", CachedToolNode(tools))
    g.add_node("clarifier", clarifier)
    g.add_node("clarifier_appel", clarifier_appel)
    g.add_node("confirmer", confirmer)
    g.add_node("reviser", reviser)
    g.add_node("envoyer", envoyer)
    g.add_node("valider_plan", valider)
    g.add_node("approfondir", approfondir)
    g.add_node("coder", coder)

    g.add_edge(START, "chatbot")
    # `tools_condition` mène à `tools` ou à la fin. On s'intercale avant la fin :
    # un plan se valide sur le TEXTE du modèle, pas sur un appel d'outil.
    def _apres_chatbot(state):
        route = tools_condition(state)
        if route == "tools" and appel_clarification(state["messages"][-1]):
            return "clarifier_appel"
        if route == END and plan_a_valider(state):
            return "valider_plan"
        return route

    g.add_conditional_edges("chatbot", _apres_chatbot,
                            {"tools": "tools", "clarifier_appel": "clarifier_appel",
                             "valider_plan": "valider_plan", END: END})
    # `tools` ne revient au modèle que si aucun nœud de demande n'a la main.
    g.add_conditional_edges("tools", apres_les_outils, {
        "clarifier": "clarifier",
        "confirmer": "confirmer",
        "reviser": "reviser",
        "envoyer": "envoyer",
        "approfondir": "approfondir",
        "coder": "coder",
        "chatbot": "chatbot",
    })
    g.add_edge("clarifier", "chatbot")
    g.add_conditional_edges("clarifier_appel",
                            lambda e: "tools" if appels_en_attente(e) else "chatbot",
                            {"tools": "tools", "chatbot": "chatbot"})
    g.add_conditional_edges("confirmer", apres_confirmation,
                            {"tools": "tools", "chatbot": "chatbot"})
    g.add_edge("reviser", "chatbot")
    g.add_edge("envoyer", "chatbot")
    g.add_edge("valider_plan", "chatbot")
    g.add_edge("approfondir", "chatbot")

    g.add_conditional_edges("coder",
                            lambda e: "reviser" if revision_attendue(e) else "chatbot",
                            {"reviser": "reviser", "chatbot": "chatbot"})

    return g.compile(checkpointer=build_checkpointer())

