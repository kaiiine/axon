#!/usr/bin/env python
"""`load_skill` toujours lié : avant / après, hors ligne puis sur le vrai modèle.

Hors ligne (défaut), sur le jeu de `tests/corpus_skills_lies.py`, une fois le
drapeau `skills_toujours_lies` à False (« avant »), une fois à True (« après ») :

    skill proposé    `load_skill` est lié, par famille de skill
    actions gardées  le groupe d'action attendu (gmail, calendar) reste lié
    ambiguës         le skill ET les groupes d'action sont liés
    tokens / tour    taille des schémas d'outils envoyés au modèle
    écarts           outils d'action liés avant et plus après (régressions)

Même chemin que la production : classement des groupes, budget, puis
`appliquer_les_skills`. Seuls MCP et les outils « ouverts » du catalogue manquent.

`--live` ajoute la question que la proposition ne tranche pas : le modèle APPELLE-
t-il `load_skill`, avec le bon skill, quand il le faut — et s'abstient-il sur une
action pure. Coûte des appels au modèle ; ne tourne pas dans la suite de tests.

    python outils/mesure_skills_lies.py
    python outils/mesure_skills_lies.py --live --backend mistral
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
sys.stdout.reconfigure(line_buffering=True)

from corpus_skills_lies import ACTIONS, AMBIGUES, SKILLS  # noqa: E402

PORTEE = "orchestrator"


def monde(toujours_lies: bool):
    """Le retriever et l'outil du catalogue, reconstruits avec ce réglage : le
    drapeau change les documents indexés, donc l'index."""
    from src.infra.settings import settings
    from src.orchestrator.routage.catalogue import indexer, obtenir_outil
    from src.orchestrator.routage.registry import build_all_tools
    from src.orchestrator.routage.tool_retriever import ToolRetriever

    settings.skills_toujours_lies = toujours_lies
    outils = build_all_tools()
    retriever = ToolRetriever(outils)
    indexer(outils + [obtenir_outil])
    return retriever, obtenir_outil


def selection(mon, requete: str) -> list:
    """Les outils liés au modèle pour cette requête, comme dans `chatbot`."""
    from src.orchestrator.routage.skills_lies import appliquer_les_skills

    retriever, obtenir_outil = mon
    return appliquer_les_skills(retriever.get(requete), requete, PORTEE) + [obtenir_outil]


def groupe_lie(groupe: str, liees: list) -> bool:
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

    return bool(set(TOOL_GROUPS[groupe].tools) & {t.name for t in liees})


def _compteur_de_tokens():
    try:
        import tiktoken

        encodeur = tiktoken.get_encoding("cl100k_base")
        return lambda texte: len(encodeur.encode(texte))
    except Exception:                                        # noqa: BLE001
        return lambda texte: len(texte) // 4


def tokens_du_schema(outils: list, compter) -> int:
    from langchain_core.utils.function_calling import convert_to_openai_tool

    return sum(compter(json.dumps(convert_to_openai_tool(o), ensure_ascii=False)) for o in outils)


def _requetes() -> list[str]:
    return ([q for qs in SKILLS.values() for q in qs]
            + [q for q, _ in ACTIONS] + [q for q, _, _ in AMBIGUES])


def mesurer(toujours_lies: bool) -> dict:
    mon = monde(toujours_lies)
    compter = _compteur_de_tokens()
    liees = {q: selection(mon, q) for q in _requetes()}
    noms = {q: {t.name for t in outils} for q, outils in liees.items()}

    par_skill = {nom: sum("load_skill" in noms[q] for q in qs) for nom, qs in SKILLS.items()}
    actions = sum(groupe_lie(g, liees[q]) for q, g in ACTIONS)
    ambigues = sum("load_skill" in noms[q] and all(groupe_lie(g, liees[q]) for g in gs)
                   for q, _, gs in AMBIGUES)
    tokens = [tokens_du_schema(liees[q], compter) for q in liees]
    schema_skill = max((tokens_du_schema([t], compter) for outils in liees.values()
                        for t in outils if t.name == "load_skill"), default=0)
    return {"noms": noms, "par_skill": par_skill, "actions": actions, "ambigues": ambigues,
            "tokens": sum(tokens) / len(tokens), "schema_skill": schema_skill,
            "outils": sum(len(o) for o in liees.values()) / len(liees)}


