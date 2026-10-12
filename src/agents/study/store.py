"""Persistance des suivis (matières, projets, travaux ponctuels), de leurs
ressources, échéances et résultats.

Même squelette que `src/agents/cron/store.py` : un fichier JSON, un
`FileLock`, des fonctions `_load`/`_save` privées. Trois collections au lieu
d'une liste plate d'échéances (v1) :

- `suivis`   — la racine. Une échéance appartient à un suivi, jamais seule.
- `ressources` — collection À PART, référencée par ID depuis les suivis
  (`Suivi.ressources: list[str]`) : la même ressource (un dépôt Git, un PDF de
  cours) doit pouvoir être partagée par plusieurs suivis sans copie
  divergente, impossible si elle vivait imbriquée dans un seul suivi.
- `resultats` — collection À PART elle aussi, avec un `suivi_id` OPTIONNEL :
  un travail rapide (§3) produit un résultat qui existe AVANT tout suivi, puis
  se rattache après coup (`rattacher_resultat`) sans jamais être déplacé.
"""
from __future__ import annotations

import json
import uuid
from datetime import date as _date, datetime
from filelock import FileLock
from src.infra import chemins as _chemins
from .type import (
    Echeance, Exercice, GenerationTache, PointAvancement, Rappel, Ressource, Resultat, Suivi, Tache, Verification,
)

FICHIER = _chemins.etudes()
_LOCK = FileLock(str(FICHIER) + ".lock")
_VERSION = 2


def _vide() -> dict:
    return {"version": _VERSION, "suivis": [], "ressources": [], "resultats": [], "generations": []}


def _maintenant() -> str:
    return datetime.now().isoformat()


# ── migration v1 → v2 ──────────────────────────────────────────────────

def _migrer_v1(data: dict) -> dict:
    """L'ancien schéma (liste plate d'échéances, exercices/documents imbriqués
    dedans) devient : un suivi par échéance (type « matiere » si une matière
    était renseignée), l'échéance elle-même à l'intérieur, les anciens noms de
    documents promus en ressources « document »/« copie ». Rien n'est perdu —
    chaque échéance redevient consultable telle quelle, sous un suivi qui
    porte son nom. Écrite tout de suite par `_load` : la migration n'arrive
    qu'une fois, pas à chaque lecture."""
    neuf = _vide()
    maintenant = _maintenant()
    for ancienne in data.get("echeances", []):
        ressources_ids = []
        for nom_fichier in ancienne.get("documents", []) or []:
            ressource: Ressource = {
                "id": "res_" + uuid.uuid4().hex[:8], "type": "document", "nom": nom_fichier,
                "provenance": "copie", "chemin": nom_fichier, "taille": None, "modifie_le": None,
                "branche": None, "commit": None, "accessible": True, "message_erreur": None,
                "created_at": maintenant, "updated_at": maintenant,
            }
            neuf["ressources"].append(ressource)
            ressources_ids.append(ressource["id"])

        echeance_id = ancienne.get("id") or "ech_" + uuid.uuid4().hex[:8]
        echeance: Echeance = {
            "id": echeance_id, "titre": ancienne.get("titre", ""),
            "type": ancienne.get("type", "autre"), "date": ancienne.get("date", ""),
            "statut": "a_venir", "ressources_ciblees": [],
            "chapitres": ancienne.get("chapitres", []) or [], "notes": ancienne.get("notes", ""),
            "created_at": ancienne.get("created_at", maintenant),
            "updated_at": ancienne.get("updated_at", maintenant),
            "rappels": ancienne.get("rappels", []) or [],
        }
        exercices = [
            {**x, "ressource_id": None, "echeance_id": echeance_id,
             "indices_donnes": x.get("indices_donnes", 0)}
            for x in (ancienne.get("exercices", []) or [])
        ]
        historique = [
            {**p, "origine": "utilisateur", "echeance_id": None}
            for p in (ancienne.get("historique", []) or [])
        ]
        suivi: Suivi = {
            "id": "suivi_" + uuid.uuid4().hex[:8],
            "titre": ancienne.get("matiere") or ancienne.get("titre", "Suivi"),
            "type": "matiere" if ancienne.get("matiere") else "autre",
            "matiere": ancienne.get("matiere", ""), "description": "", "archive": False,
            "ressources": ressources_ids, "echeances": [echeance], "exercices": exercices,
            "taches": [], "historique": historique, "rappels": [], "verifications": [],
            "created_at": echeance["created_at"], "updated_at": maintenant,
        }
        neuf["suivis"].append(suivi)
    return neuf


