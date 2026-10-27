#!/usr/bin/env python
"""Le modèle charge-t-il `redaction` avant d'écrire un mail ? Trois variantes.

    base      prompt et descriptions tels que le dépôt les livre
    indice    `gmail_send_email` demande de charger `redaction` d'abord
    ref       le prompt système d'un autre fichier (`--prompt-ref`), pour comparer
              avant / après une refonte sans toucher au dépôt

Même chemin que la production : sélection d'outils, `_ensure_system_prompt`, puis
un seul tour du modèle. Verdict sur les appels du PREMIER tour :

    SKILL SEUL     `load_skill(redaction)` sans autre appel         ← attendu
    SKILL+ACTION   le skill ET l'envoi dans le même tour            ← l'envoi part sans lire
    ACTION         `gmail_send_email` sans skill
    QUESTION       `ask_clarification`
    AUTRE / TEXTE

    python outils/mesure_prompt.py --backend ollama_cloud --variante base indice
    python outils/mesure_prompt.py --backend mistral --prompt-ref /chemin/orchestrateur_avant.py
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
sys.stdout.reconfigure(line_buffering=True)

from corpus_redaction_gmail import PRET, REDACTION  # noqa: E402

INDICE = (
    "\n\nAVANT d'appeler ce tool pour écrire ou réécrire un texte : appelle d'abord "
    "load_skill(stack=\"redaction\"), seul dans ce tour, puis rédige le corps en suivant "
    "ses règles. N'appelle PAS ce tool dans le même tour que load_skill."
)


def appliquer_indice(outils: list) -> None:
    for o in outils:
        if o.name == "gmail_send_email" and INDICE not in o.description:
            o.description += INDICE


def prompt_externe(chemin: str):
    spec = importlib.util.spec_from_file_location("prompt_ref", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_system_prompt


def classer(reponse) -> str:
    noms = [a.get("name") for a in getattr(reponse, "tool_calls", None) or []]
    skills = [str((a.get("args") or {}).get("stack", "")).lower()
              for a in reponse.tool_calls if a.get("name") == "load_skill"]
    envoi = "gmail_send_email" in noms
    if "redaction" in skills:
        return "SKILL+ACTION" if envoi else "SKILL SEUL"
    if envoi:
        return "ACTION"
    if "ask_clarification" in noms:
        return "QUESTION"
    return "AUTRE" if noms else "TEXTE"


def mesurer(nom_backend: str, fabrique, variante: str, pause: float, prompt_ref: str | None) -> dict:
    from langchain_core.messages import HumanMessage

    import src.orchestrator.noeuds.chat as chat
    from outils.mesure_skills_lies import monde, selection
    from src.orchestrator.routage.catalogue import menu

    if prompt_ref:
        chat.build_system_prompt = prompt_externe(prompt_ref)
    mon = monde(True)
    resultats: dict[str, Counter] = {"REDACTION": Counter(), "PRET": Counter()}
    for famille, requetes in (("REDACTION", REDACTION), ("PRET", PRET)):
        for requete in requetes:
            liees = selection(mon, requete)
            if variante == "indice":
                appliquer_indice(liees)
            messages = chat._ensure_system_prompt([HumanMessage(content=requete)], liees,
                                                  datetime.now().strftime("%Y-%m-%d"), catalogue=menu())
            time.sleep(pause)
            try:
                verdict = classer(fabrique().bind_tools(liees).invoke(messages))
            except Exception as erreur:                       # noqa: BLE001
                print(f"   ERREUR {type(erreur).__name__}: {str(erreur)[:70]}")
                continue
            resultats[famille][verdict] += 1
            print(f"   {verdict:<13} {famille:<9} « {requete[:64]} »")
    return resultats


def main() -> None:
    parseur = argparse.ArgumentParser()
    parseur.add_argument("--backend", required=True)
    parseur.add_argument("--variante", nargs="+", default=["base"], choices=["base", "indice"])
    parseur.add_argument("--prompt-ref")
    parseur.add_argument("--pause", type=float, default=2.0)
    args = parseur.parse_args()

    import src.infra.settings  # noqa: F401
    from src.llm.backends import fabriques

    fabrique = fabriques()[args.backend]
    for variante in args.variante:
        etiquette = f"{variante}{' + prompt-ref' if args.prompt_ref else ''}"
        print(f"\n━━ {args.backend} — {etiquette} ━━")
        res = mesurer(args.backend, fabrique, variante, args.pause, args.prompt_ref)
        for famille, c in res.items():
            print(f"   → {famille:<9} " + "  ".join(f"{v} {k}" for k, v in sorted(c.items())))


if __name__ == "__main__":
    main()
