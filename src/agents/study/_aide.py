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
