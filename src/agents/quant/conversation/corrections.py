"""Les détections de réponse fautive PROPRES aux paris.

Elles vivaient dans le nœud `chatbot`, c'est-à-dire que le nœud qui pilote
toutes les conversations d'AXON portait des règles sur les bankrolls et les
cotes. Elles suivent ici le mécanisme générique de
`src.orchestrator.modele.corrections`, qui les ramasse par `correcteurs_actifs()` — et
qui tourne sans elles si ce paquet n'est pas installé.
"""
from __future__ import annotations

from src.orchestrator.modele.corrections import Contexte, Verdict, _appels


def clarification_de_perimetre_deja_repondue(response, ctx: Contexte) -> Verdict:
    """Le modèle redemande un périmètre que `betting_recommend` a déjà appliqué.

    En conversation réelle il l'a fait trois fois de suite après avoir reçu un
    scan complet — la boucle du dump, déplacée après le scan au lieu d'avant.
    """
    appels = _appels(response, "ask_clarification")
    if not appels:
        return None

    from src.agents.quant.conversation.evidence import redundant_scope_question

    if not all(redundant_scope_question(ctx.working, tc.get("args", {}).get("questions") or [])
               for tc in appels):
        return None
    return (
        "clarification de périmètre déjà répondue",
        "[SYSTEME] Tu redemandes un périmètre (sport, compétition, "
        "marché, période ou bankroll) que l'utilisateur a déjà fixé et "
        "que betting_recommend a déjà appliqué dans ce tour. La réponse "
        "est dans le champ `rendered` de son résultat : restitue-la "
        "telle quelle, sans poser de question. Si l'utilisateur veut "
        "restreindre, il le dira de lui-même.",
    )


CORRECTEURS = [clarification_de_perimetre_deja_repondue]
