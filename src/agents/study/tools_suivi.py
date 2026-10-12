"""Outils `etude_*` pour la racine du modèle : le suivi lui-même, ses
ressources associées, et ce qu'il a produit (résultats de génération).

Pas les échéances (`tools_echeance.py`), pas les exercices/tâches
(`tools_progression.py`) : ici, c'est la gestion du suivi en tant
qu'espace — le créer, le retrouver, y associer ou retirer une ressource,
retrouver ce qui en est sorti.
"""
from __future__ import annotations

from langchain_core.tools import tool

from ._aide import TYPES_RESSOURCE, TYPES_SUIVI, avancement_exercices, resoudre_git, temps_restant_texte


# ── suivis ───────────────────────────────────────────────────────────────

@tool("etude_creer_suivi")
def etude_creer_suivi(titre: str, type: str, matiere: str = "", description: str = "") -> str:
    """
    Crée un espace de suivi — PAS forcément un contrôle avec une date : une
    matière, une préparation de partiel, un projet (dépôt + sujet), ou un
    travail ponctuel qu'on veut juste conserver (deux PDF à exploiter, par
    exemple). N'ajoute une échéance (`etude_ajouter_echeance`) que si
    l'utilisateur en mentionne vraiment une.

    Mots-clés : suivi, matière, projet, espace de travail, organiser,
    conserver, dossier de révision.

    **Args:**
        - `titre` (str)
        - `type` (str) : "matiere", "projet", "ponctuel" ou "autre"
        - `matiere` (str, optionnel) : texte libre, si pertinent
        - `description` (str, optionnel)

    **Returns:**
        - Confirmation avec l'identifiant du suivi.
    """
    from .store import creer_suivi

    if type not in TYPES_SUIVI:
        return f"Type inconnu : {type}. Attendu : {', '.join(TYPES_SUIVI)}."
    suivi = creer_suivi(titre, type, matiere, description)
    return f"Suivi créé : **{titre}** ({type}).\nID : `{suivi['id']}`"


@tool("etude_lister_suivis")
def etude_lister_suivis(archives: bool = False) -> str:
    """
    Liste les suivis (matières, projets, travaux ponctuels) avec un aperçu :
    prochaine échéance, avancement des exercices. Utilise ce tool pour « mes
    projets en cours », « qu'est-ce que je suis en train de préparer ? ».

    Mots-clés : suivis, matières, projets, mes espaces, mes travaux.

    **Args:**
        - `archives` (bool) : False (défaut) pour les suivis actifs, True
          pour les archivés.

    **Returns:**
        - Liste Markdown, ou message si vide.
    """
    from .store import lister_suivis

    suivis = lister_suivis(archives=archives)
    if not suivis:
        return "Aucun suivi archivé." if archives else "Aucun suivi pour l’instant."
    lignes = []
    for s in suivis:
        a_venir = sorted((e for e in s["echeances"] if e.get("statut") == "a_venir"),
                          key=lambda e: e.get("date", ""))
        prochaine = (f" · prochaine échéance : {a_venir[0]['titre']} ({temps_restant_texte(a_venir[0]['date'])})"
                     if a_venir else "")
        lignes.append(f"- **{s['titre']}** ({s['type']}) · {avancement_exercices(s['exercices'])}"
                       f"{prochaine} · `{s['id']}`")
    return "\n".join(lignes)


