"""Rattraper une réponse mal formée en la renvoyant au modèle avec une consigne.

Quatre défauts mesurés à l'écran étaient corrigés dans le nœud `chatbot`, et
chacun y avait sa propre copie manuscrite du MÊME mécanisme :

    if <le modèle a mal fait X>:
        console.print("… — correction…")
        rappel = HumanMessage(content="[SYSTEME] …")
        try:
            response = llm.invoke(working + [response, rappel])
        except Exception:
            pass

Quatre détections différentes, un seul mécanisme — mais écrit quatre fois. Un
correctif apporté à l'une n'atteignait jamais les trois autres : c'est la même
classe de défaut que les deux pipelines de `save_study_file`, qui avaient
divergé en silence jusqu'à ne plus produire la même qualité de fiche.

Ici une détection ne fait que RÉPONDRE À UNE QUESTION — « ce tour est-il
fautif, et que faut-il dire au modèle ? » — et rend soit `None`, soit le
couple (ce qu'on annonce à l'écran, la consigne). Le mécanisme, lui, n'existe
qu'une fois, dans `appliquer`.

Elles s'appliquent EN CHAÎNE, dans l'ordre, chacune examinant la réponse telle
que la précédente l'a laissée — c'est le comportement d'origine, pas un
premier-qui-gagne.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.orchestrator.commun.messages import texte_du_contenu
from src.orchestrator.modele.provider_quirks import _MALFORMED_TOOL_CALL_RE, outil_ecrit_en_json

#: Au-delà de ce volume de texte HORS questions, le modèle a répondu — il ne
#: réclame pas. Voir `demande_de_precision`.
_SUBSTANCE_REPONSE = 240

_DEMANDE_EXPLICITE = re.compile(
    r"(?i)\b(veuillez préciser|merci de préciser|peux-tu préciser|"
    r"il me (?:manque|faut)|precise[rz]|please specify)\b")

#: Les outils dont le flow normal EST « je prépare, tu confirmes » : leur poser
#: une question en texte libre est légitime, on ne corrige pas.
_OUTILS_DE_FLOW = {"slack_send_message", "git_commit"}
_GROUPES_DE_FLOW = {"slack", "git"}


@dataclass
class Contexte:
    """Ce qu'une détection a besoin de savoir du tour en cours."""

    working: list = field(default_factory=list)
    selected_tools: list = field(default_factory=list)
    force_text: bool = False
    plan_mode: bool = False
    groupe_de_tete: str | None = None


#: (ce qu'on annonce à l'écran, la consigne envoyée au modèle) — ou None si le
#: tour n'est pas fautif.
Verdict = tuple[str, str] | None
Correcteur = Callable[[object, Contexte], Verdict]


# ── ce que le texte d'une réponse révèle ───────────────────────────────────────

def demande_de_precision(texte: str) -> bool:
    """Le modèle RÉCLAME-T-IL une information au lieu de répondre ?

    L'ancienne détection déclenchait sur un « ? » N'IMPORTE OÙ dans la réponse.
    Une réponse complète qui se terminait par « Tu veux que je détaille ? » était
    donc traitée comme une question en texte libre : le modèle recevait l'ordre de
    la reposer via `ask_clarification`, et l'utilisateur voyait un questionnaire
    arriver APRÈS sa réponse, sans objet. Chaque réponse contenant une seule
    interrogation coûtait en plus un aller-retour de correction.

    Ce qui distingue les deux cas n'est pas la présence d'une question mais
    l'absence de réponse : on mesure donc ce que le texte dit EN DEHORS de ses
    questions.
    """
    phrases = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", texte or "") if p.strip()]
    questions = [p for p in phrases if p.endswith("?")]
    substance = sum(len(p) for p in phrases if not p.endswith("?"))

    if not questions and not _DEMANDE_EXPLICITE.search(texte or ""):
        return False
    return substance < _SUBSTANCE_REPONSE


def _appels(response, nom: str) -> list:
    return [tc for tc in (getattr(response, "tool_calls", None) or [])
            if tc.get("name") == nom]


def _reponses_de_clarification(working: Iterable) -> dict[str, str]:
    """Les couples question → réponse déjà obtenus via `ask_clarification`."""
    obtenues: dict[str, str] = {}
    for m in working:
        if not (isinstance(m, ToolMessage) and getattr(m, "name", None) == "ask_clarification"):
            continue
        try:
            brut = m.content if isinstance(m.content, str) else json.dumps(m.content)
            for question, reponse in (json.loads(brut).get("answers") or {}).items():
                if question != "_extra":
                    obtenues[question.strip().lower()] = reponse
        except Exception:      # noqa: BLE001 — un résultat illisible n'est pas une réponse
            pass
    return obtenues


