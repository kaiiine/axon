"""Raccourcis rapides pour les mini-dashboards d'intégration de l'île.

Appellent les tools de lecture d'Axon directement — pas de passage par le
graphe/LLM — pour remplir les tuiles de l'île en un clic, en une ou deux
secondes plutôt qu'un tour d'agent complet. Lecture seule par construction :
seules les actions qui ne modifient rien (Gmail, Jira, Google Calendar) sont
exposées ici. Les tools d'écriture (`gmail_send_email`, `calendar_create_event`,
`drive_delete_file`...) ne doivent jamais être ajoutés à `ACTIONS` — ils
passent par `demanderAxon` côté île, donc par le graphe complet avec sa
confirmation normale.

Deux familles d'actions, même liste blanche :
  - les actions de panneau (`gmail_non_lus`, `jira_mes_tickets`,
    `workspace_aujourdhui`) remplissent le dashboard à l'ouverture ;
  - les actions de détail (`gmail_resumer_mail`, `jira_detail_ticket`)
    sont déclenchées par un clic sur UNE ligne précise (`item` = son id),
    pour ne récupérer le contenu complet que si l'utilisateur le demande —
    aller chercher le corps de chaque mail seulement pour en afficher cinq
    lignes serait du travail perdu dans l'immense majorité des cas.
"""
from __future__ import annotations

from typing import Any, Callable

from src.agents.study._aide import date_courte


def _gmail_non_lus(_item: str | None) -> dict[str, Any]:
    from src.agents.gmail.tools import gmail_search

    texte = gmail_search.invoke({"query": "is:unread", "max_results": 5})
    if not isinstance(texte, str) or texte.startswith("📭"):
        return {"stats": [{"label": "Non lus", "value": "0", "accent": True}], "rows": []}

    rows = []
    for ligne in texte.splitlines():
        ligne = ligne.strip()
        if not ligne.startswith("|") or ligne.startswith("| #") or ligne.startswith("|---"):
            continue
        parts = [p.strip() for p in ligne.strip("|").split("|")]
        if len(parts) < 5:
            continue
        _, message_id, de, objet, date = parts[:5]
        rows.append({
            "title": objet or "(sans objet)",
            "meta": f"{de} · {date}",
            "id": message_id.strip("`"),
        })
    return {"stats": [{"label": "Non lus", "value": str(len(rows)), "accent": True}], "rows": rows}


def _gmail_resumer_mail(item: str | None) -> dict[str, Any]:
    from src.agents.gmail.tools import gmail_summarize

    if not item:
        raise ValueError("identifiant de mail manquant")
    texte = gmail_summarize.invoke({"message_id": item})
    return {"text": texte if isinstance(texte, str) else str(texte)}


def _jira_mes_tickets(_item: str | None) -> dict[str, Any]:
    from src.agents.jira.tools import jira_get_my_issues

    res = jira_get_my_issues.invoke({"limit": 5})
    if res.get("status") != "ok":
        raise RuntimeError(res.get("error") or "Jira indisponible")
    issues = res.get("issues", [])
    termines = {"done", "terminé", "terminée", "closed", "fermé"}
    en_cours = sum(1 for i in issues if (i.get("status") or "").lower() not in termines)
    rows = [
        {
            "title": f"{i.get('key')} · {i.get('summary') or ''}",
            "meta": i.get("priority") or i.get("updated") or "",
            "tag": i.get("status") or "",
            "accent": (i.get("status") or "").lower() not in termines,
            "id": i.get("key"),
        }
        for i in issues
    ]
    return {
        "stats": [
            {"label": "Assignés à toi", "value": str(res.get("count", len(issues))), "accent": True},
            {"label": "En cours", "value": str(en_cours)},
        ],
        "rows": rows,
    }


def _jira_detail_ticket(item: str | None) -> dict[str, Any]:
    from src.agents.jira.tools import jira_get_issue

    if not item:
        raise ValueError("clé de ticket manquante")
    res = jira_get_issue.invoke({"key": item})
    if res.get("status") != "ok":
        raise RuntimeError(res.get("error") or "Jira indisponible")
    issue = res.get("issue", {})
    lignes = [f"**{issue.get('status') or '?'}** · priorité {issue.get('priority') or '—'}"]
    if issue.get("assignee"):
        lignes.append(f"Assigné à {issue['assignee']}")
    if issue.get("due"):
        lignes.append(f"Échéance : {issue['due']}")
    if issue.get("description_text"):
        lignes.append("")
        lignes.append(issue["description_text"][:800])
    if issue.get("url"):
        lignes.append("")
        lignes.append(f"[Ouvrir dans Jira]({issue['url']})")
    return {"text": "\n\n".join(lignes)}


