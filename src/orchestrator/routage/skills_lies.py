"""Les skills dans le routage : `load_skill` est lié à chaque tour, hors classement.

Le groupe d'outils « skills » est une moyenne de tous les skills : il perd face à
tout groupe d'action qui recoupe un skill (`gmail` pour « rédige un mail »). Ici
`load_skill` est ajouté après le choix des groupes, comme `obtenir_outil`, avec le
catalogue des skills routables.

Derrière `settings.skills_toujours_lies` : à False, l'ancien routage.
"""
from __future__ import annotations

#: Le groupe moyenné, retiré du classement quand les skills sont toujours liés.
GROUPE_SKILLS = "skills"


def groupes_neutralises() -> frozenset[str]:
    """Les groupes que le classement ne doit ni indexer ni élire."""
    from src.infra.settings import settings

    return frozenset({GROUPE_SKILLS}) if settings.skills_toujours_lies else frozenset()


def restreindre_les_skills(outils: list, requete: str, portee: str) -> list:
    """Remplace `load_skill` par une version dont le catalogue se limite à la requête
    (49 skills font 2 241 tokens ; le modèle n'en choisissait aucun)."""
    if not requete.strip() or not any(o.name == "load_skill" for o in outils):
        return outils
    try:
        from src.skills.tools import make_load_skill

        etroit = make_load_skill(portee, requete)
    except Exception:                                        # noqa: BLE001
        return outils
    return [etroit if o.name == "load_skill" else o for o in outils]


def lier_load_skill(outils: list, requete: str, portee: str) -> list:
    """`load_skill` en fin de sélection, qu'un groupe l'ait élu ou non.

    Sans skill routable pour cette portée, l'outil n'aurait rien à proposer : on
    le retire plutôt que de lier un catalogue vide. Un échec de construction
    laisse la sélection telle quelle.
    """
    from src.skills import skills_routables

    sans = [o for o in outils if o.name != "load_skill"]
    try:
        if not skills_routables(portee):
            return sans
        from src.skills.tools import make_load_skill

        return sans + [make_load_skill(portee, requete)]
    except Exception:                                        # noqa: BLE001
        return outils


def appliquer_les_skills(outils: list, requete: str, portee: str) -> list:
    """Le point d'entrée du routeur : toujours lié, ou l'ancien comportement."""
    from src.infra.settings import settings

    if settings.skills_toujours_lies:
        return lier_load_skill(outils, requete, portee)
    return restreindre_les_skills(outils, requete, portee)