@tool("etude_detail_suivi")
def etude_detail_suivi(suivi_id: str) -> str:
    """
    Donne le détail complet d'un suivi : ressources associées, échéances,
    exercices avec leur statut, tâches, historique et résultats générés.
    Relis ce détail avant de proposer une prochaine action ou de faire un
    point.

    Mots-clés : détail, suivi, ressources, fiche de suivi.

    **Args:**
        - `suivi_id` (str)

    **Returns:**
        - Fiche Markdown complète, ou erreur si l'ID est inconnu.
    """
    from .store import obtenir_suivi, obtenir_ressource, lister_resultats

    s = obtenir_suivi(suivi_id)
    if s is None:
        return f"Suivi introuvable : {suivi_id}"
    lignes = [f"# {s['titre']} ({s['type']})"]
    if s["description"]:
        lignes.append(s["description"])

    if s["ressources"]:
        lignes.append("\n**Ressources :**")
        for rid in s["ressources"]:
            r = obtenir_ressource(rid)
            if r is None:
                continue
            etat = "" if r["accessible"] else f" ⚠️ inaccessible : {r['message_erreur']}"
            lignes.append(f"- [{r['type']}] **{r['nom']}** (`{r['id']}`){etat}")
    else:
        lignes.append("\n_Aucune ressource associée._")

    if s["echeances"]:
        lignes.append("\n**Échéances :**")
        for e in s["echeances"]:
            lignes.append(f"- **{e['titre']}** — {e['date']} ({temps_restant_texte(e['date'])}, "
                           f"{e['statut']}) · `{e['id']}`")

    lignes.append(f"\n**Exercices** ({avancement_exercices(s['exercices'])}) :")
    if s["exercices"]:
        for x in s["exercices"]:
            lignes.append(f"- [{x['statut']}] **{x['titre']}** (`{x['id']}`)"
                           + (f" — {x['description']}" if x["description"] else ""))
            for d in x["difficultes"][-3:]:
                lignes.append(f"  - ⚠️ {d['texte']}")
    else:
        lignes.append("_Aucun exercice._")

    if s["taches"]:
        lignes.append("\n**Tâches :**")
        for t in s["taches"]:
            lignes.append(f"- [{t['statut']}] {t['titre']} (`{t['id']}`)")

    resultats = lister_resultats(limite=5, suivi_id=suivi_id)
    if resultats:
        lignes.append("\n**Résultats récents :**")
        for r in resultats:
            lignes.append(f"- [{r['type']}] {r['fichier']} ({r['created_at'][:10]})")

    if s["verifications"]:
        lignes.append("\n**Dernières vérifications :**")
        for v in sorted(s["verifications"], key=lambda x: x.get("date", ""), reverse=True)[:3]:
            lignes.append(f"- {v['date'][:10]} — {len(v['exigences_couvertes'])} couvertes, "
                           f"{len(v['elements_manquants'])} manquantes, "
                           f"{len(v['points_non_verifiables'])} non vérifiables · `{v['id']}`")

    if s["historique"]:
        lignes.append("\n**Historique :**")
        for p in s["historique"][-10:]:
            lignes.append(f"- {p['date'][:10]} ({p['origine']}) — {p['texte']}")

    return "\n".join(lignes)


@tool("etude_archiver_suivi")
def etude_archiver_suivi(suivi_id: str, archive: bool = True) -> str:
    """
    Archive ou réactive un suivi — le sort de la liste active sans rien
    supprimer (ressources, échéances, exercices, historique restent
    consultables).

    **Args:**
        - `suivi_id` (str)
        - `archive` (bool) : True pour archiver (défaut), False pour
          réactiver.

    **Returns:**
        - Confirmation, ou erreur si le suivi est introuvable.
    """
    from .store import archiver_suivi

    s = archiver_suivi(suivi_id, archive)
    if s is None:
        return f"Suivi introuvable : {suivi_id}"
    return f"Suivi **{s['titre']}** {'archivé' if archive else 'réactivé'}."


# ── ressources ───────────────────────────────────────────────────────────

