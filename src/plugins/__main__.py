"""`/plugin` hors du CLI — pour `setup.sh`, `setup.ps1` et les scripts.

    python -m src.plugins list
    python -m src.plugins install ./axon-overlay
"""
from __future__ import annotations

import sys

from src.plugins.commandes import handle_plugin


def _choisir(options: list[str], titre: str) -> str | None:
    print(f"\n  {titre}")
    for numero, option in enumerate(options, 1):
        print(f"    {numero}. {option}")
    try:
        reponse = input("  Choix (Entrée pour annuler) : ").strip()
    except EOFError:
        return None
    return options[int(reponse) - 1] if reponse.isdigit() and 0 < int(reponse) <= len(options) else None


def main() -> int:
    texte = handle_plugin(sys.argv[1:], choisir=_choisir, annoncer=lambda ligne: print(f"  {ligne}"))
    print(texte)
    return 1 if texte.startswith("✗") else 0


if __name__ == "__main__":
    raise SystemExit(main())
