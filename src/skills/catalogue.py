"""Le catalogue des skills montré au modèle : une ligne par skill routable,
généré depuis le frontmatter. Les annexes en sont exclues ; la portée (`scope`)
décide de qui voit quoi."""
from __future__ import annotations

from src.skills import skills_pertinentes, skills_routables

_MAX_DESCRIPTION = 160

BUDGET = 5

MAX_ENTREES = 12


def _ligne(description: str) -> str:
    une_ligne = " ".join(description.split())
    if len(une_ligne) <= _MAX_DESCRIPTION:
        return une_ligne
    return une_ligne[:_MAX_DESCRIPTION - 1].rstrip() + "…"


def entrees(scope: str, requete: str = "") -> list[tuple[str, str]]:
    """(nom, description courte) des skills routables pour cette portée."""
    routables = [(n, _ligne(d)) for n, d in skills_routables(scope)]
    if not requete.strip() or len(routables) <= MAX_ENTREES:
        return routables
    retenues = set(skills_pertinentes(requete, scope, BUDGET))
    return [(n, d) for n, d in routables if n in retenues] or routables


def texte(scope: str, requete: str = "") -> str:
    """Le bloc à insérer dans la consigne de `load_skill`."""
    lignes = entrees(scope, requete)
    if not lignes:
        return "  (aucun)"
    return "\n".join(f"  - {nom}: {desc}" for nom, desc in lignes)
