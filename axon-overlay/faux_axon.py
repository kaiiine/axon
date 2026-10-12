#!/usr/bin/env python3
"""Un faux Axon pour tester l'overlay sans lancer le vrai agent.

1. Lance l'overlay.
2. Lance ce script : il joue une petite session, demande une confirmation,
   puis affiche dans le terminal ce que tu tapes dans l'overlay.
"""
import time

from pont_axon import PontOverlay

pont = PontOverlay()
if not pont.connecter():
    raise SystemExit("Overlay introuvable : lance d'abord overlay.py")

pont.etat("thinking", "lit ta demande")
time.sleep(1.5)
pont.outil("web_research_report", "gtk4 layer shell python")
time.sleep(1.5)
pont.outil("read_file", "src/llm/backends.py")
time.sleep(1.2)

reponses = pont.demander({"genre": "autorisation", "apercu": "python -m compileall -q . (simulation)", "questions": [{"texte": "Autoriser la vérification simulée ?", "choix": ["Autoriser", "Refuser"], "affirmatif": "Autoriser"}]})
decision = None if reponses is None else reponses == ["Autoriser"]
if decision is None:
    decision = input("Pas de réponse dans l'overlay. Autoriser la vérification simulée ? [o/N] ").lower() == "o"
print("Décision :", "autorisé" if decision else "refusé")

if decision:
    pont.outil("shell_run", "python -m compileall -q . (simulé, rien n’est exécuté)")
    time.sleep(1)
pont.etat("finished", "session de test terminée")

print("Tape quelque chose dans l'overlay (Ctrl+C pour quitter).")
try:
    while True:
        texte = pont.commandes.get()
        print("Reçu de l'overlay :", texte)
        pont.etat("thinking", texte)
        time.sleep(1)
        pont.message(f"(simulation) j'ai bien reçu « {texte} »")
        pont.etat("finished", "réponse envoyée")
except KeyboardInterrupt:
    pass