def _load() -> dict:
    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    if not FICHIER.exists():
        return _vide()
    try:
        data = json.loads(FICHIER.read_text())
    except Exception:
        return _vide()
    if not isinstance(data, dict):
        return _vide()
    if data.get("version") == 1 and isinstance(data.get("echeances"), list):
        migre = _migrer_v1(data)
        _save(migre)
        return migre
    if data.get("version") != _VERSION or not all(
        isinstance(data.get(cle), list) for cle in ("suivis", "ressources", "resultats")
    ):
        return _vide()
    # `generations` est arrivée après coup (lot 3) sur un schéma v2 déjà écrit
    # — même traitement que `verifications` plus bas : un complément
    # silencieux, jamais une invalidation de tout le fichier pour un champ
    # manquant.
    data.setdefault("generations", [])
    for suivi in data["suivis"]:
        # Champs ajoutés après coup sur un fichier v2 déjà écrit par une
        # version antérieure — pas de bump de version pour un champ manquant,
        # juste un complément silencieux.
        suivi.setdefault("verifications", [])
        for rappel in suivi.get("rappels", []):
            rappel.setdefault("offset_jours", None)
        for echeance in suivi.get("echeances", []):
            for rappel in echeance.get("rappels", []):
                rappel.setdefault("offset_jours", None)
    return data


def _save(data: dict) -> None:
    """Écrit dans un fichier temporaire PUIS renomme — `os.replace` est
    atomique sur un même système de fichiers : un crash en plein milieu de
    l'écriture laisse l'ancien contenu intact, jamais un JSON à moitié
    écrit (§12 « écritures atomiques »)."""
    import os
    import tempfile

    FICHIER.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=FICHIER.parent, prefix=".etudes-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        os.replace(tmp_path, FICHIER)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _avec_suivi(suivi_id: str, fonction):
    """Charge, verrouille, laisse `fonction(data, suivi)` modifier en place,
    sauve. None si le suivi n'existe pas — rien n'est sauvé dans ce cas."""
    with _LOCK:
        data = _load()
        suivi = next((s for s in data["suivis"] if s["id"] == suivi_id), None)
        if suivi is None:
            return None
        resultat = fonction(data, suivi)
        suivi["updated_at"] = _maintenant()
        _save(data)
        return resultat


# ── ressources ───────────────────────────────────────────────────────────

def ajouter_ressource(
    type: str, nom: str, provenance: str, chemin: str,
    taille: int | None = None, modifie_le: str | None = None,
    branche: str | None = None, commit: str | None = None,
) -> Ressource:
    maintenant = _maintenant()
    ressource: Ressource = {
        "id": "res_" + uuid.uuid4().hex[:8], "type": type, "nom": nom, "provenance": provenance,
        "chemin": chemin, "taille": taille, "modifie_le": modifie_le, "branche": branche,
        "commit": commit, "accessible": True, "message_erreur": None,
        "created_at": maintenant, "updated_at": maintenant,
    }
    with _LOCK:
        data = _load()
        data["ressources"].append(ressource)
        _save(data)
    return ressource


def obtenir_ressource(ressource_id: str) -> Ressource | None:
    return next((r for r in _load()["ressources"] if r["id"] == ressource_id), None)


