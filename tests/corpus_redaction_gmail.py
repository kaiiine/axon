"""Le jeu de `outils/mesure_prompt.py` : le modèle charge-t-il `redaction` AVANT
d'écrire un mail, au lieu d'appeler `gmail_send_email` d'emblée ?

ÉCRIT UNE FOIS, avant toute variante du prompt ou des descriptions, et non
retouché en regardant les résultats. Contrairement à `corpus_skills_lies.py`, chaque
demande de réécriture porte son texte : sans lui, un modèle a raison de demander.

  REDACTION   le texte reste à écrire : `redaction` doit être chargé d'abord ;
  PRET        le message est dicté mot pour mot : charger le skill est inutile.
"""
from __future__ import annotations

REDACTION: list[str] = [
    "rédige un mail à mon patron pour savoir quand je dois rendre le dossier",
    "écris un email de relance à un client qui n'a toujours pas payé sa facture de mars",
    "envoie un mail à marie@exemple.fr pour lui dire que je serai en retard à la réunion de demain",
    "réponds poliment au mail de mon prof qui me demande mon rapport, dis-lui que je le rends vendredi",
    "écris à thomas@exemple.fr pour le remercier de son aide sur le projet",
    "rédige un message pour candidater à un stage de développeur chez Acme, j'ai fait deux ans d'IUT",
    "réécris et envoie ce texte à lea@exemple.fr : « Bonjour, je vous contacte afin de vous informer "
    "que, dans le cadre de nos échanges, il convient de souligner l'importance cruciale de notre rendez-vous. »",
    "fais un mail pour annuler mon abonnement à la salle de sport, adresse contact@salle.fr",
]

PRET: list[str] = [
    "envoie à paul@exemple.fr exactement ceci : objet « Salle B12 », message « La réunion est en salle B12. »",
    "mail à anne@exemple.fr, objet « RDV 14h », corps « Ok pour 14h, à demain. »",
    "envoie « Bien reçu, merci » en réponse à jean@exemple.fr avec l'objet « Re: devis »",
    "mail à contact@exemple.fr, objet « Facture 204 », corps « Facture 204 en pièce jointe. »",
]
