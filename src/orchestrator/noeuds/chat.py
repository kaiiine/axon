"""Le nœud `chatbot` : choisir les outils du tour, appeler le modèle, rattraper.

Les neuf autres nœuds du graphe vivent chacun dans leur fichier — `coder` dans
`agents/coding/noeud.py`, `approfondir` dans `agents/deep/noeud.py`, `confirmer`,
`envoyer`, `reviser`, `valider`, `clarifier`. Celui-ci était le seul resté inline
dans `graph.py`, où ses ~365 lignes noyaient les 54 lignes de câblage du graphe.

Ce qu'il fait, dans l'ordre : élire les outils pour la requête, appliquer le mode
plan, rouvrir le catalogue sur demande, plafonner les tours, compresser le
contexte au besoin, appeler le modèle avec reprise sur erreur, puis passer la
réponse aux rattrapages de `corrections.py`.
"""
from __future__ import annotations

from datetime import datetime
from typing import List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from rich.console import Console as RichConsole

from src.orchestrator.modele.context import (
    _cap_tool_messages,
    _compress_context,
    _estimate_tokens,
    _should_compress,
    _SUMMARY_MARKER,
)
from src.orchestrator.modele.corrections import (
    Contexte as ContexteCorrection,
    appliquer as appliquer_les_corrections,
    garde_du_domaine as _garde_du_domaine,
)
from src.orchestrator.commun.messages import texte_du_contenu
from src.orchestrator.modele.provider_quirks import _sanitize_messages_for_mistral
from src.orchestrator.modele.invocation import invoke_with_recovery

from src.llm.models import (
    make_llm,
    make_llm_gemini,
    make_llm_groq,
    make_llm_mistral,
    make_llm_ollama_cloud,
    make_llm_nvidia,
    make_orchestrator_llm_with_key,
)
from src.llm.prompts import build_system_prompt
from src.orchestrator.routage.registry import build_all_tools
from src.orchestrator.state import GlobalState
from src.orchestrator.routage.catalogue import (
    indexer as _indexer, menu as _menu, obtenir_outil, ouverts as _ouverts,
    signaler_delegation as _signaler_delegation, _EXPLORATION,
    outil as _outil_du_catalogue, serveurs_actifs as _serveurs_actifs,
)
from src.orchestrator.routage.ellipse import est_une_ellipse
from src.orchestrator.commun.note_interne import est_interne
from src.orchestrator.routage.tool_retriever import ToolRetriever

from src.utils.write_file import write_logs

console = RichConsole()


_MAX_TOOL_ROUNDS = 12


# `_demande_de_precision` est désormais importé de `corrections.py`, avec les
# trois détections qui s'en servent.

# ── Compile callback ───────────────────────────────────────────────────────────
_compile_callback = None
_compressed_this_turn: bool = False


def set_compile_callback(fn) -> None:
    global _compile_callback, _compressed_this_turn
    _compile_callback = fn
    _compressed_this_turn = False  # reset at start of each user turn


# ── Language preference ────────────────────────────────────────────────────────
_lang_pref: str = "fr"


def set_lang_pref(lang: str) -> None:
    global _lang_pref
    _lang_pref = lang


def get_lang_pref() -> str:
    return _lang_pref


# ── Last selected tools (for /debug) ──────────────────────────────────────────
_last_selected_tools: list[str] = []


def get_last_selected_tools() -> list[str]:
    return _last_selected_tools


def _on_compress() -> None:
    if _compile_callback:
        _compile_callback()


# ── Tool-round counter ────────────────────────────────────────────────────────


def _consecutive_tool_rounds(messages: List) -> int:
    """Count total AI→Tool rounds since the last HumanMessage (not just consecutive).
    This catches loops where the LLM interleaves text between tool calls to reset the counter."""
    rounds = 0
    for m in reversed(messages):
        if isinstance(m, HumanMessage):
            break
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            rounds += 1
    return rounds




# ── Orchestrator ───────────────────────────────────────────────────────────────

from src.infra.checkpoint import build_checkpointer
from src.llm.models import (
    make_llm,
    make_llm_gemini,
    make_llm_groq,
    make_llm_mistral,
    make_llm_ollama_cloud,
    make_llm_nvidia,
    make_orchestrator_llm_with_key,
)
from src.llm.prompts import build_system_prompt
from src.orchestrator.routage.registry import build_all_tools
from src.orchestrator.state import GlobalState
from src.orchestrator.routage.catalogue import (
    indexer as _indexer, menu as _menu, obtenir_outil, ouverts as _ouverts,
    signaler_delegation as _signaler_delegation, _EXPLORATION,
    outil as _outil_du_catalogue, serveurs_actifs as _serveurs_actifs,
)
from src.orchestrator.routage.ellipse import est_une_ellipse
from src.orchestrator.commun.note_interne import est_interne
from src.orchestrator.routage.tool_retriever import ToolRetriever