def lister_ressources() -> list[Ressource]:
    return _load()["ressources"]


def marquer_ressource(ressource_id: str, accessible: bool, message_erreur: str | None = None) -> Ressource | None:
    """Une ressource devenue injoignable n'est jamais purgée — juste
    marquée, avec l'explication (§2)."""
    with _LOCK:
        data = _load()
        ressource = next((r for r in data["ressources"] if r["id"] == ressource_id), None)
        if ressource is None:
            return None
        ressource["accessible"] = accessible
        ressource["message_erreur"] = message_erreur
        ressource["updated_at"] = _maintenant()
        _save(data)
        return ressource


def suivis_utilisant(ressource_id: str) -> list[Suivi]:
    return [s for s in _load()["suivis"] if ressource_id in s.get("ressources", [])]


# ── suivis ───────────────────────────────────────────────────────────────

def creer_suivi(titre: str, type: str, matiere: str = "", description: str = "") -> Suivi:
    maintenant = _maintenant()
    suivi: Suivi = {
        "id": "suivi_" + uuid.uuid4().hex[:8], "titre": titre, "type": type, "matiere": matiere,
        "description": description, "archive": False, "ressources": [], "echeances": [],
        "exercices": [], "taches": [], "historique": [], "rappels": [], "verifications": [],
        "created_at": maintenant, "updated_at": maintenant,
    }
    with _LOCK:
        data = _load()
        data["suivis"].append(suivi)
        _save(data)
    return suivi


def lister_suivis(archives: bool = False) -> list[Suivi]:
    return [s for s in _load()["suivis"] if s.get("archive", False) == archives]


def obtenir_suivi(suivi_id: str) -> Suivi | None:
    return next((s for s in _load()["suivis"] if s["id"] == suivi_id), None)


def archiver_suivi(suivi_id: str, archive: bool = True) -> Suivi | None:
    def _faire(_data, suivi):
        suivi["archive"] = archive
        return suivi
    return _avec_suivi(suivi_id, _faire)


def enregistrer_resume(suivi_id: str, texte: str) -> Suivi | None:
    """Garde le dernier résumé IA du suivi : la page projet l'affiche tout de
    suite à la prochaine ouverture, sans repayer un appel LLM."""
    def _faire(_data, suivi):
        suivi["resume"] = {"texte": texte, "date": _maintenant()}
        return suivi
    return _avec_suivi(suivi_id, _faire)


def supprimer_suivi(suivi_id: str) -> Suivi | None:
    """Supprime définitivement un suivi. Renvoie le suivi supprimé (pour que
    l'appelant désactive ses rappels cron), ou None s'il n'existe pas.

    Ce qui ne disparaît PAS avec lui : les résultats générés (fichiers dans
    ~/Documents/axon_fiches) redeviennent du travail rapide non rattaché, et
    les ressources encore utilisées par un autre suivi restent. Seules les
    ressources qui ne servaient qu'à lui sont retirées — ce ne sont que des
    références, aucun fichier du disque n'est touché."""
    with _LOCK:
        data = _load()
        suivi = next((s for s in data["suivis"] if s["id"] == suivi_id), None)
        if suivi is None:
            return None
        data["suivis"] = [s for s in data["suivis"] if s["id"] != suivi_id]
        for resultat in data["resultats"]:
            if resultat.get("suivi_id") == suivi_id:
                resultat["suivi_id"] = None
        encore_utilisees = {rid for s in data["suivis"] for rid in s["ressources"]}
        data["ressources"] = [r for r in data["ressources"]
                              if r["id"] not in suivi["ressources"] or r["id"] in encore_utilisees]
        _save(data)
        return suivi


def associer_ressource(suivi_id: str, ressource_id: str) -> Suivi | None:
    def _faire(_data, suivi):
        if ressource_id not in suivi["ressources"]:
            suivi["ressources"].append(ressource_id)
        return suivi
    return _avec_suivi(suivi_id, _faire)


