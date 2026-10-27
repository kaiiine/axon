"""Résumé IA d'un suivi : un appel LLM qui lit le projet dans sa globalité
(détail du suivi, dépôts Git, sujet) et l'explique, en flux.

Diffusé morceau par morceau à l'île (`src/ui/flux_overlay.py`) ; le texte
complet est gardé dans le suivi pour s'afficher tout de suite à la prochaine
ouverture de la page projet.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

#: Bornes du contexte : assez pour comprendre un projet, pas assez pour
#: exploser le budget d'un appel qu'on relance d'un clic.
README_MAX = 2500
DOCUMENT_MAX = 4000
DOCUMENTS_MAX = 2
FICHIERS_RACINE_MAX = 40

CONSIGNE = """Tu es Axon. Explique ce projet à son auteur, en français, en Markdown concis (180 mots maximum) :

**En bref** — ce que fait le projet, en une ou deux phrases.
**Où ça en est** — d'après les commits récents, les tâches, les exercices et la dernière vérification.
**À faire ensuite** — deux ou trois actions concrètes, en tenant compte des échéances.

N'invente rien qui ne figure pas dans le contexte. S'il manque une information utile (pas de sujet, pas d'échéance, pas de tâches), dis-le en une phrase plutôt que de deviner.

Contexte :

{contexte}"""


def _extrait_document(chemin: str) -> str:
    p = Path(chemin)
    if not p.is_file():
        return ""
    try:
        if p.suffix.lower() == ".pdf":
            from src.ui.attachments import _extract_pdf
            texte = _extract_pdf(p)
        else:
            texte = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return texte[:DOCUMENT_MAX]


def _contexte_depot(nom: str, chemin: str) -> str:
    from ._aide import depuis_combien_de_temps, derniers_commits, etat_depot

    racine = Path(chemin)
    if not racine.is_dir():
        return f"## Dépôt {nom}\nInjoignable ({chemin})."
    # L'historique Git est un plus : s'il est illisible, README et SPEC
    # restent les meilleures sources sur ce que le projet doit faire.
    etat = etat_depot(chemin)
    if etat is None:
        lignes = [f"## Dépôt {nom} — historique Git illisible"]
    else:
        lignes = [f"## Dépôt {nom} — branche {etat['branche']}, {etat['modifies']} fichier(s) non commité(s)"]
    commits = derniers_commits(chemin)
    if commits:
        lignes.append("Derniers commits :")
        for horodatage, sujet in commits:
            lignes.append(f"- {depuis_combien_de_temps(horodatage)} : {sujet}")
    entrees = sorted(p for p in racine.iterdir() if not p.name.startswith("."))
    lignes.append("Racine : " + ", ".join(p.name for p in entrees[:FICHIERS_RACINE_MAX]))
    # README (toute casse : README.MD, readme.md…) et SPEC à la racine : ce
    # sont eux qui disent ce que le projet doit faire.
    for prefixe, libelle in (("readme", "README"), ("spec", "Spécification")):
        fichier = next((p for p in entrees if p.is_file() and p.name.lower().startswith(prefixe)), None)
        if fichier is not None:
            extrait = fichier.read_text(encoding="utf-8", errors="replace")[:README_MAX]
            lignes.append(f"{libelle} — {fichier.name} (extrait) :\n{extrait}")
    return "\n".join(lignes)


def contexte_suivi(suivi_id: str) -> str | None:
    """Tout ce que le LLM doit savoir du suivi — None s'il n'existe pas."""
    from .store import obtenir_ressource, obtenir_suivi
    from .tools_suivi import etude_detail_suivi

    suivi = obtenir_suivi(suivi_id)
    if suivi is None:
        return None
    parties = [f"# Projet : {suivi['titre']}", etude_detail_suivi.invoke({"suivi_id": suivi_id})]
    documents = 0
    for rid in suivi["ressources"]:
        ressource = obtenir_ressource(rid)
        if ressource is None or not ressource.get("accessible", True):
            continue
        if ressource["type"] == "depot_git":
            parties.append(_contexte_depot(ressource["nom"], ressource["chemin"]))
        elif ressource["type"] == "document" and documents < DOCUMENTS_MAX:
            extrait = _extrait_document(ressource["chemin"])
            if extrait:
                parties.append(f"## Document : {ressource['nom']} (extrait)\n{extrait}")
                documents += 1
    return "\n\n".join(parties)


def _texte(contenu) -> str:
    """Gemini rend parfois une liste de blocs plutôt qu'une chaîne."""
    if isinstance(contenu, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in contenu)
    return contenu or ""


def flux_resume_suivi(suivi_id: str) -> Iterator[str]:
    """Rend le résumé morceau par morceau, puis l'enregistre dans le suivi.

    Rotation de clés comme `tools._generer_via_skill` : une clé épuisée passe
    à la suivante — mais seulement AVANT le premier morceau. Une fois du texte
    affiché, changer de fournisseur le dupliquerait : l'erreur remonte."""
    from langchain_core.messages import HumanMessage

    from src.infra.settings import settings
    from src.llm.models import make_orchestrator_llm_with_key
    from src.llm.rotation import clients, marquer_echec, vaut_la_peine_de_reessayer
    from .store import enregistrer_resume

    contexte = contexte_suivi(suivi_id)
    if contexte is None:
        raise ValueError(f"Suivi introuvable : {suivi_id}")
    message = HumanMessage(content=CONSIGNE.format(contexte=contexte))

    derniere: Exception | None = None
    for fournisseur, cle, llm in clients(settings.llm_backend, make_orchestrator_llm_with_key):
        recu = ""
        try:
            for chunk in llm.stream([message]):
                morceau = _texte(chunk.content)
                # Certains fournisseurs renvoient le texte cumulé à chaque
                # morceau (même correction que `streaming._stream_message`).
                if recu and morceau.startswith(recu):
                    morceau = morceau[len(recu):]
                if morceau:
                    recu += morceau
                    yield morceau
        except Exception as exc:  # noqa: BLE001 — clé suivante, si rien n'est encore affiché
            if recu:
                raise
            derniere = exc
            marquer_echec(fournisseur, cle, exc)
            if not vaut_la_peine_de_reessayer(exc):
                break
            continue
        if recu:
            enregistrer_resume(suivi_id, recu)
            return
    raise RuntimeError(derniere or "aucun fournisseur n'a répondu")