def a_deja_des_reponses(working: Iterable) -> bool:
    return bool(_reponses_de_clarification(working))


def garde_actif(selected_tools, groupe_de_tete: str | None, working) -> bool:
    """Le garde-fou « pas de question en texte libre » s'applique-t-il ?

    Mesuré sur 142 requêtes réelles : 33 tours liaient `slack_send_message` ou
    `git_commit`, et 29 n'avaient RIEN à voir avec Slack ni un commit. Vingt
    pour cent des tours perdaient le garde-fou parce qu'un outil était à
    portée, pas parce que le tour le concernait — d'où le rang 1 dans la
    condition, et non la simple liaison.
    """
    flow = (any(getattr(t, "name", None) in _OUTILS_DE_FLOW for t in selected_tools)
            and groupe_de_tete in _GROUPES_DE_FLOW)
    return (not flow) or a_deja_des_reponses(working)


# ── les détections ─────────────────────────────────────────────────────────────

def question_deja_repondue(response, ctx: Contexte) -> Verdict:
    """Le modèle repose une question dont il a déjà la réponse."""
    if ctx.force_text:
        return None
    appels = _appels(response, "ask_clarification")
    if not appels:
        return None

    obtenues = set(_reponses_de_clarification(ctx.working))
    repose = any(
        (q.get("question") if isinstance(q, dict) else str(q) or "").strip().lower() in obtenues
        for tc in appels
        for q in (tc.get("args", {}).get("questions") or [])
    )
    if not repose:
        return None
    return (
        "question déjà répondue reposée",
        "[SYSTEME] Tu viens de reposer une question à laquelle tu as déjà "
        "une réponse dans cette conversation (visible dans un précédent "
        "résultat de ask_clarification). Utilise cette réponse directement, "
        "ne la redemande pas. Continue l'action demandée avec les outils "
        "appropriés.",
    )


def reponse_vide(response, ctx: Contexte) -> Verdict:
    """Le modèle rend un tour sans texte NI appel d'outil — la tâche meurt là.

    Mesuré avec gpt-oss:120b sur Ollama Cloud : après un `git_status`, une
    dizaine de tokens générés, `done_reason: stop`, et un contenu vide (les
    tokens partent dans un canal qu'Ollama ne rend pas). L'utilisateur ne
    voyait que le compte rendu de secours, sans savoir pourquoi ça s'arrêtait.
    """
    if getattr(response, "tool_calls", None):
        return None
    if texte_du_contenu(response.content).strip():
        return None
    return (
        "réponse vide du modèle",
        "[SYSTEME] Ta dernière réponse était vide : ni texte, ni appel d'outil. "
        "Reprends la tâche là où tu en étais. Si une étape reste à faire, "
        "appelle l'outil suivant. Sinon, rédige maintenant la réponse finale "
        "à l'utilisateur à partir des résultats déjà obtenus — et dis "
        "explicitement ce qui manque si une information n'était pas "
        "disponible.",
    )


def appel_ecrit_en_texte(response, ctx: Contexte) -> Verdict:
    """Le modèle a ÉCRIT un appel d'outil au lieu de l'émettre — rien ne s'exécute."""
    if ctx.force_text or getattr(response, "tool_calls", None):
        return None

    texte = texte_du_contenu(response.content)
    en_json = outil_ecrit_en_json(texte, ctx.selected_tools)
    if not (_MALFORMED_TOOL_CALL_RE.search(texte) or en_json):
        return None
    return (
        f"appel d'outil écrit en texte{f' ({en_json})' if en_json else ''}",
        "[SYSTEME] Ta dernière réponse contenait un faux appel d'outil "
        "écrit en texte brut au lieu d'un vrai appel : une balise "
        "'xxx:tool_call', ou les arguments rendus comme objet JSON. "
        "Ni l'un ni l'autre n'exécute quoi que ce soit. "
        "Refais le même appel en utilisant le vrai mécanisme de function "
        "calling à ta disposition, pas du texte.",
    )