def retirer_ressource(suivi_id: str, ressource_id: str) -> bool:
    """Retire seulement l'ASSOCIATION — la ressource elle-même et ses liens
    vers d'autres suivis restent intacts (§2)."""
    def _faire(_data, suivi):
        avant = len(suivi["ressources"])
        suivi["ressources"] = [r for r in suivi["ressources"] if r != ressource_id]
        return len(suivi["ressources"]) < avant
    return bool(_avec_suivi(suivi_id, _faire))


# ── échéances ────────────────────────────────────────────────────────────

def ajouter_echeance(
    suivi_id: str, titre: str, type: str, date: str,
    ressources_ciblees: list[str] | None = None, chapitres: list[str] | None = None,
    notes: str = "",
) -> Echeance | None:
    def _faire(_data, suivi):
        maintenant = _maintenant()
        echeance: Echeance = {
            "id": "ech_" + uuid.uuid4().hex[:8], "titre": titre, "type": type, "date": date,
            "statut": "a_venir", "ressources_ciblees": list(ressources_ciblees or []),
            "chapitres": list(chapitres or []), "notes": notes,
            "created_at": maintenant, "updated_at": maintenant, "rappels": [],
        }
        suivi["echeances"].append(echeance)
        return echeance
    return _avec_suivi(suivi_id, _faire)


def trouver_echeance(echeance_id: str) -> tuple[Suivi, Echeance] | None:
    """Cherche dans tous les suivis — utile quand on n'a que l'ID (ex. depuis
    un rappel cron, qui ne connaît que ça)."""
    for suivi in _load()["suivis"]:
        for echeance in suivi["echeances"]:
            if echeance["id"] == echeance_id:
                return suivi, echeance
    return None


def lister_echeances(a_venir_seulement: bool = True, inclure_archives: bool = False) -> list[tuple[Suivi, Echeance]]:
    aujourdhui = _date.today().isoformat()
    paires: list[tuple[Suivi, Echeance]] = []
    for suivi in _load()["suivis"]:
        if suivi.get("archive", False) and not inclure_archives:
            continue
        for echeance in suivi["echeances"]:
            if a_venir_seulement and echeance.get("date", "") < aujourdhui:
                continue
            paires.append((suivi, echeance))
    return sorted(paires, key=lambda paire: paire[1].get("date", ""))


def maj_echeance(suivi_id: str, echeance_id: str, **champs) -> Echeance | None:
    """`champs` parmi date/statut/notes/chapitres/ressources_ciblees/titre —
    seuls ceux fournis (non None) changent."""
    permis = {"date", "statut", "notes", "chapitres", "ressources_ciblees", "titre"}
    def _faire(_data, suivi):
        echeance = next((e for e in suivi["echeances"] if e["id"] == echeance_id), None)
        if echeance is None:
            return None
        for cle, valeur in champs.items():
            if cle in permis and valeur is not None:
                echeance[cle] = valeur
        echeance["updated_at"] = _maintenant()
        return echeance
    return _avec_suivi(suivi_id, _faire)


# ── exercices ────────────────────────────────────────────────────────────

def ajouter_exercice(
    suivi_id: str, titre: str, description: str = "",
    ressource_id: str | None = None, echeance_id: str | None = None,
) -> Exercice | None:
    def _faire(_data, suivi):
        maintenant = _maintenant()
        exercice: Exercice = {
            "id": "exo_" + uuid.uuid4().hex[:8], "titre": titre, "description": description,
            "statut": "a_faire", "tentatives": [], "difficultes": [], "indices_donnes": 0,
            "ressource_id": ressource_id, "echeance_id": echeance_id,
            "created_at": maintenant, "updated_at": maintenant,
        }
        suivi["exercices"].append(exercice)
        return exercice
    return _avec_suivi(suivi_id, _faire)