def _ensure_system_prompt(
    messages: List, selected_tools: List, today: str, plan_mode: bool = False,
    catalogue: str = "",
) -> List:
    import os

    user_name = os.getenv("USER_NAME", "l'utilisateur")
    tool_names = [t.name for t in selected_tools]
    system_msg = SystemMessage(
        content=build_system_prompt(
            tool_names, today, user_name, plan_mode=plan_mode, lang=_lang_pref,
            catalogue=catalogue,
        )
    )
    if not messages:
        return [system_msg]
    first = messages[0]
    role0 = (
        first.get("type") if isinstance(first, dict) else getattr(first, "type", None)
    )
    if role0 == "system":
        return [system_msg] + messages[1:]
    return [system_msg] + messages


def _panneau_debug(selected_tools: list, working: list) -> None:
    """Ce qui part RÉELLEMENT au modèle, imprimé au moment où ça part.

    L'affichage vivait dans `streaming.py`, appelé AVANT le tour : il montrait
    donc la sélection du tour précédent, et un prompt reconstruit depuis la liste
    complète des outils au lieu du prompt envoyé. Vécu sur « schématise un RAG en
    prod » : le panneau listait shell, cron, blender et playwright — les outils
    d'une requête d'avant — sans `mermaid_diagram`, pourtant le seul appelé.
    """
    from rich.box import SIMPLE_HEAD
    from rich.panel import Panel

    from src.ui.commands import debug_state

    if not debug_state.get("enabled"):
        return
    lignes = [f"[dim]tools sélectionnés :[/dim] {', '.join(t.name for t in selected_tools)}"]
    for message in working:
        role = getattr(message, "type", "?")
        contenu = str(getattr(message, "content", ""))
        lignes.append(f"[dim]{role}:[/dim] {contenu[:300]}{'...' if len(contenu) > 300 else ''}")
    console.print(Panel("\n\n".join(lignes), box=SIMPLE_HEAD,
                        border_style="dim", title="prompt"))


def _restreindre_les_skills(outils: list, requete: str, portee: str) -> list:
    """Remplace `load_skill` par une version qui ne montre que ce qui concerne
    la requête.

    Son catalogue est DANS sa description : 49 skills, 2 241 tokens, à chaque
    tour où l'outil est lié. C'est l'inverse de ce que fait le routage pour les
    outils — et devant une liste pareille, le modèle n'en choisissait aucune.

    Mesuré sur « fais-moi un site vitrine en Next.js » : 2 241 → 488 tokens, et
    `nextjs` entre dans les cinq montrées, là où le classement dense seul le
    plaçait cinquième derrière `fiche`, `exo` et `browser-driving`.

    Un échec de restriction rend la liste entière : perdre des tokens vaut mieux
    que cacher la skill qu'il fallait.
    """
    if not requete.strip() or not any(o.name == "load_skill" for o in outils):
        return outils
    try:
        from src.skills.tools import make_load_skill

        etroit = make_load_skill(portee, requete)
    except Exception:                                        # noqa: BLE001
        return outils
    return [etroit if o.name == "load_skill" else o for o in outils]