def _workspace_aujourdhui(_item: str | None) -> dict[str, Any]:
    from src.agents.google_calendar.tools import calendar_list_events

    res = calendar_list_events.invoke({"days_ahead": 1, "max_results": 6})
    if res.get("status") != "ok":
        raise RuntimeError(res.get("error") or "Google Calendar indisponible")
    events = res.get("events", [])

    def heure(e: dict) -> str:
        debut = e.get("start") or ""
        return debut[11:16] if "T" in debut else "toute la journée"

    def detail(e: dict) -> str | None:
        # Déjà dans la réponse de calendar_list_events — pas besoin d'un
        # aller-retour supplémentaire pour afficher le détail d'un événement.
        morceaux = []
        if e.get("location"):
            morceaux.append(f"📍 {e['location']}")
        if e.get("description"):
            morceaux.append(e["description"][:500])
        return "\n\n".join(morceaux) if morceaux else None

    rows = [
        {
            "title": e.get("title") or "(sans titre)",
            "meta": heure(e),
            "tag": "Agenda",
            "accent": i == 0,
            "detail": detail(e),
        }
        for i, e in enumerate(events)
    ]
    return {
        "stats": [{"label": "Événements aujourd’hui", "value": str(len(events)), "accent": True}],
        "rows": rows,
    }


def _dossier_fiches():
    from pathlib import Path

    return Path.home() / "Documents" / "axon_fiches"


# Libellés affichés dans l'île : le store garde ses clés internes
# (`matiere`, `rendu_projet`…), l'interface ne doit jamais les montrer brutes.
_LIBELLES_SUIVI = {"matiere": "Matière", "projet": "Projet", "ponctuel": "Ponctuel", "autre": "Autre"}
_LIBELLES_ECHEANCE = {"devoir": "Devoir", "partiel": "Partiel", "rendu_projet": "Rendu", "autre": "Autre"}
_LIBELLES_RESULTAT = {"fiche": "Fiche", "exo": "Exercices"}


def _champs_generation(suivi_id: str | None) -> dict[str, Any]:
    """Statut de génération fiche/exo pour ce suivi (`None` = travail rapide)
    — alimente les boutons « Génération en cours »/« Ouvrir le résultat »/
    « Réessayer » de l'île (§1, lot 3). Seulement les champs dont on a une
    vraie valeur : une génération jamais lancée ne doit ajouter aucune clé,
    plutôt que `None` partout, pour que le frontend distingue "jamais lancé"
    de "statut inconnu"."""
    from src.agents.study.store import derniere_generation, obtenir_resultat

    champs: dict[str, Any] = {}
    for type_gen, prefixe in (("fiche", "generationFiche"), ("exo", "generationExo")):
        generation = derniere_generation(suivi_id, type_gen)
        if generation is None:
            continue
        champs[f"{prefixe}Statut"] = generation["statut"]
        if generation["statut"] == "terminee" and generation["resultat_id"]:
            resultat = obtenir_resultat(generation["resultat_id"])
            if resultat:
                champs[f"{prefixe}Fichier"] = resultat["fichier"]
    return champs


def _etudes_fiches_recentes(_item: str | None) -> dict[str, Any]:
    """Source principale : `store.lister_resultats()` (type, suivi, sources
    réelles). Complété — sans doublon — par un scan du dossier pour les
    fichiers générés avant ce câblage, jamais enregistrés dans le store."""
    from datetime import datetime
    from pathlib import Path
    from src.agents.study.store import lister_resultats

    resultats = lister_resultats(limite=10)
    connus = {r["fichier"] for r in resultats}
    rows = [
        {"title": Path(r["fichier"]).stem,
         "meta": f"{date_courte(r['created_at'])} {r['created_at'][11:16]}".strip(),
         "tag": _LIBELLES_RESULTAT.get(r["type"], r["type"]), "id": r["fichier"]}
        for r in resultats
    ]
    dossier = _dossier_fiches()
    if dossier.is_dir() and len(rows) < 10:
        autres = sorted(
            (f for f in dossier.glob("*.html") if f.name not in connus),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )[: 10 - len(rows)]
        for f in autres:
            modifie = datetime.fromtimestamp(f.stat().st_mtime)
            type_fichier = f.stem.split("_", 1)[0]
            rows.append({
                "title": f.stem,
                "meta": f"{date_courte(modifie.date().isoformat())} {modifie:%H:%M}",
                "tag": _LIBELLES_RESULTAT.get(type_fichier, ""),
                "id": f.name,
            })
    return {"stats": [{"label": "Récents", "value": str(len(rows)), "accent": True}], "rows": rows,
            **_champs_generation(None)}


