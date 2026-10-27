"""Outils `etude_*` pour ce qui se passe PENDANT la préparation d'un suivi :
exercices (cycle de vie complet — tentatives, indices, correction), tâches
légères (juste à faire/fait), et l'historique des points d'avancement.
"""
from __future__ import annotations

from langchain_core.tools import tool

from ._aide import STATUTS_EXERCICE


# ── exercices ────────────────────────────────────────────────────────────

@tool("etude_ajouter_exercice")
def etude_ajouter_exercice(suivi_id: str, titre: str, description: str = "", echeance_id: str | None = None) -> str:
    """
    Ajoute un exercice à préparer dans un suivi, éventuellement rattaché à
    une échéance précise.

    Mots-clés : exercice, TD, TP, à faire, préparer.

    **Args:**
        - `suivi_id` (str)
        - `titre`, `description` (str)
        - `echeance_id` (str, optionnel)

    **Returns:**
        - Confirmation avec l'identifiant de l'exercice.
    """
    from .store import ajouter_exercice

    exercice = ajouter_exercice(suivi_id, titre, description, echeance_id=echeance_id)
    if exercice is None:
        return f"Suivi introuvable : {suivi_id}"
    return f"Exercice ajouté : **{titre}**.\nID : `{exercice['id']}`"


@tool("etude_maj_exercice")
def etude_maj_exercice(
    suivi_id: str, exercice_id: str, statut: str | None = None,
    tentative: str | None = None, difficulte: str | None = None, indice: bool = False,
) -> str:
    """
    Met à jour un exercice : statut, et/ou journalise une tentative ou une
    difficulté. Couvre « j'ai terminé cet exercice » (statut "termine"),
    « je bloque » (difficulte), un essai raté (tentative), ou demande un
    indice (indice=True) — **donne UN indice à la fois, jamais la solution
    complète d'un coup**, et incrémente le compteur plutôt que de la révéler.

    **Un exercice "termine" NE PROUVE PAS la maîtrise de la notion** — ne
    déduis jamais une maîtrise depuis un simple changement de statut ; une
    vraie maîtrise déclarée est un point d'avancement
    (`etude_point_avancement`), pas une inférence automatique.

    Mots-clés : terminé, fini, bloqué, raté, tentative, difficulté, indice,
    corriger, reprendre, à revoir.

    **Args:**
        - `suivi_id`, `exercice_id` (str)
        - `statut` (str, optionnel) : "a_faire", "en_cours", "bloque",
          "termine", "a_revoir"
        - `tentative`, `difficulte` (str, optionnels) : note libre
        - `indice` (bool) : incrémente le compteur d'indices donnés

    **Returns:**
        - Confirmation, ou erreur si le suivi/exercice est introuvable.
    """
    from .store import maj_exercice

    if statut is not None and statut not in STATUTS_EXERCICE:
        return f"Statut inconnu : {statut}. Attendu : {', '.join(STATUTS_EXERCICE)}."
    exercice = maj_exercice(suivi_id, exercice_id, statut, tentative, difficulte, indice)
    if exercice is None:
        return f"Suivi ou exercice introuvable ({suivi_id} / {exercice_id})."
    extra = f" · indice n°{exercice['indices_donnes']}" if indice else ""
    return f"Exercice **{exercice['titre']}** mis à jour (statut : {exercice['statut']}){extra}."


# ── tâches ───────────────────────────────────────────────────────────────

@tool("etude_ajouter_tache")
def etude_ajouter_tache(suivi_id: str, titre: str, echeance_id: str | None = None) -> str:
    """
    Ajoute une tâche légère (objectif) à un suivi — distincte d'un exercice :
    pas de tentatives/indices/correction, juste à faire ou fait.

    **Args:**
        - `suivi_id`, `titre` (str)
        - `echeance_id` (str, optionnel)

    **Returns:**
        - Confirmation avec l'identifiant de la tâche.
    """
    from .store import ajouter_tache

    tache = ajouter_tache(suivi_id, titre, echeance_id)
    if tache is None:
        return f"Suivi introuvable : {suivi_id}"
    return f"Tâche ajoutée : **{titre}**.\nID : `{tache['id']}`"


@tool("etude_maj_tache")
def etude_maj_tache(suivi_id: str, tache_id: str, statut: str) -> str:
    """
    Marque une tâche à faire ou faite.

    **Args:**
        - `suivi_id`, `tache_id` (str)
        - `statut` (str) : "a_faire" ou "fait"

    **Returns:**
        - Confirmation, ou erreur si introuvable.
    """
    from .store import maj_tache

    if statut not in ("a_faire", "fait"):
        return 'Statut inconnu. Attendu : "a_faire" ou "fait".'
    tache = maj_tache(suivi_id, tache_id, statut)
    if tache is None:
        return f"Suivi ou tâche introuvable ({suivi_id} / {tache_id})."
    return f"Tâche **{tache['titre']}** → {statut}."


# ── historique / points d'avancement ──────────────────────────────────

@tool("etude_point_avancement")
def etude_point_avancement(suivi_id: str, texte: str, echeance_id: str | None = None) -> str:
    """
    Ajoute une entrée à l'historique d'un suivi — ce qui est fait, ce qui
    reste, une difficulté générale, le résultat d'un « faisons le point ».
    Précise `echeance_id` si le point vise une échéance en particulier
    plutôt que le suivi entier.

    Avant d'appeler ce tool pour « faisons le point sur mon partiel »,
    relis `etude_detail_suivi` pour t'appuyer sur ce qui est RÉELLEMENT
    enregistré (exercices faits/bloqués, temps restant) plutôt que de
    deviner — et distingue dans ta réponse ce que l'utilisateur vient de
    déclarer de ce que tu proposes comme prochaine étape : ne logue dans
    l'historique que ce qui est acté, pas une simple suggestion.

    Mots-clés : point d'avancement, historique, où j'en suis, bilan, notion,
    je bloque, je comprends, faisons le point.

    **Args:**
        - `suivi_id`, `texte` (str)
        - `echeance_id` (str, optionnel)

    **Returns:**
        - Confirmation, ou erreur si le suivi est introuvable.
    """
    from .store import ajouter_point_avancement

    point = ajouter_point_avancement(suivi_id, texte, origine="utilisateur", echeance_id=echeance_id)
    if point is None:
        return f"Suivi introuvable : {suivi_id}"
    return "Point d’avancement enregistré."