def maj_exercice(
    suivi_id: str, exercice_id: str, statut: str | None = None,
    tentative: str | None = None, difficulte: str | None = None, indice: bool = False,
) -> Exercice | None:
    def _faire(_data, suivi):
        exercice = next((x for x in suivi["exercices"] if x["id"] == exercice_id), None)
        if exercice is None:
            return None
        maintenant = _maintenant()
        if statut is not None:
            exercice["statut"] = statut
        if tentative is not None:
            exercice["tentatives"].append({"date": maintenant, "texte": tentative})
        if difficulte is not None:
            exercice["difficultes"].append({"date": maintenant, "texte": difficulte})
        if indice:
            exercice["indices_donnes"] += 1
        exercice["updated_at"] = maintenant
        return exercice
    return _avec_suivi(suivi_id, _faire)


# ── tâches ───────────────────────────────────────────────────────────────

def ajouter_tache(suivi_id: str, titre: str, echeance_id: str | None = None) -> Tache | None:
    def _faire(_data, suivi):
        maintenant = _maintenant()
        tache: Tache = {
            "id": "tache_" + uuid.uuid4().hex[:8], "titre": titre, "statut": "a_faire",
            "echeance_id": echeance_id, "created_at": maintenant, "updated_at": maintenant,
        }
        suivi["taches"].append(tache)
        return tache
    return _avec_suivi(suivi_id, _faire)


def maj_tache(suivi_id: str, tache_id: str, statut: str) -> Tache | None:
    def _faire(_data, suivi):
        tache = next((t for t in suivi["taches"] if t["id"] == tache_id), None)
        if tache is None:
            return None
        tache["statut"] = statut
        tache["updated_at"] = _maintenant()
        return tache
    return _avec_suivi(suivi_id, _faire)


# ── historique ───────────────────────────────────────────────────────────

def ajouter_point_avancement(
    suivi_id: str, texte: str, origine: str = "utilisateur", echeance_id: str | None = None,
) -> PointAvancement | None:
    def _faire(_data, suivi):
        point: PointAvancement = {
            "date": _maintenant(), "texte": texte, "origine": origine, "echeance_id": echeance_id,
        }
        suivi["historique"].append(point)
        return point
    return _avec_suivi(suivi_id, _faire)


# ── rappels ──────────────────────────────────────────────────────────────
# Deux familles : ceux d'une échéance précise (vivent SUR l'échéance) et ceux
# de point d'avancement récurrent (vivent sur le suivi, pas liés à une date).

def ajouter_rappel_echeance(
    suivi_id: str, echeance_id: str, cron_id: str, quand: str, offset_jours: int | None = None,
) -> Rappel | None:
    def _faire(_data, suivi):
        echeance = next((e for e in suivi["echeances"] if e["id"] == echeance_id), None)
        if echeance is None:
            return None
        rappel: Rappel = {"cron_id": cron_id, "type": "echeance", "quand": quand,
                           "echeance_id": echeance_id, "offset_jours": offset_jours,
                           "frequence_jours": None}
        echeance["rappels"].append(rappel)
        return rappel
    return _avec_suivi(suivi_id, _faire)


def trouver_rappel(cron_id: str) -> tuple[Suivi, Echeance | None, Rappel] | None:
    """Le rappel d'études qui correspond à une tâche cron — le daemon ne
    connaît que l'id de sa tâche. Échéance à None pour un rappel de point
    d'avancement (attaché au suivi, pas à une date)."""
    for suivi in _load()["suivis"]:
        for rappel in suivi["rappels"]:
            if rappel["cron_id"] == cron_id:
                return suivi, None, rappel
        for echeance in suivi["echeances"]:
            for rappel in echeance["rappels"]:
                if rappel["cron_id"] == cron_id:
                    return suivi, echeance, rappel
    return None