def _chat_node_factory():
    from src.llm.backends import fabriques as _fabriques

    _factories = _fabriques()
    tools = build_all_tools()
    retriever = ToolRetriever(tools)


    from src.mcp_client.runtime import mcp_runtime

    _mcp = mcp_runtime()
    tools = tools + _mcp.tools + [obtenir_outil]

    def chatbot(state: GlobalState):
        from src.infra.settings import settings
        from src.ui.plan_mode import BLOCKED_TOOLS
        from src.ui.plan_mode import is_active as _is_plan_mode

        global _compressed_this_turn
        last = state["messages"][-1] if state["messages"] else None
        if isinstance(last, HumanMessage) and not est_interne(last):
            _compressed_this_turn = False

        try:
            from src.llm.key_pool import restore_preferred_backend as _restore
            _restored = _restore(settings)
            if _restored:
                console.print(f"[dim]  ↩  retour au provider préféré : {_restored}[/dim]")
        except Exception:
            pass

        backend = settings.llm_backend
        factory = _factories.get(backend, make_llm_ollama_cloud)

        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        last_message = state["messages"][-1]

        if last_human:
            query = texte_du_contenu(last_human.content)
            if est_une_ellipse(query):
                human_msgs = [
                    texte_du_contenu(m.content)
                    for m in state["messages"]
                    if isinstance(m, HumanMessage)
                ]
                query = " ".join(human_msgs[-3:])
        else:
            query = (
                texte_du_contenu(last_message.content)
                if hasattr(last_message, "content")
                else str(last_message)
            )
        selected_tools = retriever.get(query) + _mcp.select(
            query, actifs=_serveurs_actifs(state["messages"]))
        selected_tools = _restreindre_les_skills(selected_tools, query, "orchestrator")

        global _last_selected_tools
        _last_selected_tools = [t.name for t in selected_tools]

        # Plan mode — force-include all read-only tools, strip writes
        plan_mode = _is_plan_mode()
        if plan_mode:
            from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

            _read_groups = ("filesystem", "search", "news", "git", "drive", "time")
            _tools_by_name = {t.name: t for t in tools}
            _selected_names = {t.name for t in selected_tools}
            for _g in _read_groups:
                for _tname in TOOL_GROUPS[_g].tools:
                    if _tname not in _selected_names and _tname in _tools_by_name:
                        selected_tools.append(_tools_by_name[_tname])
            selected_tools = [t for t in selected_tools if t.name not in BLOCKED_TOOLS]

        _indexer(tools + _mcp.tools)
        
        _peut_deleguer = any(t.name == "run_coding_agent" for t in selected_tools)
        _signaler_delegation(_peut_deleguer)
        _interdits = set(BLOCKED_TOOLS) if plan_mode else set()
        if _peut_deleguer:
            _interdits |= _EXPLORATION
        _noms = {t.name for t in selected_tools}
        for _nom in _ouverts(state["messages"]):
            if _nom in _noms or _nom in _interdits:
                continue
            _reclame = _outil_du_catalogue(_nom)
            if _reclame is not None:
                selected_tools.append(_reclame)
                _noms.add(_nom)
                # Visible : c'est ce taux qui dira jusqu'où la sélection peut
                # être resserrée. Sans trace, l'arbitrage se referait au doigt.
                console.print(f"[dim]  +  catalogue → {_nom}[/dim]")
        selected_tools.append(obtenir_outil)
        catalogue = _menu(_interdits)

        # Tool-round cap — force text response after _MAX_TOOL_ROUNDS consecutive rounds
        force_text = _consecutive_tool_rounds(state["messages"]) >= _MAX_TOOL_ROUNDS
        if force_text:
            console.print(
                f"[dim]  ↩  {_MAX_TOOL_ROUNDS} rounds atteints — synthèse forcée[/dim]"
            )
            llm_with_tools = factory()
            catalogue = ""
        else:
            llm_with_tools = factory().bind_tools(selected_tools)

        messages = state["messages"]
        today = datetime.now().strftime("%Y-%m-%d")
        messages = _ensure_system_prompt(
            messages, selected_tools, today, plan_mode=plan_mode,
            catalogue=catalogue,
        )

        # Proactive compression before calling the LLM (once per user turn max)
        working = messages
        _state_removals: list = []  # original msgs replaced by summary → RemoveMessage
        _summary_msg = None  # compressed SystemMessage to persist

        if _should_compress(working, backend) and not _compressed_this_turn:
            _compressed_this_turn = True
            console.print("[dim]  ↩  contexte chargé — compression proactive…[/dim]")
            _on_compress()
            plain_llm = factory()
            working = _cap_tool_messages(working)
            working, _state_removals = _compress_context(working, plain_llm, backend)
            before_tokens = _estimate_tokens(messages)
            after_tokens = _estimate_tokens(working)
            freed = before_tokens - after_tokens
            console.print(
                f"[dim]  ↩  compression: -{freed:,} tokens estimés "
                f"({before_tokens:,} → {after_tokens:,})[/dim]"
            )
            # Find compressed summary SystemMessage
            _summary_msg = next(
                (
                    m
                    for m in working
                    if isinstance(m, SystemMessage)
                    and _SUMMARY_MARKER in str(m.content)
                ),
                None,
            )

        if backend == "mistral":
            working = _sanitize_messages_for_mistral(working)

        def _notifier(msg: str) -> None:
            console.print(f"[dim]  ↩  {msg}[/dim]")

        def _compresser_une_fois() -> None:
            global _compressed_this_turn
            if not _compressed_this_turn:
                _compressed_this_turn = True
                _on_compress()

        _panneau_debug(selected_tools, working)

        _issue = invoke_with_recovery(
            llm_with_tools, working,
            backend=backend, factory=factory, selected_tools=selected_tools,
            force_text=force_text, on_compress=_compresser_une_fois, notify=_notifier,
        )
        response = _issue.response
        working = _issue.working
        _state_removals.extend(r for r in _issue.removals if r not in _state_removals)
        _summary_msg = _issue.summary or _summary_msg


        # Quatre détections, un seul mécanisme — voir `corrections.py`. Elles
        # s'appliquent en chaîne, chacune examinant la réponse telle que la
        # précédente l'a laissée.
        response = appliquer_les_corrections(
            response,
            ContexteCorrection(
                working=working,
                selected_tools=selected_tools,
                force_text=force_text,
                plan_mode=plan_mode,
                groupe_de_tete=retriever.groupe_de_tete,
            ),
            invoquer=llm_with_tools.invoke,
            notifier=_notifier,
        )

        response = _garde_du_domaine(response, working, _notifier)

 
        from langchain_core.messages import RemoveMessage

        result: list = []
        if _state_removals:
            result += [
                RemoveMessage(id=m.id)
                for m in _state_removals
                if getattr(m, "id", None)
            ]
            if _summary_msg:
                result.append(_summary_msg)
        result.append(response)

        #TODO: Introduire les logs pour les tools, pour entrainer un modele dessus
        
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )

        write_logs(response, last_human, selected_tools, state["messages"])
        

        return {"messages": result}

    return chatbot, tools
