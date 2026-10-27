"""Une demande HITL posée au terminal ET à l'île, la première réponse l'emporte.

Avant, une demande partait EXCLUSIVEMENT à l'île dès qu'elle était connectée.
Tant que le CLI se connectait rarement, ça passait inaperçu ; depuis qu'il se
reconnecte tout seul, il l'est en permanence — île fermée comprise — et le
terminal n'affichait plus aucune question : on ne pouvait plus rien faire au
clavier.

Désormais le terminal pose la question comme avant l'île, et l'île la reçoit en
parallèle. Répondre au terminal ferme la carte de l'île ; répondre dans l'île
interrompt la saisie du terminal, qui le signale.

Interrompre une saisie en cours, c'est ce que le code d'avant jugeait peu
fiable : une lecture TTY brute bloquée sur `read(1)` ne se réveille pas. Les
lecteurs du terminal attendent donc désormais par `select()` en surveillant
`ANNULATION` (`attendre_touche`), et les saisies prompt_toolkit sont quittées
depuis leur propre boucle (`prompt_annulable`, `executer_annulable`).
"""
from __future__ import annotations

import os
import select
import threading
import uuid
from typing import Callable, TypeVar

T = TypeVar("T")

#: Levé quand l'île a répondu pendant que le terminal attendait.
ANNULATION = threading.Event()

#: Une demande sans réponse dans l'île n'expire pas : c'est le terminal, ou
#: `abandonner`, qui la clôt.
_DELAI_ILE = 24 * 3600


class ReponseAilleurs(Exception):
    """La demande a reçu sa réponse dans l'île : la saisie du terminal s'efface."""


def attendre_touche(fd: int, delai: float | None = None) -> bool:
    """Attend qu'un octet soit lisible sur `fd`.

    Lève `ReponseAilleurs` si l'île répond entre-temps. Avec `delai`, rend False
    s'il s'écoule sans rien — utile pour distinguer Échap seul d'une séquence.
    """
    reste = delai
    while True:
        pas = 0.1 if reste is None else min(0.1, reste)
        if select.select([fd], [], [], pas)[0]:
            return True
        if ANNULATION.is_set():
            raise ReponseAilleurs
        if reste is not None:
            reste -= pas
            if reste <= 0:
                return False


def lire_octet(fd: int) -> str:
    """Un octet du terminal (déjà lisible), décodé sans erreur."""
    return os.read(fd, 1).decode("utf-8", errors="ignore")


def _quitter_quand_annule(app, fini: threading.Event) -> None:
    while not fini.is_set():
        if ANNULATION.wait(0.1):
            boucle = getattr(app, "loop", None)
            if app.is_running and boucle is not None:
                def _sortir():
                    if app.is_running:
                        app.exit(exception=ReponseAilleurs())
                boucle.call_soon_threadsafe(_sortir)
            return


def executer_annulable(app) -> object:
    """`app.run()`, mais quitté avec `ReponseAilleurs` si l'île répond."""
    fini = threading.Event()
    threading.Thread(target=_quitter_quand_annule, args=(app, fini), daemon=True).start()
    try:
        return app.run()
    finally:
        fini.set()


def prompt_annulable(session, label) -> str:
    """`session.prompt(label)`, mais quitté avec `ReponseAilleurs` si l'île répond."""
    fini = threading.Event()
    threading.Thread(target=_quitter_quand_annule, args=(session.app, fini),
                     daemon=True).start()
    try:
        return session.prompt(label)
    finally:
        fini.set()


def en_course(demande: dict, terminal: Callable[[], T],
              depuis_ile: Callable[[list[str]], T],
              annonce: Callable[[], None] | None = None) -> T:
    """Pose `demande` à l'île en parallèle de `terminal()` ; la première réponse gagne.

    `terminal()` sert la demande au clavier (et peut lever `ReponseAilleurs`) ;
    `depuis_ile(reponses)` convertit la réponse de l'île en résultat ;
    `annonce()` signale au terminal qu'on a répondu ailleurs.
    Sans île connectée, c'est simplement `terminal()`.
    """
    from src.ui.pont_overlay import pont

    if not pont.connecte or not demande.get("questions"):
        return terminal()

    id_ = uuid.uuid4().hex[:8]
    recu: dict[str, list[str]] = {}
    ANNULATION.clear()

    def _ile() -> None:
        reponses = pont.demander(demande, delai=_DELAI_ILE, id_=id_)
        if reponses is not None:
            recu["reponses"] = reponses
            ANNULATION.set()

    fil = threading.Thread(target=_ile, daemon=True)
    fil.start()
    try:
        resultat = terminal()
    except ReponseAilleurs:
        fil.join(timeout=1)
        if annonce:
            annonce()
        return depuis_ile(recu.get("reponses") or [])
    finally:
        ANNULATION.clear()
    # Le terminal a répondu : la carte de l'île se ferme.
    pont.abandonner(id_)
    return resultat
