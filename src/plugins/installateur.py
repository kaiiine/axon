"""Installer, mettre à jour et retirer un plugin.

Tout se prépare dans un dossier de travail : récupération (clone git superficiel
ou copie locale), validation du manifeste, étapes d'installation. La version
installée n'est remplacée qu'à la fin, d'un seul renommage — une étape qui
échoue laisse l'ancienne en place.

Les étapes d'installation exécutent du code venu du dépôt : elles ne tournent
qu'après `confirmer`, qui les voit en clair.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from src.plugins import registre
from src.plugins.catalogue import Source
from src.plugins.manifeste import ErreurPlugin, Manifeste, Plateforme, plateforme_courante

#: Ce qu'une copie locale n'emporte pas : historique et artefacts reconstruits.
_IGNORES = shutil.ignore_patterns(".git", "node_modules", "target", "__pycache__", "*.pyc")
_DELAI_ETAPE_S = 900

Confirmer = Callable[[Manifeste, Plateforme], bool]
Annoncer = Callable[[str], None]


class InstallationAnnulee(ErreurPlugin):
    """L'utilisateur a refusé les étapes d'installation."""


def installer(source: Source, *, confirmer: Confirmer, annoncer: Annoncer = lambda _t: None,
              id_attendu: str = "") -> registre.Installe:
    racine = registre.dossier()
    travail_parent = racine / ".travail"
    travail_parent.mkdir(parents=True, exist_ok=True)
    travail = Path(tempfile.mkdtemp(dir=travail_parent))
    try:
        annoncer(f"récupération : {source.decrire()}")
        recupere, commit = _recuperer(source, travail)
        manifeste = Manifeste.lire(recupere)
        if id_attendu and manifeste.id != id_attendu:
            raise ErreurPlugin(f"le dépôt contient « {manifeste.id} », pas « {id_attendu} »")
        plateforme = manifeste.pour(plateforme_courante())
        if plateforme is None:
            raise ErreurPlugin(f"{manifeste.id} ne prend pas en charge {plateforme_courante()} "
                               f"(seulement : {', '.join(manifeste.plateformes)})")
        manquantes = [c for c in plateforme.commandes if not shutil.which(c)]
        if manquantes:
            raise ErreurPlugin(f"{manifeste.id} a besoin de : {', '.join(manquantes)}")
        if plateforme.installation and not confirmer(manifeste, plateforme):
            raise InstallationAnnulee(f"installation de {manifeste.id} annulée")
        for etape in plateforme.installation:
            annoncer(f"$ {' '.join(etape)}")
            _executer(etape, recupere)
        _mettre_en_place(recupere, registre.dossier_plugin(manifeste.id))
        installe = registre.Installe(
            id=manifeste.id, version=manifeste.version, capacites=tuple(sorted(manifeste.capacites)),
            source=source.en_clair(), commit=commit,
            installe_le=datetime.now().isoformat(timespec="seconds"))
        registre.enregistrer(installe)
        return installe
    finally:
        shutil.rmtree(travail, ignore_errors=True)


def mettre_a_jour(ident: str, *, confirmer: Confirmer,
                  annoncer: Annoncer = lambda _t: None) -> registre.Installe:
    actuel = registre.installes().get(ident)
    if actuel is None:
        raise ErreurPlugin(f"{ident} n'est pas installé")
    return installer(Source.depuis(actuel.source), confirmer=confirmer, annoncer=annoncer,
                     id_attendu=ident)


def desinstaller(ident: str) -> None:
    dossier = registre.dossier_plugin(ident)
    if ident not in registre.installes():
        raise ErreurPlugin(f"{ident} n'est pas installé")
    registre.oublier(ident)
    shutil.rmtree(dossier, ignore_errors=True)


def _recuperer(source: Source, travail: Path) -> tuple[Path, str]:
    """Le dossier du plugin dans `travail`, et le commit d'où il vient."""
    if source.local:
        origine = Path(source.local).expanduser().resolve() / source.dossier
        if not origine.is_dir():
            raise ErreurPlugin(f"dossier introuvable : {origine}")
        copie = travail / "plugin"
        shutil.copytree(origine, copie, ignore=_IGNORES, symlinks=True)
        return copie, ""
    if not shutil.which("git"):
        raise ErreurPlugin("git est nécessaire pour installer depuis un dépôt")
    clone = travail / "depot"
    commande = ["git", "clone", "--depth", "1", "--quiet"]
    if source.ref:
        commande += ["--branch", source.ref]
    _executer([*commande, "--", source.git, str(clone)], travail)
    commit = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=False).stdout.strip()
    dossier = (clone / source.dossier).resolve()
    if not dossier.is_dir() or not dossier.is_relative_to(clone.resolve()):
        raise ErreurPlugin(f"sous-dossier introuvable dans le dépôt : {source.dossier}")
    shutil.rmtree(clone / ".git", ignore_errors=True)
    return dossier, commit


def _executer(arguments: list[str] | tuple[str, ...], dossier: Path) -> None:
    try:
        resultat = subprocess.run(list(arguments), cwd=dossier, capture_output=True, text=True,
                                  timeout=_DELAI_ETAPE_S, check=False)
    except FileNotFoundError:
        raise ErreurPlugin(f"programme introuvable : {arguments[0]}") from None
    except subprocess.TimeoutExpired:
        raise ErreurPlugin(f"délai dépassé : {' '.join(arguments)}") from None
    if resultat.returncode != 0:
        sortie = (resultat.stderr or resultat.stdout).strip().splitlines()[-8:]
        raise ErreurPlugin(f"échec de « {' '.join(arguments)} » :\n" + "\n".join(sortie))


def _mettre_en_place(pret: Path, destination: Path) -> None:
    """Remplace la version installée d'un seul renommage, sans fenêtre où
    le plugin serait à moitié copié."""
    entrant = destination.with_name(f".{destination.name}.entrant")
    sortant = destination.with_name(f".{destination.name}.sortant")
    for reste in (entrant, sortant):
        shutil.rmtree(reste, ignore_errors=True)
    shutil.move(str(pret), entrant)
    if destination.exists():
        destination.rename(sortant)
    entrant.rename(destination)
    shutil.rmtree(sortant, ignore_errors=True)