def _etudes_suivis(_item: str | None) -> dict[str, Any]:
    from src.agents.study.store import lister_suivis

    suivis = lister_suivis(archives=False)
    rows = []
    for s in suivis:
        a_venir = sorted((e for e in s["echeances"] if e.get("statut") == "a_venir"),
                          key=lambda e: e.get("date", ""))
        morceaux = []
        if a_venir:
            morceaux.append(f"{a_venir[0]['titre']} le {date_courte(a_venir[0]['date'])}")
        if s["exercices"]:
            termines = sum(1 for x in s["exercices"] if x.get("statut") == "termine")
            morceaux.append(f"{termines}/{len(s['exercices'])} exercices")
        nb_ressources = len(s["ressources"])
        if nb_ressources:
            morceaux.append(f"{nb_ressources} ressource" + ("s" if nb_ressources > 1 else ""))
        meta = " · ".join(morceaux) or "Aucune échéance"
        rows.append({"title": s["titre"], "meta": meta, "tag": _LIBELLES_SUIVI.get(s["type"], s["type"]),
                      "id": s["id"], **_champs_generation(s["id"])})
    return {"stats": [{"label": "Suivis actifs", "value": str(len(rows)), "accent": True}], "rows": rows}


def _etudes_echeances(_item: str | None) -> dict[str, Any]:
    from src.agents.study._aide import temps_restant_texte
    from src.agents.study.store import lister_echeances

    # `lister_echeances` ne filtre que par date : une échéance annulée depuis
    # l'île resterait sinon affichée parmi les prochaines.
    paires = [(suivi, e) for suivi, e in lister_echeances(a_venir_seulement=True)
              if e.get("statut") != "annulee"]
    rows = [
        # `suiviId` : une échéance liste son suivi parent en texte (`meta`)
        # mais l'île a besoin de son ID pour reporter/annuler (§3, lot 3) —
        # `etude_maj_echeance` prend `suivi_id` + `echeance_id`, pas
        # l'échéance seule.
        {"title": e["titre"],
         "meta": f"{suivi['titre']} · {date_courte(e['date'])}, {temps_restant_texte(e['date'])}",
         "tag": _LIBELLES_ECHEANCE.get(e["type"], e["type"]), "id": e["id"], "suiviId": suivi["id"]}
        for suivi, e in paires
    ]
    return {"stats": [{"label": "À venir", "value": str(len(rows)), "accent": True}], "rows": rows}


