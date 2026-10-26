"""Skills projet — guides markdown chargés à la demande.

Chaque skill déclare qui peut le lire dans son frontmatter :

    scope: [coding, orchestrator]     lisible des deux
    scope: orchestrator               hors code seulement
    (absent)                          coding uniquement — défaut

Une ANNEXE (`annexe: true`) reste chargeable par nom — un skill principal y
renvoie — mais n'apparaît pas au catalogue que voit le modèle : il ne la choisit
jamais seul. `catalogue.py` construit ce catalogue, un skill par ligne.

Les consommateurs passent par ici, jamais par `retriever` directement.
"""
from src.skills.retriever import (
    describe_skills,
    get_skill,
    list_skills,
    scopes_in_use,
    skill_anchors,
    skills_pertinentes,
    skills_routables,
    warmup,
)

__all__ = ["describe_skills", "get_skill", "list_skills", "scopes_in_use",
           "skill_anchors", "skills_pertinentes", "skills_routables", "warmup"]
