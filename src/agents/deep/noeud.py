"""Le nœud qui exécute une recherche approfondie.

Le sous-graphe est compilé SANS checkpointer : invoqué depuis un nœud, il hérite
de celui du parent. Ses étapes sont donc checkpointées — une recherche
interrompue reprend là où elle en était, sans refaire les appels déjà faits.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp

from src.orchestrator.commun.note_interne import note

MARQUEUR = "recherche_approfondie_demandee"

# ── Progrès, pour l'UI ────────────────────────────────────────────────────────
# `approfondir` tournait via `.invoke()` sur le sous-graphe : un seul appel
# bloquant, opaque de l'extérieur jusqu'à son retour. Le graphe PRINCIPAL, lui,
# montre chaque outil dès que son appel est vu dans le flux — vécu : « je n'ai
# plus accès aux sites qu'il consulte en temps réel » pour /deep, alors que le
# mécanisme existe déjà côté agent de code (`specialist._notifier`). Même
# forme ici, pour la même raison.
_progress_cb: Optional[Callable[[str, dict], None]] = None


def set_progress_callback(cb: Optional[Callable[[str, dict], None]]) -> None:
    global _progress_cb
    _progress_cb = cb


def _notifier(noeud: str, partiel: dict) -> None:
    """Un événement d'affichage ne doit jamais faire échouer la recherche."""
    if not _progress_cb:
        return
    try:
        _progress_cb(noeud, partiel)
    except Exception:                                        # noqa: BLE001
        pass


def question_a_creuser(message: Any) -> str | None:
    """La question dont ce résultat d'outil demande l'approfondissement."""
    if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
        return None
    try:
        charge = json.loads(message.content)
    except (ValueError, TypeError):
        return None
    if not isinstance(charge, dict) or charge.get("status") != MARQUEUR:
        return None
    question = charge.get("question")
    return question if isinstance(question, str) and question.strip() else None


def approfondir(state: dict) -> dict:
    from src.agents.deep.graphe import construire
    from src.agents.deep.tools import chercher_web, repondre_avec_modele

    question = question_a_creuser(state["messages"][-1]) or ""
    if not question:
        return {"messages": []}

    graphe = construire(repondre_avec_modele(), chercher_web)
    sortie: dict = {}
    try:
        # `stream_mode=["updates", "values"]` plutôt que `.invoke()` : "updates"
        # rend un événement par tâche `Send` — donc un par recherche, à mesure
        # qu'elle finit, MÊME lancées en parallèle (vérifié : trois recherches
        # simultanées donnent trois événements distincts, pas un seul groupé).
        # "values" rend l'état déjà FUSIONNÉ après chaque super-étape — on
        # n'a donc pas à réimplémenter le réducteur `operator.add` de
        # `trouvailles` à la main ; le dernier "values" reçu EST le résultat.
        for mode, evenement in graphe.stream(
            {"question": question, "trouvailles": []},
            stream_mode=["updates", "values"],
        ):
            if mode == "values":
                sortie = evenement
                continue
            for noeud, partiel in evenement.items():
                _notifier(noeud, partiel)
    except GraphBubbleUp:
        # Une interruption n'est pas une erreur : c'est le sous-graphe qui
        # demande. L'attraper la transformerait en « la recherche a échoué ».
        raise
    except Exception as erreur:      # noqa: BLE001 — rapporté, jamais avalé
        return {"messages": [note(
            texte=f"La recherche approfondie a échoué : {type(erreur).__name__}: "
                    f"{erreur}. Dis-le à l'utilisateur sans inventer de résultat.")]}

    rapport = (sortie.get("rapport") or "").strip()
    sujets = [t["sujet"] for t in sortie.get("trouvailles", [])]
    if not rapport:
        return {"messages": [note(
            texte="La recherche approfondie n'a produit aucune synthèse.")]}

    return {"messages": [note(
        texte=f"Résultat de la recherche approfondie sur « {question} » — "
                f"{len(sujets)} recherche(s) sur {sortie.get('tours', 1)} tour(s).\n\n"
                f"{rapport}\n\nRestitue-le à l'utilisateur sans rien y ajouter.")]}
