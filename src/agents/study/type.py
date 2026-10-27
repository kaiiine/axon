"""Study type.

`Suivi` est la racine, pas `Echeance` : un suivi peut représenter une matière,
une préparation de partiel, un projet, ou un travail ponctuel sans date — deux
PDF qu'on veut juste exploiter ne doivent jamais forcer la création d'un
« contrôle ». Une échéance appartient à un suivi (zéro, une ou plusieurs) et
peut cibler un sous-ensemble de ses ressources.

Les ressources vivent dans leur PROPRE collection au niveau du store (voir
`store.py`), pas imbriquées dans un suivi : la même ressource (un dépôt Git,
un PDF de cours) doit pouvoir être partagée par plusieurs suivis sans copie
divergente. Un `Suivi` ne garde que des `ids`.
"""
from __future__ import annotations
from typing import Literal, TypedDict

# ── ressources ───────────────────────────────────────────────────────────

TypeRessource = Literal["document", "dossier", "depot_git", "lien"]
#: Distinction centrale (§2) : un fichier qu'Axon a COPIÉ et garde, un chemin
#: EXTERNE juste référencé (le fichier original reste sous la responsabilité
#: de l'utilisateur, un retrait d'association ne le touche jamais), ou une
#: source DISTANTE (dépôt Git hébergé, lien).
Provenance = Literal["copie", "chemin_externe", "distant"]


class Ressource(TypedDict):
    id: str
    type: TypeRessource
    nom: str
    provenance: Provenance
    #: Chemin local (copie/chemin_externe/dossier/dépôt local) ou URL
    #: (distant/lien).
    chemin: str
    #: Pour détecter un changement de SOURCE sur un fichier/dossier — pas une
    #: preuve cryptographique, un signal suffisant pour prévenir plutôt que
    #: pour certifier.
    taille: int | None
    modifie_le: str | None
    #: Pour un dépôt Git : branche/commit au moment de la dernière analyse.
    branche: str | None
    commit: str | None
    #: False si la ressource est devenue injoignable (fichier déplacé, dépôt
    #: inaccessible) — l'entrée reste, voir `message_erreur`, jamais purgée
    #: silencieusement.
    accessible: bool
    message_erreur: str | None
    created_at: str
    updated_at: str


# ── exercices, tâches, historique ──────────────────────────────────────

StatutExercice = Literal["a_faire", "en_cours", "bloque", "termine", "a_revoir"]
StatutTache = Literal["a_faire", "fait"]
#: §9 : distingue ce que l'utilisateur a déclaré, ce qu'un outil a observé
#: (ex. lecture d'un dépôt), et ce que l'agent propose sans que ce soit acté.
OrigineHistorique = Literal["utilisateur", "outil", "agent"]


class Tentative(TypedDict):
    date: str
    texte: str


class Exercice(TypedDict):
    id: str
    titre: str
    description: str
    statut: StatutExercice
    #: Historique, pas une valeur unique : plusieurs essais racontent une
    #: progression qu'une seule note effacerait.
    tentatives: list[Tentative]
    difficultes: list[Tentative]
    #: Compteur d'indices déjà donnés — jamais la solution complète d'un
    #: coup (§8).
    indices_donnes: int
    #: Rattachements optionnels, sans duplication : d'où vient l'exercice
    #: (quelle ressource l'a généré) et pour quelle échéance il compte.
    ressource_id: str | None
    echeance_id: str | None
    created_at: str
    updated_at: str


class Tache(TypedDict):
    """Objectif léger (§1 « objectifs et tâches ») — distinct d'un `Exercice`,
    qui porte tout un cycle de vie (tentatives, indices, correction)."""
    id: str
    titre: str
    statut: StatutTache
    echeance_id: str | None
    created_at: str
    updated_at: str


class PointAvancement(TypedDict):
    date: str
    texte: str
    origine: OrigineHistorique
    #: Point rattaché à une échéance précise, ou None = le suivi entier —
    #: nécessaire pour que « je bloque sur ce chapitre » (général) et
    #: « fais le point sur mon partiel » (une échéance) visent la bonne cible.
    echeance_id: str | None


# ── vérification de projet (§11) ──────────────────────────────────────
#
# Ce store ne lit ni n'inspecte rien lui-même (filesystem, Git) — ça reste le
# travail des outils existants (`local_list_directory`, `local_grep`,
# `git_status`, `git_log`...), que l'agent appelle lui-même avant de consigner
# sa conclusion ici. Ce qui est gardé, c'est le compte rendu, pas la méthode.

class Verification(TypedDict):
    id: str
    date: str
    #: Ids des ressources effectivement inspectées pour produire ce compte
    #: rendu — jamais une liste devinée.
    ressources_inspectees: list[str]
    elements_presents: list[str]
    exigences_couvertes: list[str]
    elements_manquants: list[str]
    #: Ce qui n'a pas pu être vérifié (accès refusé, dépôt distant non
    #: cloné...) — distinct d'un élément manquant : on ne SAIT pas.
    points_non_verifiables: list[str]
    #: Chemins, commits, extraits — ce sur quoi s'appuie chaque constat.
    preuves: list[str]
    texte: str