def question_en_texte_libre(response, ctx: Contexte) -> Verdict:
    """Le modèle pose une question en prose au lieu d'ouvrir un questionnaire."""
    if ctx.force_text or ctx.plan_mode:
        return None
    if not garde_actif(ctx.selected_tools, ctx.groupe_de_tete, ctx.working):
        return None
    if getattr(response, "tool_calls", None):
        return None
    if not demande_de_precision(texte_du_contenu(response.content).strip()):
        return None

    deja = _reponses_de_clarification(ctx.working)
    rappel_des_reponses = ""
    if deja:
        paires = [f"- {q} -> {r}" for q, r in deja.items() if r]
        if paires:
            rappel_des_reponses = (
                "\nRéponses DÉJÀ données par l'utilisateur (utilise-les, ne les "
                "redemande pas) :\n" + "\n".join(paires)
            )
    return (
        "question en texte libre détectée",
        "[SYSTEME] Tu viens de répondre par une question en texte libre — "
        "c'est interdit. Si l'info est déjà présente ailleurs dans cette "
        "conversation (y compris une réponse précédente à ask_clarification), "
        "utilise-la directement sans la redemander. Sinon, repose la question "
        "immédiatement via ask_clarification(questions=[...])."
        + rappel_des_reponses,
    )


#: Les détections valables quel que soit le domaine.
CORRECTEURS_DE_BASE: list[Correcteur] = [
    reponse_vide,
    question_deja_repondue,
    appel_ecrit_en_texte,
    question_en_texte_libre,
]


def correcteurs_actifs() -> list[Correcteur]:
    """Les détections de base, plus celles des domaines installés.

    `quant` en apporte une (une clarification de périmètre de pari déjà
    tranchée). L'import est tolérant : si le paquet n'est pas là, AXON tourne
    sans, et le cœur n'a aucune raison de le savoir.
    """
    correcteurs = list(CORRECTEURS_DE_BASE)
    try:
        from src.agents.quant.conversation.corrections import CORRECTEURS as _quant
    except ImportError:
        pass
    else:
        correcteurs += list(_quant)
    return correcteurs


# ── le mécanisme, une seule fois ───────────────────────────────────────────────

def appliquer(response, ctx: Contexte, invoquer, notifier=None,
              correcteurs: list[Correcteur] | None = None):
    """Rejoue la réponse auprès du modèle tant qu'une détection la trouve fautive.

    `invoquer(messages)` appelle le modèle ; `notifier(texte)` l'annonce à
    l'écran. Une correction qui échoue laisse la réponse d'origine : mieux vaut
    une réponse imparfaite qu'un tour perdu.
    """
    for detecter in (correcteurs if correcteurs is not None else correcteurs_actifs()):
        verdict = detecter(response, ctx)
        if verdict is None:
            continue
        annonce, consigne = verdict
        if notifier:
            notifier(f"{annonce} — correction…")
        # Un message assistant vide est refusé par certains fournisseurs
        # (Mistral) : on ne le renvoie pas, la consigne suffit.
        fautive = ([response] if getattr(response, "tool_calls", None)
                   or texte_du_contenu(response.content).strip() else [])
        try:
            response = invoquer(ctx.working + fautive + [HumanMessage(content=consigne)])
        except Exception:      # noqa: BLE001 — on garde la réponse d'origine
            pass
    return response


def garde_du_domaine(response, working, notifier=None):
    """Remplace une réponse qu'un domaine REFUSE de laisser passer.

    Autre mécanisme que les correcteurs : on ne redemande rien au modèle, on
    substitue. `quant` s'en sert pour qu'un conseil de pari non sourcé ne
    parvienne jamais à l'écran — un garde sans opinion, qui vérifie la présence
    de la preuve et pas la qualité du raisonnement.

    Sans le paquet `quant`, il n'y a rien à faire garder : la réponse passe.
    """
    if getattr(response, "tool_calls", None):
        return response
    try:
        from src.agents.quant.conversation.evidence import (
            extract_evidence,
            has_structured_output,
        )
        from src.agents.quant.conversation.guard import concerne_les_paris, enforce
    except ImportError:
        return response

    texte = texte_du_contenu(response.content)
    # Le garde paris ne s'applique qu'à un tour de paris. Sans cette borne, il
    # remplaçait une réponse météo (« 17,6 °C ») par « DATA_UNAVAILABLE », prenant
    # les températures pour des faits de pari non sourcés.
    if not concerne_les_paris(texte, working):
        return response

    verdict = enforce(
        texte,
        extract_evidence(working),
        has_structured_output=has_structured_output(working),
    )
    if not verdict.blocked:
        return response
    if notifier:
        notifier(f"⛔ réponse de pari non sourcée — remplacée ({verdict.reason})")
    return AIMessage(content=verdict.replacement)
