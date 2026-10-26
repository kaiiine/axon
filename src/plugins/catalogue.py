"""Le catalogue de la marketplace : les plugins proposés et où les trouver.

Deux fichiers, fusionnés par identifiant :

- `plugins/catalogue.json`, versionné avec Axon ;
- `~/.axon/plugins/catalogue.json`, les dépôts que tu ajoutes toi-même —
  il l'emporte sur le premier pour un même identifiant.

    {"plugins": [{"id": "…", "nom": "…", "description": "…",
                  "source": {"git": "https://…", "ref": "main", "dossier": "sous/dossier"}}]}
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.plugins import registre
from src.plugins.manifeste import ErreurPlugin

CATALOGUE_AXON = Path(__file__).resolve().parents[2] / "plugins" / "catalogue.json"


@dataclass(frozen=True)
class Source:
    """D'où récupérer un plugin : un dépôt git, ou un dossier local."""
    git: str = ""
    ref: str = ""
    dossier: str = ""
    local: str = ""

    def __post_init__(self) -> None:
        if bool(self.git) == bool(self.local):
            raise ErreurPlugin("une source est soit un dépôt git, soit un dossier local")
        if Path(self.dossier).is_absolute() or ".." in Path(self.dossier).parts:
            raise ErreurPlugin(f"sous-dossier invalide : {self.dossier}")

    @classmethod
    def depuis(cls, brut: object) -> "Source":
        if not isinstance(brut, dict):
            raise ErreurPlugin("source invalide")
        return cls(**{k: str(brut.get(k) or "") for k in ("git", "ref", "dossier", "local")})

    def en_clair(self) -> dict:
        return {k: v for k, v in vars(self).items() if v}

    def decrire(self) -> str:
        if self.local:
            return self.local
        return self.git + (f" @ {self.ref}" if self.ref else "") + (f" · {self.dossier}" if self.dossier else "")


@dataclass(frozen=True)
class Entree:
    id: str
    nom: str
    description: str
    source: Source


def _lire(chemin: Path) -> list[Entree]:
    try:
        brut = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as erreur:
        raise ErreurPlugin(f"catalogue illisible ({chemin}) : {erreur}") from erreur
    entrees = []
    for e in brut.get("plugins", []) if isinstance(brut, dict) else []:
        if isinstance(e, dict) and isinstance(e.get("id"), str):
            entrees.append(Entree(id=e["id"], nom=str(e.get("nom") or e["id"]),
                                  description=str(e.get("description") or ""),
                                  source=Source.depuis(e.get("source"))))
    return entrees


def entrees() -> list[Entree]:
    fusion = {e.id: e for e in _lire(CATALOGUE_AXON)}
    fusion.update({e.id: e for e in _lire(registre.dossier() / "catalogue.json")})
    return sorted(fusion.values(), key=lambda e: e.id)


def trouver(ident: str) -> Entree | None:
    return next((e for e in entrees() if e.id == ident), None)
