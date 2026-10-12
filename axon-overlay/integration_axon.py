"""Exemple de branchement dans Axon.

Ce fichier n'est pas exécutable tel quel : les noms (graphe, demander_dans_le_cli,
accorder...) sont à adapter à ton code. Il montre les deux points d'accroche.
"""
import asyncio

from pont_axon import PontOverlay

pont = PontOverlay()
pont.connecter()  # sans effet si l'overlay n'est pas lancé : Axon marche comme avant


# 1) Relayer l'activité du graphe ---------------------------------------------
# astream_events (version v2) émet un événement pour chaque appel de modèle et
# chaque outil. Tu les traduis en états de la mascotte.

def resumer(entree) -> str:
    if isinstance(entree, dict):
        for cle in ("command", "commande", "query", "path", "url"):
            if cle in entree:
                return str(entree[cle])
    return str(entree)[:120]


async def executer_tour(graphe, entree, config):
    pont.etat("thinking", "lit ta demande")
    try:
        async for ev in graphe.astream_events(entree, config, version="v2"):
            genre = ev["event"]
            if genre == "on_chat_model_start":
                pont.etat("thinking", "réfléchit")
            elif genre == "on_tool_start":
                pont.outil(ev["name"], resumer(ev["data"].get("input")))
            elif genre == "on_tool_end":
                pont.etat("thinking", f"{ev['name']} terminé")
        pont.etat("finished", "réponse prête")
    except Exception as erreur:
        pont.etat("erreur", type(erreur).__name__)
        raise


# 2) N'importe quelle demande HITL : l'overlay d'abord, le CLI en repli --------
# À placer là où ton graphe sert une `Demande` (autorisation, clarification,
# diff, plan, envoi — cf. hitl.py). La décision vient toujours d'un humain :
# l'overlay ou le CLI, jamais le modèle. C'est exactement ce que fait
# `_servir_demande_pont` dans src/ui/streaming.py, en vrai.

async def servir(demande_en_clair: dict) -> list[str]:
    reponses = await asyncio.to_thread(pont.demander, demande_en_clair)
    if reponses is None:                      # overlay absent ou sans réponse
        reponses = await servir_dans_le_cli(demande_en_clair)   # ton questionnaire actuel
    return reponses


# 3) Commandes tapées dans l'overlay ------------------------------------------
# Elles arrivent dans pont.commandes. Tu les traites comme une saisie du CLI :
# une ligne qui commence par « / » part vers tes commandes (/debug, /mcp, /undo...),
# le reste devient un message pour l'agent.

async def boucle_commandes(traiter_saisie):
    while True:
        texte = await asyncio.to_thread(pont.commandes.get)
        await traiter_saisie(texte)          # même fonction que pour le CLI


# Nom à remplacer par le tien (le questionnaire CLI existant, cf. review.py) :
async def servir_dans_le_cli(demande_en_clair: dict) -> list[str]: ...
