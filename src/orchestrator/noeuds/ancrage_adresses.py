"""Un destinataire n'est jamais deviné : son adresse vient de la conversation.

Un modèle à qui il manque l'adresse d'un manager en écrit une plausible
(`manager@entreprise.com`) plutôt que de la demander, et le brouillon qui en
résulte a l'air parfait. Aucune validation de forme ne l'attrape : seule la
provenance le fait. L'adresse doit figurer dans un message de l'utilisateur, un
résultat d'outil (`gmail_search`…) ou une réponse à `ask_clarification`.
"""
from __future__ import annotations

import re

from langchain_core.messages import ToolMessage

#: Les outils dont l'argument `to` désigne un destinataire à ancrer.
OUTILS_A_DESTINATAIRE = frozenset({"gmail_send_email"})

_ADRESSE = re.compile(r"[^@\s,;<>()\[\]\"']+@[^@\s,;<>()\[\]\"']+\.[^@\s,;<>()\[\]\"']+")


def _texte(message) -> str:
    contenu = getattr(message, "content", "")
    if isinstance(contenu, str):
        return contenu
    return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in contenu)


def adresses_connues(messages: list) -> set[str]:
    """Les adresses que la conversation a rendues disponibles."""
    return {a.lower().rstrip(".") for m in messages if not getattr(m, "tool_calls", None)
            for a in _ADRESSE.findall(_texte(m))}


def destinataires(args: dict) -> list[str]:
    champs = " ".join(str(args.get(c) or "") for c in ("to", "cc", "bcc"))
    return [a.lower().rstrip(".") for a in _ADRESSE.findall(champs)]


def refus_adresses_inventees(tool_calls: list, messages: list) -> list[ToolMessage]:
    connues = adresses_connues(messages)
    refus = []
    for tc in tool_calls:
        if tc["name"] not in OUTILS_A_DESTINATAIRE:
            continue
        inconnues = [a for a in destinataires(tc.get("args") or {}) if a not in connues]
        if inconnues:
            refus.append(ToolMessage(
                content=(f"Brouillon refusé : {', '.join(inconnues)} n'a été donnée ni par "
                         f"l'utilisateur ni par un outil. Ne la devine pas : demande-la avec "
                         f"ask_clarification (ou cherche-la avec gmail_search), puis rappelle "
                         f"{tc['name']}."),
                tool_call_id=tc["id"], name=tc["name"], status="error"))
    return refus
