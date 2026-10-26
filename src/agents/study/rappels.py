"""Ce qu'Axon dit des études EN DEHORS d'une conversation : notifications
envoyées par le daemon cron (`src/cron_daemon.py`), qui ne fait que décider
QUAND les envoyer — le contenu se décide ici, à partir du store.

Deux textes :
- un rappel d'échéance manqué (PC éteint ou daemon arrêté à l'heure prévue),
  affiché avec son vrai contenu plutôt qu'un « tâche manquée » générique ;
- le récapitulatif du jour : prochaines échéances et état des dépôts liés.
"""
from __future__ import annotations

from ._aide import date_courte, etat_depot, jours_restants, temps_restant_texte

#: Fenêtre du récapitulatif : au-delà, une échéance n'appelle rien aujourd'hui.
HORIZON_RECAP_JOURS = 14
#: Au-delà, une échéance en retard n'est plus rappelée chaque matin.
HORIZON_RETARD_JOURS = 30
#: Une notification bureau reste lisible en quelques lignes.
LIGNES_MAX = 6


def echeance_du_rappel(cron_id: str) -> tuple[dict, dict] | None:
    """(suivi, échéance) d'un rappel d'échéance encore pertinent — None si la
    tâche n'est pas un rappel d'études, ou si l'échéance est passée ou
    annulée (prévenir après coup n'aurait plus de sens)."""
    from .store import trouver_rappel

    trouve = trouver_rappel(cron_id)
    if trouve is None:
        return None
    suivi, echeance, _rappel = trouve
    if echeance is None or echeance.get("statut") == "annulee":
        return None
    if jours_restants(echeance["date"]) < 0:
        return None
    return suivi, echeance


def contexte_echeance(suivi: dict, echeance: dict) -> dict:
    """Ce que l'île doit savoir d'un rappel d'échéance pour proposer ses actions."""
    return {"genre": "echeance", "suivi_id": suivi["id"], "echeance_id": echeance["id"]}


def texte_rappel_manque(suivi: dict, echeance: dict) -> tuple[str, str]:
    titre = f"Axon · {echeance['titre']}"
    corps = (f"{suivi['titre']} — {temps_restant_texte(echeance['date'])} "
             f"(le {date_courte(echeance['date'])}). Rappel prévu pendant que l'ordinateur était éteint.")
    return titre, corps


def recap_du_jour() -> tuple[str, str] | None:
    """Prochaines échéances (14 jours) et état des dépôts Git liés aux suivis
    actifs. None s'il n'y a rien à dire : pas de notification vide."""
    from .store import lister_echeances, lister_suivis, obtenir_ressource

    lignes = []
    # En retard d'abord : une échéance passée encore « à venir » n'a été ni
    # rendue ni reportée — c'est elle qu'il ne faut pas laisser filer en silence.
    for suivi, echeance in lister_echeances(a_venir_seulement=False):
        retard = -jours_restants(echeance["date"])
        if echeance.get("statut") != "a_venir" or not 0 < retard <= HORIZON_RETARD_JOURS:
            continue
        lignes.append(f"• {echeance['titre']} ({suivi['titre']}) — en retard de {retard} j")
    for suivi, echeance in lister_echeances(a_venir_seulement=True):
        if echeance.get("statut") == "annulee" or jours_restants(echeance["date"]) > HORIZON_RECAP_JOURS:
            continue
        lignes.append(f"• {echeance['titre']} ({suivi['titre']}) — {temps_restant_texte(echeance['date'])}")

    depots_vus = set()
    for suivi in lister_suivis():
        for rid in suivi["ressources"]:
            ressource = obtenir_ressource(rid)
            if ressource is None or ressource["type"] != "depot_git" or ressource["chemin"] in depots_vus:
                continue
            depots_vus.add(ressource["chemin"])
            etat = etat_depot(ressource["chemin"])
            if etat is None:
                lignes.append(f"• {ressource['nom']} : dépôt injoignable")
                continue
            ligne = f"• {ressource['nom']} : {etat['branche']}, dernier commit {etat['age']}"
            if etat["modifies"]:
                ligne += f", {etat['modifies']} fichier(s) non commité(s)"
            lignes.append(ligne)

    if not lignes:
        return None
    if len(lignes) > LIGNES_MAX:
        lignes = lignes[:LIGNES_MAX - 1] + [f"… et {len(lignes) - LIGNES_MAX + 1} autre(s)"]
    return "Axon · Études", "\n".join(lignes)