def retirer_rappel_echeance(suivi_id: str, echeance_id: str, cron_id: str) -> bool:
    def _faire(_data, suivi):
        echeance = next((e for e in suivi["echeances"] if e["id"] == echeance_id), None)
        if echeance is None:
            return False
        avant = len(echeance["rappels"])
        echeance["rappels"] = [r for r in echeance["rappels"] if r["cron_id"] != cron_id]
        return len(echeance["rappels"]) < avant
    return bool(_avec_suivi(suivi_id, _faire))


def ajouter_rappel_suivi(suivi_id: str, cron_id: str, quand: str, frequence_jours: int | None) -> Rappel | None:
    def _faire(_data, suivi):
        rappel: Rappel = {"cron_id": cron_id, "type": "point_avancement", "quand": quand,
                           "echeance_id": None, "offset_jours": None, "frequence_jours": frequence_jours}
        suivi["rappels"].append(rappel)
        return rappel
    return _avec_suivi(suivi_id, _faire)


def retirer_rappel_suivi(suivi_id: str, cron_id: str) -> bool:
    def _faire(_data, suivi):
        avant = len(suivi["rappels"])
        suivi["rappels"] = [r for r in suivi["rappels"] if r["cron_id"] != cron_id]
        return len(suivi["rappels"]) < avant
    return bool(_avec_suivi(suivi_id, _faire))


# ── résultats (fiches/exos générés) ───────────────────────────────────

def ajouter_resultat(
    type: str, fichier: str, ressources_utilisees: list[str] | None = None,
    ressources_manquantes: list[str] | None = None, suivi_id: str | None = None,
    echeance_id: str | None = None, parametres: dict | None = None,
) -> Resultat:
    resultat: Resultat = {
        "id": "gen_" + uuid.uuid4().hex[:8], "type": type, "fichier": fichier,
        "ressources_utilisees": list(ressources_utilisees or []),
        "ressources_manquantes": list(ressources_manquantes or []),
        "suivi_id": suivi_id, "echeance_id": echeance_id, "parametres": parametres or {},
        "created_at": _maintenant(),
    }
    with _LOCK:
        data = _load()
        data["resultats"].append(resultat)
        _save(data)
    return resultat


def lister_resultats(limite: int = 10, suivi_id: str | None = None) -> list[Resultat]:
    resultats = _load()["resultats"]
    if suivi_id is not None:
        resultats = [r for r in resultats if r.get("suivi_id") == suivi_id]
    return sorted(resultats, key=lambda r: r.get("created_at", ""), reverse=True)[:limite]


def obtenir_resultat(resultat_id: str) -> Resultat | None:
    return next((r for r in _load()["resultats"] if r["id"] == resultat_id), None)


def rattacher_resultat(resultat_id: str, suivi_id: str) -> Resultat | None:
    """Rattache un résultat de travail rapide (§3) à un suivi après coup —
    le fichier ne bouge pas, seule la référence change."""
    with _LOCK:
        data = _load()
        resultat = next((r for r in data["resultats"] if r["id"] == resultat_id), None)
        if resultat is None or not any(s["id"] == suivi_id for s in data["suivis"]):
            return None
        resultat["suivi_id"] = suivi_id
        _save(data)
        return resultat


# ── vérifications (§11) ───────────────────────────────────────────────

def ajouter_verification(
    suivi_id: str, ressources_inspectees: list[str], elements_presents: list[str],
    exigences_couvertes: list[str], elements_manquants: list[str],
    points_non_verifiables: list[str], preuves: list[str], texte: str,
) -> Verification | None:
    def _faire(_data, suivi):
        verification: Verification = {
            "id": "verif_" + uuid.uuid4().hex[:8], "date": _maintenant(),
            "ressources_inspectees": list(ressources_inspectees),
            "elements_presents": list(elements_presents),
            "exigences_couvertes": list(exigences_couvertes),
            "elements_manquants": list(elements_manquants),
            "points_non_verifiables": list(points_non_verifiables),
            "preuves": list(preuves), "texte": texte,
        }
        suivi["verifications"].append(verification)
        return verification
    return _avec_suivi(suivi_id, _faire)


