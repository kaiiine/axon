"""Tool `load_skill`, fabriqué par contexte — seule la portée sépare les agents."""
from __future__ import annotations

from langchain_core.tools import StructuredTool

from src.skills.catalogue import BUDGET

_TEMPLATE = """\
Loads the guidelines WRITTEN FOR THIS PROJECT about a domain.

Call this FIRST — before any other tool — whenever the request touches one of the
skills below. The check is unconditional; only the loading depends on a match.
Alone in its turn: the action tool comes after you have read the result.

Skills COMPOSE — call this tool once per skill that applies. A stack skill says WHAT
to install and scaffold; a cross-cutting skill says HOW the result must behave or
look ("a site in <framework>, with a great design" → load both).

Available skills:
{catalogue}

Args:
    stack: a skill name from the list above
Returns:
    The full guidelines text for that skill
"""


#: Alias historique — le budget vit maintenant dans `catalogue.BUDGET`, avec la
#: construction du catalogue. Gardé pour les appelants (tests, mesures).
BUDGET_SKILLS = BUDGET


def make_load_skill(scope: str, requete: str = "") -> StructuredTool:
    """Une fabrique et non un singleton : les deux agents tournent dans le même
    processus, un objet partagé montrerait à l'un le catalogue de l'autre.

    `requete` RESTREINT le catalogue à ce qui la concerne. Sans elle — au
    démarrage, quand aucune question n'est encore posée — on montre tout : mieux
    vaut un catalogue large qu'un catalogue deviné.
    """
    from src.skills import get_skill, list_skills
    from src.skills.catalogue import texte as catalogue_texte

    catalogue = catalogue_texte(scope, requete)

    def _run(stack: str) -> str:
        result = get_skill(stack, scope=scope)
        if result and not result.startswith("Skill '"):
            return result
        return f"Skill '{stack}' non disponible ici. Disponibles : {', '.join(list_skills(scope))}"

    return StructuredTool.from_function(
        func=_run, name="load_skill", description=_TEMPLATE.format(catalogue=catalogue)
    )


def anchors_for(scope: str) -> list[str]:
    try:
        from src.skills import skill_anchors
        return skill_anchors(scope)
    except Exception:
        return []
