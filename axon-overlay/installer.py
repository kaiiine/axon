#!/usr/bin/env python3
"""Installe le dossier complet dans RACINE/.axon/plugins/axon-overlay."""
from __future__ import annotations
import argparse
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def installer(racine: Path) -> Path:
    source = Path(__file__).resolve().parent
    if not (source / "ui/dist/axon.js").is_file():
        raise RuntimeError("Archive sans front compilé : lancer npm ci puis npm run build.")
    parent = racine.resolve() / ".axon" / "plugins"
    destination = parent / "axon-overlay"
    if destination.resolve() == source:
        return destination
    if parent.is_relative_to(source):
        raise ValueError("Choisis la racine du projet Axon, pas le dossier du plugin.")
    if destination.is_symlink():
        raise ValueError("La destination est un lien symbolique : installation interrompue.")
    if destination.exists():
        try:
            metadata = json.loads((destination / "plugin.json").read_text())
        except (OSError, ValueError) as exc:
            raise ValueError("Un dossier existe déjà sans manifeste Axon ; déplace-le avant l’installation.") from exc
        if metadata.get("id") != "axon-overlay":
            raise ValueError("Le dossier existant ne correspond pas au plugin axon-overlay.")
    parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".axon-overlay-", dir=parent))
    backup = None
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True, ignore=shutil.ignore_patterns("node_modules", ".git", "__pycache__", ".pytest_cache", "*.pyc", ".DS_Store"))
        for name in ("lancer.sh", "waybar-toggle.sh"):
            (stage / name).chmod(0o755)
        if destination.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup = parent / ("axon-overlay.backup-" + stamp)
            destination.rename(backup)
        stage.rename(destination)
    except Exception:
        if backup is not None and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="Racine du projet Axon (ou ~ pour une installation utilisateur)")
    args = parser.parse_args()
    try:
        path = installer(args.root)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(f"Plugin installé : {path}\nLancement : {path / 'lancer.sh'}")