def _etudes_page_suivi(item: str | None) -> dict[str, Any]:
    """Tout ce que la page projet de l'île affiche, en un aller-retour : le
    suivi, ses échéances, tâches, ressources (avec l'état des dépôts),
    résultats, dernière vérification, dernier résumé IA, et les événements
    de son calendrier. Rien n'appelle de LLM ici : la page s'affiche tout de
    suite, le résumé arrive à part, en flux (`flux_overlay`)."""
    from datetime import datetime
    from src.agents.study._aide import derniers_commits, etat_depot, temps_restant_texte
    from src.agents.study.store import lister_resultats, lister_verifications, obtenir_ressource, obtenir_suivi

    if not item:
        raise ValueError("identifiant de suivi manquant")
    suivi = obtenir_suivi(item)
    if suivi is None:
        raise ValueError(f"Suivi introuvable : {item}")

    calendrier: list[dict[str, str]] = []

    echeances = []
    for e in sorted(suivi["echeances"], key=lambda e: e.get("date", "")):
        echeances.append({
            "id": e["id"], "titre": e["titre"], "type": _LIBELLES_ECHEANCE.get(e["type"], e["type"]),
            "date": e["date"], "dateCourte": date_courte(e["date"]), "restant": temps_restant_texte(e["date"]),
            "statut": e["statut"], "rappels": len(e["rappels"]),
        })
        if e["statut"] != "annulee":
            calendrier.append({"date": e["date"][:10], "libelle": e["titre"], "genre": "echeance"})
            for rappel in e["rappels"]:
                calendrier.append({"date": rappel["quand"][:10], "libelle": f"Rappel · {e['titre']}", "genre": "rappel"})

    ressources = []
    for rid in suivi["ressources"]:
        r = obtenir_ressource(rid)
        if r is None:
            continue
        ligne = {"id": r["id"], "nom": r["nom"], "type": r["type"], "chemin": r["chemin"]}
        if r["type"] == "depot_git":
            etat = etat_depot(r["chemin"])
            if etat is not None:
                ligne.update({"branche": etat["branche"], "age": etat["age"], "sujet": etat["sujet"],
                              "modifies": etat["modifies"]})
            for horodatage, sujet in derniers_commits(r["chemin"]):
                calendrier.append({"date": datetime.fromtimestamp(horodatage).date().isoformat(),
                                   "libelle": f"{r['nom']} · {sujet}", "genre": "commit"})
        ressources.append(ligne)

    resultats = []
    for res in lister_resultats(limite=8, suivi_id=item):
        resultats.append({"fichier": res["fichier"], "type": _LIBELLES_RESULTAT.get(res["type"], res["type"]),
                          "date": date_courte(res["created_at"])})
        calendrier.append({"date": res["created_at"][:10], "libelle": res["fichier"], "genre": "resultat"})

    verification = None
    verifications = lister_verifications(item, limite=1)
    if verifications:
        verification = {"date": date_courte(verifications[0]["date"]), "texte": verifications[0]["texte"]}
        calendrier.append({"date": verifications[0]["date"][:10], "libelle": "Vérification", "genre": "verification"})

    exercices = suivi["exercices"]
    page = {
        "id": suivi["id"], "titre": suivi["titre"], "type": _LIBELLES_SUIVI.get(suivi["type"], suivi["type"]),
        "description": suivi.get("description", ""),
        "echeances": echeances,
        "taches": [{"id": t["id"], "titre": t["titre"], "statut": t["statut"]} for t in suivi["taches"]],
        "exercices": {"total": len(exercices), "termines": sum(1 for x in exercices if x.get("statut") == "termine")},
        "ressources": ressources, "resultats": resultats, "verification": verification,
        "resume": suivi.get("resume"), "calendrier": sorted(calendrier, key=lambda ev: ev["date"]),
    }
    return {"page": page}


def _etudes_detail_suivi(item: str | None) -> dict[str, Any]:
    """Réutilise directement le tool `etude_detail_suivi` (même rendu
    Markdown que côté chat) — pas une seconde mise en forme qui pourrait
    diverger."""
    if not item:
        raise ValueError("identifiant de suivi manquant")
    from src.agents.study.tools_suivi import etude_detail_suivi

    return {"text": etude_detail_suivi.invoke({"suivi_id": item})}


def _etudes_ouvrir_fiche(item: str | None) -> dict[str, Any]:
    """Ouvre un fichier déjà généré par Axon dans le navigateur par défaut —
    même mécanisme que la fin de `/fiche`/`/exo` (`xdg-open`), pas une
    modification de données externes : reste dans l'esprit « lecture seule »
    du module même si ce n'est pas un GET réseau à proprement parler."""
    import subprocess

    if not item:
        raise ValueError("nom de fichier manquant")
    chemin = _dossier_fiches() / item
    if not chemin.is_file():
        raise FileNotFoundError(f"{item} introuvable")
    subprocess.Popen(["xdg-open", str(chemin)])
    return {"text": f"Ouvert dans le navigateur : **{item}**"}


#: Liste blanche volontairement explicite : seule une action listée ici peut
#: être déclenchée par l'île, et chacune est lecture seule (voir docstring).
ACTIONS: dict[str, Callable[[str | None], dict[str, Any]]] = {
    "gmail_non_lus": _gmail_non_lus,
    "gmail_resumer_mail": _gmail_resumer_mail,
    "jira_mes_tickets": _jira_mes_tickets,
    "jira_detail_ticket": _jira_detail_ticket,
    "workspace_aujourdhui": _workspace_aujourdhui,
    "etudes_fiches_recentes": _etudes_fiches_recentes,
    "etudes_ouvrir_fiche": _etudes_ouvrir_fiche,
    "etudes_suivis": _etudes_suivis,
    "etudes_echeances": _etudes_echeances,
    "etudes_detail_suivi": _etudes_detail_suivi,
    "etudes_page_suivi": _etudes_page_suivi,
}


def executer(action: str, item: str | None = None) -> dict[str, Any]:
    """Exécute une action connue. Lève si l'action est inconnue ou échoue —
    à l'appelant (voir `app.py`) de transformer ça en `raccourci_erreur`."""
    fonction = ACTIONS.get(action)
    if fonction is None:
        raise ValueError(f"action inconnue : {action}")
    return fonction(item)
