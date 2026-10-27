"""Flux de texte vers l'île : un appel LLM dont la réponse s'affiche en temps
réel, morceau par morceau.

Même principe que `raccourcis_overlay.ACTIONS` : seule une source listée dans
`FLUX` peut être demandée par l'île. Chaque source est une fonction
`(cible) -> Iterator[str]`. Le protocole est générique — l'île affiche
n'importe quel flux avec le même composant (`TexteEnFlux.svelte`) :

    île → CLI : {"type": "demander_flux", "id", "genre", "cible"}
    CLI → île : {"type": "flux_morceau", "id", "texte"}   (répété)
                {"type": "flux_fin", "id"} | {"type": "flux_erreur", "id", "message"}
"""
from __future__ import annotations

import time
from typing import Callable, Iterator


def _resume_suivi(cible: str) -> Iterator[str]:
    from src.agents.study.resume import flux_resume_suivi
    return flux_resume_suivi(cible)


FLUX: dict[str, Callable[[str], Iterator[str]]] = {
    "resume_suivi": _resume_suivi,
}

#: Regrouper les morceaux : un modèle rend parfois un mot à la fois, et un
#: message socket + un rendu markdown par mot ferait ramer l'île.
INTERVALLE_ENVOI = 0.08  # sec


def diffuser(id_: str, genre: str, cible: str, envoyer: Callable[..., object]) -> None:
    """Exécute le flux `genre` sur `cible` et l'envoie par `envoyer(**message)`.
    Bloquant : à lancer dans un thread. Ne lève jamais — une erreur devient
    un `flux_erreur` pour cet id, pour que l'île ne reste pas en attente."""
    source = FLUX.get(genre)
    if source is None:
        envoyer(type="flux_erreur", id=id_, message=f"flux inconnu : {genre}")
        return
    tampon = ""
    dernier_envoi = time.monotonic()
    try:
        for morceau in source(cible):
            tampon += morceau
            if time.monotonic() - dernier_envoi >= INTERVALLE_ENVOI:
                envoyer(type="flux_morceau", id=id_, texte=tampon)
                tampon = ""
                dernier_envoi = time.monotonic()
        if tampon:
            envoyer(type="flux_morceau", id=id_, texte=tampon)
        envoyer(type="flux_fin", id=id_)
    except Exception as e:
        if tampon:
            envoyer(type="flux_morceau", id=id_, texte=tampon)
        envoyer(type="flux_erreur", id=id_, message=str(e))