def _ecarts(avant: dict, apres: dict) -> list[str]:
    """Les requêtes où un outil d'un groupe d'action attendu a DISPARU."""
    attendus = {q: [g] for q, g in ACTIONS} | {q: list(gs) for q, _, gs in AMBIGUES}
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

    perdus = []
    for requete, groupes in attendus.items():
        for groupe in groupes:
            outils = set(TOOL_GROUPS[groupe].tools)
            manquants = (avant["noms"][requete] & outils) - apres["noms"][requete]
            if manquants:
                perdus.append(f"{groupe} : {', '.join(sorted(manquants))} — « {requete[:60]} »")
    return perdus


def _pct(n: int, total: int) -> str:
    return f"{n}/{total}  {100 * n / total:5.1f} %"


def _ligne(libelle: str, avant: str, apres: str, suite: str = "") -> None:
    print(f"   {libelle:<30}  {avant:>18}  {apres:>18}{suite}")


def rapport(avant: dict, apres: dict) -> None:
    print("\n━━ SKILL PROPOSÉ — `load_skill` lié ━━                      avant            après")
    for nom, qs in SKILLS.items():
        _ligne(nom, _pct(avant["par_skill"][nom], len(qs)), _pct(apres["par_skill"][nom], len(qs)))
    total = sum(len(qs) for qs in SKILLS.values())
    _ligne("TOTAL", _pct(sum(avant["par_skill"].values()), total),
           _pct(sum(apres["par_skill"].values()), total))
    print("\n━━ ACTIONS PURES — groupe d'action toujours lié ━━")
    _ligne("gmail / calendar", _pct(avant["actions"], len(ACTIONS)), _pct(apres["actions"], len(ACTIONS)))
    print("\n━━ AMBIGUËS — skill ET groupes d'action liés ━━")
    _ligne("skill + actions", _pct(avant["ambigues"], len(AMBIGUES)), _pct(apres["ambigues"], len(AMBIGUES)))
    print("\n━━ COÛT — par tour, schémas d'outils (tiktoken cl100k) ━━")
    _ligne("outils liés (moyenne)", f"{avant['outils']:.1f}", f"{apres['outils']:.1f}")
    _ligne("tokens de schémas (moyenne)", f"{avant['tokens']:.0f}", f"{apres['tokens']:.0f}",
           f"   Δ {apres['tokens'] - avant['tokens']:+.0f}")
    _ligne("dont `load_skill` seul", str(avant["schema_skill"]), str(apres["schema_skill"]))
    perdus = _ecarts(avant, apres)
    print(f"\n━━ ÉCARTS — outils d'action liés avant, perdus après : {len(perdus)} ━━")
    for ligne in perdus:
        print(f"   {ligne}")


# ── sur le vrai modèle ────────────────────────────────────────────────────────

def classer(reponse, attendu: str) -> str:
    appels = [(a.get("name"), a.get("args") or {}) for a in getattr(reponse, "tool_calls", None) or []]
    skills = [str(args.get("stack", "")).strip().lower() for nom, args in appels if nom == "load_skill"]
    if attendu in skills:
        return "CHARGE"
    if skills:
        return "AUTRE SKILL"
    return "SANS SKILL" if appels else "TEXTE"


def _deuxieme_tour(llm, messages: list, reponse):
    """Si le modèle n'a fait que poser une question, on la lui répond « oui » et
    on lui laisse un second tour : il peut charger le skill APRÈS la clarification."""
    from langchain_core.messages import ToolMessage

    appels = reponse.tool_calls
    if not appels or any(a["name"] != "ask_clarification" for a in appels):
        return None
    reponses = [ToolMessage(content=json.dumps({"answers": {"question": "oui"}}),
                            tool_call_id=a["id"], name="ask_clarification") for a in appels]
    return llm.invoke(messages + [reponse] + reponses)


