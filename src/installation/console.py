"""Affichage et saisie de l'installateur, dans le style de `setup.sh`.

Les couleurs se coupent hors terminal et avec `NO_COLOR` ; sous Windows, la
console est d'abord passée en mode ANSI.
"""
from __future__ import annotations

import os
import sys


def _activer_ansi_windows() -> bool:
    import ctypes

    noyau = ctypes.windll.kernel32
    sortie = noyau.GetStdHandle(-11)                     # STD_OUTPUT_HANDLE
    mode = ctypes.c_ulong()
    if not noyau.GetConsoleMode(sortie, ctypes.byref(mode)):
        return False
    return bool(noyau.SetConsoleMode(sortie, mode.value | 0x0004))   # VIRTUAL_TERMINAL_PROCESSING


def _couleurs() -> bool:
    if os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return False
    return _activer_ansi_windows() if sys.platform == "win32" else True


_ACTIVES = _couleurs()


def _c(code: str) -> str:
    return f"\033[{code}m" if _ACTIVES else ""


ORANGE, ORANGE_SOURD, BLANC = _c("38;5;214"), _c("38;5;172"), _c("0;97")
VERT, ROUGE, SOURD, FIN = _c("38;5;78"), _c("0;31"), _c("2"), _c("0")


def ok(texte: str) -> None:
    print(f"{VERT}  ✓  {FIN}{texte}")


def info(texte: str) -> None:
    print(f"{ORANGE}  →  {FIN}{texte}")


def alerte(texte: str) -> None:
    print(f"{ORANGE_SOURD}  ⚠  {FIN}{texte}")


def etape(titre: str) -> None:
    print(f"\n{ORANGE}━━  {BLANC}{titre}{FIN}")


def detail(texte: str = "") -> None:
    print(f"  {SOURD}{texte}{FIN}" if texte else "")


def titre(texte: str) -> None:
    print(f"  {ORANGE}{texte}{FIN}")


def demander(invite: str, marque: str = ">") -> str:
    """Une ligne saisie, sans espaces autour. Fin de saisie = réponse vide."""
    try:
        return input(f"  {ORANGE}{marque}{FIN} {invite}").strip()
    except EOFError:
        print()
        return ""


def oui(question: str, defaut: bool = False) -> bool:
    choix = "[O/n]" if defaut else "[o/N]"
    reponse = demander(f"{question} {choix} ", marque="?").lower()
    return defaut if not reponse else reponse[0] in "oy"
