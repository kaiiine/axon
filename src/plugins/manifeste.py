"""Le contrat d'un plugin : son `plugin.json`, validé avant toute installation.

    {
      "id": "axon-overlay",                    minuscules, chiffres, tirets
      "name": "Axon Overlay",
      "version": "0.2.0",
      "description": "…",
      "capacites": ["ile", "notifications"],   ce que le plugin apporte au cœur
      "platforms": {
        "linux-wayland": {
          "entrypoint": "lancer.sh",           facultatif
          "toggle": "waybar-toggle.sh",        facultatif
          "commandes": ["npm"],                programmes requis pour l'installer
          "installation": [["npm", "ci"], ["npm", "run", "build"]]
        }
      }
    }

Les étapes d'installation sont des listes d'arguments, jamais une ligne de
shell : rien n'est interprété, et elles ne tournent qu'après confirmation.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")

#: Ce que le cœur sait exploiter. Une capacité inconnue est refusée : un plugin
#: plus récent qu'Axon le dit, au lieu de rester sans effet en silence.
CAPACITES = {"ile", "notifications"}


class ErreurPlugin(Exception):
    """Un plugin invalide, introuvable ou impossible à installer."""


@dataclass(frozen=True)
class Plateforme:
    nom: str
    entrypoint: str = ""
    toggle: str = ""
    commandes: tuple[str, ...] = ()
    installation: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class Manifeste:
    id: str
    nom: str
    version: str
    description: str
    capacites: frozenset[str] = frozenset()
    plateformes: dict[str, Plateforme] = field(default_factory=dict)

    @classmethod
    def lire(cls, dossier: Path) -> "Manifeste":
        chemin = dossier / "plugin.json"
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ErreurPlugin(f"pas de plugin.json dans {dossier}") from None
        except (OSError, ValueError) as erreur:
            raise ErreurPlugin(f"plugin.json illisible : {erreur}") from erreur
        return cls.depuis(brut)

    @classmethod
    def depuis(cls, brut: object) -> "Manifeste":
        if not isinstance(brut, dict):
            raise ErreurPlugin("plugin.json doit être un objet JSON")
        ident = brut.get("id")
        if not isinstance(ident, str) or not _ID.match(ident):
            raise ErreurPlugin(f"identifiant invalide : {ident!r} (minuscules, chiffres, tirets)")
        version = brut.get("version")
        if not isinstance(version, str) or not version:
            raise ErreurPlugin(f"{ident} : version manquante")
        capacites = brut.get("capacites", [])
        if not isinstance(capacites, list) or not all(isinstance(c, str) for c in capacites):
            raise ErreurPlugin(f"{ident} : « capacites » doit être une liste de noms")
        inconnues = set(capacites) - CAPACITES
        if inconnues:
            raise ErreurPlugin(f"{ident} : capacités inconnues de cette version d'Axon : "
                               f"{', '.join(sorted(inconnues))}")
        plateformes = brut.get("platforms", {})
        if not isinstance(plateformes, dict):
            raise ErreurPlugin(f"{ident} : « platforms » doit associer chaque système à sa "
                               f"configuration (manifeste d'un ancien format ?)")
        if not plateformes:
            raise ErreurPlugin(f"{ident} : aucune plateforme déclarée")
        return cls(
            id=ident,
            nom=str(brut.get("name") or ident),
            version=version,
            description=str(brut.get("description") or ""),
            capacites=frozenset(capacites),
            plateformes={nom: _plateforme(ident, nom, p) for nom, p in plateformes.items()},
        )

    def pour(self, plateforme: str) -> Plateforme | None:
        return self.plateformes.get(plateforme)


def _plateforme(ident: str, nom: str, brut: object) -> Plateforme:
    if not isinstance(brut, dict):
        raise ErreurPlugin(f"{ident} : plateforme {nom} invalide")
    etapes = brut.get("installation", [])
    valides = isinstance(etapes, list) and all(
        isinstance(e, list) and e and all(isinstance(a, str) for a in e) for e in etapes)
    if not valides:
        raise ErreurPlugin(f"{ident} : étapes d'installation ({nom}) = listes d'arguments")
    commandes = brut.get("commandes", [])
    if not isinstance(commandes, list) or not all(isinstance(c, str) for c in commandes):
        raise ErreurPlugin(f"{ident} : « commandes » ({nom}) doit être une liste de programmes")
    return Plateforme(
        nom=nom,
        entrypoint=str(brut.get("entrypoint") or ""),
        toggle=str(brut.get("toggle") or ""),
        commandes=tuple(commandes),
        installation=tuple(tuple(e) for e in etapes),
    )


def plateforme_courante() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux-wayland" if os.environ.get("WAYLAND_DISPLAY") else "linux"
