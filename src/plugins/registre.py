"""Les plugins installés : ce que le cœur consulte pour savoir quoi activer.

`~/.axon/plugins/installes.json` garde, pour chaque plugin, sa version, ses
capacités et la source d'où il vient (pour `/plugin update`).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from src.infra import chemins


@dataclass(frozen=True)
class Installe:
    id: str
    version: str
    capacites: tuple[str, ...]
    source: dict
    commit: str
    installe_le: str


def dossier() -> Path:
    return chemins.plugins()


def dossier_plugin(ident: str) -> Path:
    return dossier() / ident


def _fichier() -> Path:
    return dossier() / "installes.json"


def installes() -> dict[str, Installe]:
    try:
        brut = json.loads(_fichier().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    resultat = {}
    for ident, entree in brut.items() if isinstance(brut, dict) else ():
        try:
            resultat[ident] = Installe(**{**entree, "capacites": tuple(entree["capacites"])})
        except (TypeError, KeyError):
            continue
    # Un dossier supprimé à la main n'est plus un plugin installé.
    return {i: p for i, p in resultat.items() if dossier_plugin(i).is_dir()}


def enregistrer(plugin: Installe) -> None:
    tous = {i: asdict(p) for i, p in installes().items()}
    tous[plugin.id] = asdict(plugin)
    _ecrire(tous)


def oublier(ident: str) -> None:
    tous = {i: asdict(p) for i, p in installes().items() if i != ident}
    _ecrire(tous)


def _ecrire(donnees: dict) -> None:
    fichier = _fichier()
    fichier.parent.mkdir(parents=True, exist_ok=True)
    temporaire = fichier.with_suffix(".tmp")
    temporaire.write_text(json.dumps(donnees, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporaire.replace(fichier)


def avec_capacite(capacite: str) -> list[str]:
    """Les plugins installés qui déclarent `capacite` (ex. `ile`)."""
    return sorted(i for i, p in installes().items() if capacite in p.capacites)
