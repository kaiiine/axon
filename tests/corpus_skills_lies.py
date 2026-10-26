"""Le jeu de requêtes de `outils/mesure_skills_lies.py` : quand `load_skill` doit-il
être proposé, et quand les groupes d'action doivent-ils rester liés.

ÉCRIT UNE FOIS, AVANT toute mesure de la version « toujours lié », et non relu
pendant le réglage : un jeu qu'on retouche en regardant ses résultats ne mesure
plus rien. Il n'a rien de commun avec `corpus_routage_skills.py` (réglé sur le
routage des skills du code) ni avec CORPUS-ROUTAGE.md.

Trois familles, parce qu'elles n'attendent pas la même chose :

  SKILLS      une procédure existe pour la demande : `load_skill` doit être
              proposé, et le modèle doit charger CE skill ;
  ACTIONS     une action pure, sans rédaction ni savoir-faire à charger : le
              groupe d'action doit rester lié, comme avant ;
  AMBIGUES    les deux à la fois : le skill ET les groupes d'action attendus.
"""
from __future__ import annotations

#: skill attendu → requêtes. La rédaction est mesurée AVEC et SANS le mot « mail » :
#: c'est ce mot qui faisait gagner `gmail` et perdre le groupe des skills.
SKILLS: dict[str, list[str]] = {
    "redaction — avec « mail »": [
        "rédige un mail à mon patron pour savoir quand je dois rendre le dossier",
        "écris un email de relance à un client qui n'a toujours pas payé sa facture",
        "rédigme une réponse polie au mail de mon prof qui me demande mon rapport",
    ],
    "redaction — sans « mail »": [
        "réécris ce paragraphe, il sonne trop robotique",
        "rédige un petit message pour remercier toute mon équipe après le lancement",
        "écris un texte de présentation de mon projet pour la page d'accueil, naturel et pas trop IA",
    ],
    "pentest": [
        "fais un scan de ports de 10.0.0.5 pour mon TP de cyber",
        "aide-moi pour mon CTF, je dois trouver les failles de cette machine du lab",
        "énumère les services ouverts sur la cible et dis-moi lesquels sont vulnérables",
    ],
    "blender": [
        "crée une scène 3D avec une lumière et une caméra dans blender",
        "modélise un petit objet en 3D et exporte-le en GLB",
        "anime un cube qui tourne sur lui-même dans blender",
    ],
    "browser-driving": [
        "clique sur le bouton de connexion dans mon navigateur qui est déjà ouvert",
        "remplis le formulaire de la page ouverte et envoie-le",
        "regarde les erreurs dans la console de l'onglet que j'ai ouvert",
    ],
}

#: (requête, groupe d'action qui doit rester lié) — aucune rédaction à faire.
ACTIONS: list[tuple[str, str]] = [
    ("envoie ce mail à jean@exemple.fr", "gmail"),
    ("résume mes mails non lus", "gmail"),
    ("réponds oui au dernier mail de Paul", "gmail"),
    ("ajoute une réunion demain à 14h dans mon calendrier", "calendar"),
    ("qu'est-ce que j'ai de prévu vendredi dans mon agenda", "calendar"),
    ("décale mon rendez-vous de lundi à mardi même heure", "calendar"),
]

#: (requête, skill attendu, groupes d'action qui doivent aussi rester liés).
AMBIGUES: list[tuple[str, str, tuple[str, ...]]] = [
    ("écris un mail à Paul pour lui demander ses disponibilités et ajoute la réunion au calendrier",
     "redaction", ("gmail", "calendar")),
    ("rédige la réponse au mail de mon patron et envoie-la",
     "redaction", ("gmail",)),
    ("fais un scan de ports de la cible du lab puis écris un compte rendu par mail",
     "pentest", ("gmail",)),
]