def lister_verifications(suivi_id: str, limite: int = 5) -> list[Verification]:
    suivi = obtenir_suivi(suivi_id)
    if suivi is None:
        return []
    return sorted(suivi["verifications"], key=lambda v: v.get("date", ""), reverse=True)[:limite]


# ── générations (fiche/exo) en cours ────────────────────────────────────
# Collection À PART, même raison que `resultats` (voir `GenerationTache` dans
# `type.py`) : persistée plutôt que gardée en mémoire du processus, pour que
# changer d'onglet ou se reconnecter à l'île retrouve l'état réel (§1, lot 3).

def generation_active(suivi_id: str | None, type: str) -> GenerationTache | None:
    """Une génération encore `en_cours` pour CE (suivi_id, type) — appelée
    avant de démarrer un nouveau travail pour refuser un doublon."""
    return next(
        (g for g in _load()["generations"]
         if g["statut"] == "en_cours" and g["suivi_id"] == suivi_id and g["type"] == type),
        None,
    )


def demarrer_generation(suivi_id: str | None, type: str, parametres: dict | None = None) -> GenerationTache:
    generation: GenerationTache = {
        "id": "task_" + uuid.uuid4().hex[:8], "type": type, "suivi_id": suivi_id,
        "statut": "en_cours", "resultat_id": None, "erreur": None,
        "parametres": parametres or {}, "started_at": _maintenant(), "finished_at": None,
    }
    with _LOCK:
        data = _load()
        data["generations"].append(generation)
        _save(data)
    return generation


def terminer_generation(generation_id: str, resultat_id: str) -> GenerationTache | None:
    with _LOCK:
        data = _load()
        generation = next((g for g in data["generations"] if g["id"] == generation_id), None)
        if generation is None:
            return None
        generation["statut"] = "terminee"
        generation["resultat_id"] = resultat_id
        generation["finished_at"] = _maintenant()
        _save(data)
        return generation


def echouer_generation(generation_id: str, erreur: str) -> GenerationTache | None:
    with _LOCK:
        data = _load()
        generation = next((g for g in data["generations"] if g["id"] == generation_id), None)
        if generation is None:
            return None
        generation["statut"] = "echouee"
        generation["erreur"] = erreur
        generation["finished_at"] = _maintenant()
        _save(data)
        return generation


def obtenir_generation(generation_id: str) -> GenerationTache | None:
    return next((g for g in _load()["generations"] if g["id"] == generation_id), None)


def derniere_generation(suivi_id: str | None, type: str) -> GenerationTache | None:
    """La plus récente génération (en cours, terminée ou échouée) pour ce
    (suivi_id, type) — c'est elle qui détermine l'état affiché par l'île
    après un changement d'onglet ou une reconnexion (§1)."""
    candidates = [g for g in _load()["generations"] if g["suivi_id"] == suivi_id and g["type"] == type]
    if not candidates:
        return None
    return max(candidates, key=lambda g: g["started_at"])


def purger_generations_bloquees() -> int:
    """À appeler une fois au démarrage du CLI. Toute génération encore
    `en_cours` à ce moment n'a pas pu terminer dans CE processus — le
    précédent est mort sans mettre à jour son statut (crash, kill, coupure de
    courant). Marquée `echouee` plutôt que laissée `en_cours` indéfiniment,
    ce qui bloquerait silencieusement tout nouveau lancement via
    `generation_active` (§1 « redémarrage pendant une génération »).

    Renvoie le nombre de générations ainsi purgées."""
    with _LOCK:
        data = _load()
        purgees = 0
        for generation in data["generations"]:
            if generation["statut"] == "en_cours":
                generation["statut"] = "echouee"
                generation["erreur"] = "Interrompue par un redémarrage."
                generation["finished_at"] = _maintenant()
                purgees += 1
        if purgees:
            _save(data)
        return purgees
