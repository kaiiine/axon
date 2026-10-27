"""Constantes et petits calculs partagés par les modules `tools_*.py`.

Pas un module de logique métier en soi — juste ce qui serait sinon dupliqué
entre `tools_suivi.py`, `tools_echeance.py`, `tools_progression.py` et
`tools_verification.py` (listes de valeurs valides, mise en forme de texte,
le fuseau horaire des rappels).
"""
from __future__ import annotations

import subprocess

TYPES_SUIVI = ("matiere", "projet", "ponctuel", "autre")
TYPES_ECHEANCE = ("devoir", "partiel", "rendu_projet", "autre")
STATUTS_EXERCICE = ("a_faire", "en_cours", "bloque", "termine", "a_revoir")
STATUTS_ECHEANCE = ("a_venir", "passee", "reportee", "annulee")
TYPES_RESSOURCE = ("document", "dossier", "depot_git", "lien")


_MOIS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def date_courte(date_iso: str) -> str:
    """« 2026-11-25 » → « 25 nov. ». Laisse la chaîne telle quelle si elle
    n'est pas une date ISO (donnée ancienne ou saisie libre)."""
    from datetime import date as _date

    try:
        d = _date.fromisoformat(date_iso[:10])
    except ValueError:
        return date_iso
    return f"{d.day} {_MOIS[d.month - 1]}"


def jours_restants(date_iso: str) -> int:
    from datetime import date as _date

    return (_date.fromisoformat(date_iso) - _date.today()).days


def temps_restant_texte(date_iso: str) -> str:
    n = jours_restants(date_iso)
    if n < 0:
        return "passé"
    if n == 0:
        return "aujourd’hui"
    if n == 1:
        return "demain"
    return f"dans {n} jours"


def avancement_exercices(exercices: list[dict]) -> str:
    if not exercices:
        return "—"
    termines = sum(1 for x in exercices if x.get("statut") == "termine")
    return f"{termines}/{len(exercices)} exercices terminés ({round(100 * termines / len(exercices))}%)"


FUSEAU_RAPPELS = "Europe/Paris"


def neuf_heures(date_iso: str):
    """9h, explicitement Europe/Paris (§10) — pas l'heure locale implicite
    de la machine qui exécute `cron_daemon.py`, qui pourrait différer.
    `zoneinfo` gère nativement les changements d'heure CET/CEST : le même
    appel donne +01:00 en hiver et +02:00 en été, sans calcul manuel."""
    from datetime import date as _date, datetime as _datetime
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(FUSEAU_RAPPELS)
    except Exception:
        tz = None  # tzdata absent : on dégrade vers l'heure locale plutôt que d'échouer
    d = _date.fromisoformat(date_iso)
    return _datetime.combine(d, _datetime.min.time()).replace(hour=9, tzinfo=tz)


def deja_passe(reference) -> bool:
    """`reference` (un datetime, éventuellement aware) est-il déjà passé ?
    Compare dans le même référentiel que `reference` pour ne jamais lever
    sur un mélange naive/aware."""
    from datetime import datetime as _datetime
    return reference <= _datetime.now(reference.tzinfo)


def type_ressource_pour_chemin(chemin: str) -> str:
    """Type de ressource d'un chemin local choisi par l'utilisateur : un
    dossier contenant `.git` est un dépôt (branche/commit suivis), un autre
    dossier reste un dossier, tout le reste est un document."""
    from pathlib import Path

    p = Path(chemin)
    if p.is_dir():
        return "depot_git" if (p / ".git").exists() else "dossier"
    return "document"


def depots_git_dans(dossier: str) -> list[str]:
    """Dépôts Git rangés directement dans `dossier` (un niveau) — le cas d'un
    projet front + back, où le dossier parent n'est pas lui-même un dépôt."""
    from pathlib import Path

    racine = Path(dossier)
    if not racine.is_dir():
        return []
    return sorted(str(p) for p in racine.iterdir() if p.is_dir() and (p / ".git").exists())


def depuis_combien_de_temps(horodatage: float) -> str:
    """« il y a 5 min », « il y a 3 h », « il y a 2 j » — en français, sans
    dépendre de la langue de git (`%cr` sortirait « 2 days ago »)."""
    import time

    secondes = max(0, int(time.time() - horodatage))
    if secondes < 3600:
        return f"il y a {max(1, secondes // 60)} min"
    if secondes < 86400:
        return f"il y a {secondes // 3600} h"
    return f"il y a {secondes // 86400} j"


def etat_depot(chemin: str) -> dict | None:
    """Branche, dernier commit (sujet + ancienneté) et nombre de fichiers
    modifiés non commités d'un dépôt local. None s'il est injoignable."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=chemin, capture_output=True, text=True,
                              timeout=5, check=True).stdout.strip()

    try:
        branche = git("rev-parse", "--abbrev-ref", "HEAD")
        horodatage, sujet = git("log", "-1", "--format=%ct%x1f%s").split("\x1f", 1)
        modifies = len([ligne for ligne in git("status", "--porcelain").splitlines() if ligne.strip()])
    except Exception:
        return None
    return {"branche": branche, "sujet": sujet, "age": depuis_combien_de_temps(float(horodatage)),
            "modifies": modifies}


def derniers_commits(chemin: str, nombre: int = 8) -> list[tuple[float, str]]:
    """(horodatage, sujet) des derniers commits d'un dépôt local, du plus
    récent au plus ancien — [] s'il est injoignable."""
    try:
        sortie = subprocess.run(["git", "log", f"-{nombre}", "--format=%ct%x1f%s"], cwd=chemin,
                                capture_output=True, text=True, timeout=5, check=True).stdout
    except Exception:
        return []
    commits = []
    for ligne in sortie.splitlines():
        horodatage, _, sujet = ligne.partition("\x1f")
        if horodatage.isdigit():
            commits.append((float(horodatage), sujet))
    return commits


def resoudre_git(chemin: str) -> dict:
    """Branche/commit d'un dépôt local, sans dépendre des outils git (qui
    portent une logique bien plus riche — ici juste de quoi dater
    l'association). Silencieux en cas d'échec : la ressource reste
    créable, juste sans ces deux champs."""
    try:
        branche = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=chemin,
                                  capture_output=True, text=True, timeout=5).stdout.strip() or None
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=chemin,
                                 capture_output=True, text=True, timeout=5).stdout.strip() or None
        return {"branche": branche, "commit": commit}
    except Exception:
        return {"branche": None, "commit": None}