@tool("etude_associer_ressource")
def etude_associer_ressource(
    suivi_id: str, type: str, nom: str, chemin: str, provenance: str = "chemin_externe",
) -> str:
    """
    Associe une ressource à un suivi : un document (PDF/Office), un dossier
    local, un dépôt Git (local ou distant), ou un lien. Pour un dépôt Git
    local, la branche et le commit courants sont détectés automatiquement.

    La MÊME ressource peut être associée à plusieurs suivis sans dupliquer
    quoi que ce soit — si elle existe déjà pour ce chemin, elle est
    réutilisée plutôt que recréée (vérifie d'abord avec `etude_detail_suivi`
    si tu n'es pas sûr qu'elle existe déjà).

    Mots-clés : associer, ajouter ressource, dépôt, repo, git, dossier,
    projet, document, sujet, lien.

    **Args:**
        - `suivi_id` (str)
        - `type` (str) : "document", "dossier", "depot_git" ou "lien"
        - `nom` (str) : nom lisible
        - `chemin` (str) : chemin local absolu ou URL
        - `provenance` (str) : "chemin_externe" (défaut, fichier/dossier/dépôt
          local référencé — jamais copié ni modifié), "copie" (un fichier
          qu'Axon a lui-même généré/copié, ex. une fiche), ou "distant"
          (dépôt/lien hébergé ailleurs)

    **Returns:**
        - Confirmation avec l'identifiant de la ressource.
    """
    from .store import ajouter_ressource, associer_ressource, obtenir_suivi

    if obtenir_suivi(suivi_id) is None:
        return f"Suivi introuvable : {suivi_id}"
    if type not in TYPES_RESSOURCE:
        return f"Type inconnu : {type}. Attendu : {', '.join(TYPES_RESSOURCE)}."

    extra = {}
    if type == "depot_git" and provenance != "distant":
        extra = resoudre_git(chemin)

    ressource = ajouter_ressource(type=type, nom=nom, provenance=provenance, chemin=chemin, **extra)
    associer_ressource(suivi_id, ressource["id"])
    detail = f" (branche {extra['branche']}, {extra['commit']})" if extra.get("branche") else ""
    return f"Ressource associée : **{nom}**{detail}.\nID : `{ressource['id']}`"


@tool("etude_retirer_ressource")
def etude_retirer_ressource(suivi_id: str, ressource_id: str) -> str:
    """
    Retire une ressource d'UN suivi — ne supprime ni le fichier original, ni
    ses associations à d'autres suivis.

    **Args:**
        - `suivi_id`, `ressource_id` (str)

    **Returns:**
        - Confirmation, ou message si l'association n'existait pas.
    """
    from .store import retirer_ressource

    ok = retirer_ressource(suivi_id, ressource_id)
    return "Ressource retirée de ce suivi." if ok else "Cette ressource n’était pas associée à ce suivi."


# ── résultats (fiches/exos générés, voir aussi save_study_file) ─────

@tool("etude_resultats_recents")
def etude_resultats_recents(limite: int = 10, suivi_id: str | None = None) -> str:
    """
    Liste les derniers résultats générés (fiches, exercices) — tous suivis
    confondus, ou pour un suivi précis. Un résultat généré hors de tout
    suivi (travail rapide) apparaît avec « non rattaché ».

    Mots-clés : résultats, fiches récentes, exercices récents, travaux
    récents, mes fiches.

    **Args:**
        - `limite` (int)
        - `suivi_id` (str, optionnel)

    **Returns:**
        - Liste Markdown, la plus récente en premier.
    """
    from .store import lister_resultats

    resultats = lister_resultats(limite=limite, suivi_id=suivi_id)
    if not resultats:
        return "Aucun résultat pour l’instant."
    lignes = []
    for r in resultats:
        cible = r["suivi_id"] or "non rattaché"
        lignes.append(f"- [{r['type']}] **{r['fichier']}** ({r['created_at'][:10]}) · suivi : {cible} "
                       f"· `{r['id']}`")
    return "\n".join(lignes)


@tool("etude_rattacher_resultat")
def etude_rattacher_resultat(resultat_id: str, suivi_id: str) -> str:
    """
    Rattache un résultat généré sans suivi (travail rapide, §3) à un suivi
    existant, après coup — le fichier ne bouge pas.

    **Args:**
        - `resultat_id`, `suivi_id` (str)

    **Returns:**
        - Confirmation, ou erreur si l'un des identifiants est inconnu.
    """
    from .store import rattacher_resultat

    r = rattacher_resultat(resultat_id, suivi_id)
    if r is None:
        return f"Résultat ou suivi introuvable ({resultat_id} / {suivi_id})."
    return f"Résultat **{r['fichier']}** rattaché au suivi `{suivi_id}`."