def verifier_en_reel(nom_backend: str, fabrique, pause: float, toujours_lies: bool = True) -> None:
    from datetime import datetime

    from langchain_core.messages import HumanMessage

    from src.orchestrator.noeuds.chat import _ensure_system_prompt
    from src.orchestrator.routage.catalogue import menu

    mon = monde(toujours_lies)
    cas = ([(q, skill.split(" — ")[0]) for skill, qs in SKILLS.items() for q in qs]
           + [(q, s) for q, s, _ in AMBIGUES] + [(q, "") for q, _ in ACTIONS])
    comptes: dict[str, dict[str, int]] = {}
    mode = "load_skill toujours lié" if toujours_lies else "ANCIEN routage"
    print(f"\n━━ SUR LE VRAI MODÈLE — {nom_backend} — {mode} ━━")
    for requete, attendu in cas:
        liees = selection(mon, requete)
        messages = _ensure_system_prompt([HumanMessage(content=requete)], liees,
                                         datetime.now().strftime("%Y-%m-%d"), catalogue=menu())
        llm = fabrique().bind_tools(liees)
        time.sleep(pause)
        try:
            reponse = llm.invoke(messages)
            verdict = classer(reponse, attendu or "-")
            if verdict == "SANS SKILL" and attendu:
                second = _deuxieme_tour(llm, messages, reponse)
                if second is not None and classer(second, attendu) == "CHARGE":
                    verdict = "CHARGE (2e tour)"
        except Exception as erreur:                          # noqa: BLE001
            print(f"   ERREUR   {type(erreur).__name__}: {str(erreur)[:80]}")
            continue
        famille = attendu or "action pure"
        comptes.setdefault(famille, {})
        comptes[famille][verdict] = comptes[famille].get(verdict, 0) + 1
        print(f"   {verdict:<17} {famille:<12} « {requete[:70]} »")

    print("\n   Synthèse (par famille)")
    for famille, c in comptes.items():
        print(f"   {famille:<12} " + "  ".join(f"{v} {k}" for k, v in sorted(c.items())))


def _backend(force: str | None) -> tuple[str, object]:
    import src.infra.settings  # noqa: F401
    from src.llm.backends import fabriques, ordre_de_repli

    usines = fabriques()
    for nom in ([force] if force else ordre_de_repli()):
        if nom in usines:
            return nom, usines[nom]
    raise SystemExit("aucun backend utilisable")


def _mesure_dans_un_processus(nom: str, etat: Path) -> dict:
    """Un mode par processus : Chroma garde la base ouverte, et le retriever la
    supprime pour la reconstruire — dans un même processus, la seconde échoue.
    Le dossier d'état est temporaire : l'index réel d'Axon n'est pas touché."""
    sortie = etat / f"{nom}.json"
    environnement = {**os.environ, "AXON_STATE_DIR": str(etat / nom)}
    fini = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--mode", nom,
                           "--sortie", str(sortie)], env=environnement,
                          capture_output=True, text=True, check=False)
    if fini.returncode:
        raise SystemExit(f"mesure « {nom} » en échec :\n{fini.stderr[-1500:]}")
    resultat = json.loads(sortie.read_text(encoding="utf-8"))
    resultat["noms"] = {q: set(v) for q, v in resultat["noms"].items()}
    return resultat


def main() -> None:
    analyseur = argparse.ArgumentParser(description="`load_skill` toujours lié : avant / après.")
    analyseur.add_argument("--live", action="store_true", help="aussi sur le vrai modèle")
    analyseur.add_argument("--ancien", action="store_true",
                           help="avec --live : l'ancien routage (drapeau désactivé), pour comparer")
    analyseur.add_argument("--live-seul", action="store_true",
                           help="le vrai modèle seulement, sans refaire la mesure hors ligne")
    analyseur.add_argument("--backend", default=None, help="un ou plusieurs backends, séparés par des virgules")
    analyseur.add_argument("--pause", type=float, default=2.5, help="secondes entre deux appels")
    analyseur.add_argument("--mode", choices=("avant", "apres"), help=argparse.SUPPRESS)
    analyseur.add_argument("--sortie", help=argparse.SUPPRESS)
    args = analyseur.parse_args()

    if args.mode:
        resultat = mesurer(args.mode == "apres")
        resultat["noms"] = {q: sorted(v) for q, v in resultat["noms"].items()}
        Path(args.sortie).write_text(json.dumps(resultat), encoding="utf-8")
        return

    with tempfile.TemporaryDirectory(prefix="axon-mesure-") as dossier:
        etat = Path(dossier)
        if not args.live_seul:
            rapport(_mesure_dans_un_processus("avant", etat),
                    _mesure_dans_un_processus("apres", etat))
        if args.live or args.live_seul:
            os.environ["AXON_STATE_DIR"] = str(etat / "live")
            for demande in (args.backend.split(",") if args.backend else [None]):
                nom, fabrique = _backend(demande)
                verifier_en_reel(nom, fabrique, args.pause, toujours_lies=not args.ancien)


if __name__ == "__main__":
    main()