# ── rappels ──────────────────────────────────────────────────────────────

#: §10 : un rappel de DATE (échéance qui approche) et une invitation à faire
#: un POINT D'AVANCEMENT (récurrent, pas lié à une date précise) sont deux
#: choses différentes — mêmes mécanismes cron en dessous, sémantique distincte.
TypeRappel = Literal["echeance", "point_avancement"]


class Rappel(TypedDict):
    #: ID de la tâche dans `src/agents/cron/store.py` — l'exécution réelle
    #: vit là-bas, ce store ne garde que la référence pour reporter/désactiver.
    cron_id: str
    type: TypeRappel
    quand: str
    echeance_id: str | None
    #: Nombre de jours avant l'échéance (rappel "echeance") — nécessaire pour
    #: reprogrammer automatiquement un rappel quand l'échéance est reportée,
    #: sans quoi la nouvelle date à viser ne serait plus calculable.
    offset_jours: int | None
    #: Pour un rappel récurrent de point d'avancement (pas de notion
    #: d'« offset avant une date » dans ce cas).
    frequence_jours: int | None


# ── résultats générés (fiches, exercices HTML) ────────────────────────

class Resultat(TypedDict):
    id: str
    type: Literal["fiche", "exo"]
    #: Nom de fichier dans ~/Documents/axon_fiches/ — identifiant stable
    #: dans ce dossier, pas de collection séparée pour le contenu lui-même.
    fichier: str
    #: Sources RÉELLEMENT utilisées, jamais devinées (§6) — distinct de ce
    #: qui a été demandé si une ressource n'a pas pu être lue.
    ressources_utilisees: list[str]
    ressources_manquantes: list[str]
    #: None = travail rapide, pas encore rattaché à un suivi (§3) — un
    #: résultat vit dans sa PROPRE collection au niveau du store, pas imbriqué
    #: dans un suivi, précisément pour pouvoir exister sans lui puis s'y
    #: rattacher après coup sans déplacer de données.
    suivi_id: str | None
    echeance_id: str | None
    parametres: dict
    created_at: str


# ── générations en cours (fiche/exo) ──────────────────────────────────
#
# Collection À PART, même raison que `Resultat` : une génération de travail
# rapide (§3) existe avant tout suivi (`suivi_id: None`). Suivie ici plutôt
# que dans une simple variable en mémoire du processus CLI, précisément pour
# que « changer d'onglet ou se reconnecter retrouve l'état réel » (§ lot 3) —
# une variable en mémoire ne survivrait ni à une reconnexion de l'île, ni à
# un redémarrage du CLI.

StatutGeneration = Literal["en_cours", "terminee", "echouee"]


class GenerationTache(TypedDict):
    id: str
    type: Literal["fiche", "exo"]
    #: None = travail rapide, pas de suivi associé.
    suivi_id: str | None
    statut: StatutGeneration
    #: Rempli seulement si statut == "terminee".
    resultat_id: str | None
    #: Rempli seulement si statut == "echouee".
    erreur: str | None
    parametres: dict
    started_at: str
    finished_at: str | None


# ── échéances ────────────────────────────────────────────────────────────

TypeEcheance = Literal["devoir", "partiel", "rendu_projet", "autre"]
StatutEcheance = Literal["a_venir", "passee", "reportee", "annulee"]


class Echeance(TypedDict):
    id: str
    titre: str
    type: TypeEcheance
    #: Toujours une date — une échéance EST une date ; ce qui n'est PAS
    #: obligatoire, c'est que le SUIVI qui la contient en ait une (§1).
    date: str
    statut: StatutEcheance
    #: Sous-ensemble des ressources du suivi parent ; [] = toutes.
    ressources_ciblees: list[str]
    chapitres: list[str]
    notes: str
    created_at: str
    updated_at: str
    rappels: list[Rappel]


# ── suivi (racine) ───────────────────────────────────────────────────────

TypeSuivi = Literal["matiere", "projet", "ponctuel", "autre"]


class Suivi(TypedDict):
    id: str
    titre: str
    type: TypeSuivi
    #: Texte libre, vide si non pertinent (ex. un suivi ponctuel) — pas une
    #: collection séparée tant qu'aucun besoin (filtrage...) ne le justifie.
    matiere: str
    description: str
    archive: bool
    #: Ids vers la collection `ressources` du store — jamais une copie.
    ressources: list[str]
    echeances: list[Echeance]
    exercices: list[Exercice]
    taches: list[Tache]
    historique: list[PointAvancement]
    #: Rappels de POINT D'AVANCEMENT récurrents, pas liés à une échéance —
    #: ceux d'échéance vivent sur l'`Echeance` elle-même (§10).
    rappels: list[Rappel]
    verifications: list[Verification]
    #: Pas de champ `resultats` ici : un `Resultat` vit dans sa propre
    #: collection (voir plus haut) et se filtre par `suivi_id`, pour ne pas
    #: synchroniser la même relation à deux endroits.
    created_at: str
    updated_at: str
