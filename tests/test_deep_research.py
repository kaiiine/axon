"""Recherche approfondie : décomposer, chercher en parallèle, combler, synthétiser.

Les appels au modèle et au web sont injectés — le graphe se teste sans réseau.
"""
from __future__ import annotations

import json
import time

import pytest
from langchain_core.messages import ToolMessage

from src.agents.deep.graphe import SOUS_QUESTIONS_MAX, TOURS_MAX, construire
from src.agents.deep.noeud import MARQUEUR


def _faux(decoupe='["a", "b"]', manques="[]", lenteur=0.0):
    trace = {"web": [], "modele": 0}

    def repondre(prompt: str) -> str:
        trace["modele"] += 1
        if "Découpe" in prompt:
            return decoupe
        if "restent SANS RÉPONSE" in prompt:
            return manques
        return "SYNTHÈSE"

    def chercher(sujet: str) -> str:
        trace["web"].append(sujet)
        if lenteur:
            time.sleep(lenteur)
        return f"contenu({sujet})"

    return repondre, chercher, trace


def _lancer(repondre, chercher, question="Question ?"):
    return construire(repondre, chercher).invoke(
        {"question": question, "trouvailles": []})


# ── Le découpage ─────────────────────────────────────────────────────────────
def test_la_question_est_decoupee_et_chaque_morceau_cherche():
    repondre, chercher, trace = _faux(decoupe='["prix", "avis", "garantie"]')
    sortie = _lancer(repondre, chercher)

    assert trace["web"] == ["prix", "avis", "garantie"]
    assert len(sortie["trouvailles"]) == 3


def test_un_decoupage_illisible_cherche_la_question_telle_quelle():
    """Une réponse hors format ne doit pas tuer la recherche."""
    repondre, chercher, trace = _faux(decoupe="je ne sais pas découper")
    _lancer(repondre, chercher, "Le Legion vaut-il le coup ?")

    assert trace["web"] == ["Le Legion vaut-il le coup ?"]


def test_le_decoupage_est_plafonne():
    """Sans plafond, une question vague vide un quota."""
    trop = "[" + ", ".join(f'"q{i}"' for i in range(20)) + "]"
    repondre, chercher, trace = _faux(decoupe=trop)
    _lancer(repondre, chercher)

    assert len(trace["web"]) == SOUS_QUESTIONS_MAX


# ── Le parallélisme ──────────────────────────────────────────────────────────
def test_les_recherches_partent_EN_PARALLELE():
    """La raison d'être du sous-graphe. En série, quatre recherches de 0,3 s
    prendraient 1,2 s."""
    repondre, chercher, _ = _faux(decoupe='["a","b","c","d"]', lenteur=0.3)
    debut = time.perf_counter()
    _lancer(repondre, chercher)
    duree = time.perf_counter() - debut

    assert duree < 0.9, f"{duree:.2f}s — les recherches semblent séquentielles"


# ── Les tours ────────────────────────────────────────────────────────────────
def test_un_manque_declenche_un_second_tour():
    repondre, chercher, trace = _faux(decoupe='["a"]', manques='["b"]')
    sortie = _lancer(repondre, chercher)

    assert trace["web"] == ["a", "b"]
    assert sortie["tours"] == 2


def test_aucun_manque_arrete_apres_un_tour():
    repondre, chercher, trace = _faux(decoupe='["a"]', manques="[]")
    _lancer(repondre, chercher)

    assert trace["web"] == ["a"]


def test_le_nombre_de_tours_est_borne():
    """Le modèle trouvera toujours quelque chose à creuser : c'est le code qui
    doit s'arrêter, pas lui."""
    repondre, chercher, trace = _faux(decoupe='["a"]', manques='["encore"]')
    sortie = _lancer(repondre, chercher)

    assert sortie["tours"] <= TOURS_MAX
    assert len(trace["web"]) <= SOUS_QUESTIONS_MAX * TOURS_MAX


# ── Robustesse ───────────────────────────────────────────────────────────────
def test_une_recherche_qui_echoue_n_arrete_pas_les_autres():
    repondre, _, _ = _faux(decoupe='["ok", "casse"]')

    def chercher(sujet):
        if sujet == "casse":
            raise RuntimeError("source injoignable")
        return "contenu"

    sortie = _lancer(repondre, chercher)
    assert len(sortie["trouvailles"]) == 2
    assert any("échouée" in t["contenu"] for t in sortie["trouvailles"])
    assert sortie.get("rapport")


def test_la_synthese_ne_voit_que_ce_qui_a_ete_trouve():
    """Le prompt de synthèse doit porter les sources : sans elles, le modèle
    rédigerait de mémoire."""
    vus = {}

    def repondre(prompt):
        if "Rédige une synthèse" in prompt:
            vus["prompt"] = prompt
            return "SYNTHÈSE"
        return '["a"]' if "Découpe" in prompt else "[]"

    _lancer(repondre, lambda s: f"contenu({s})")
    assert "contenu(a)" in vus["prompt"]
    assert "n'ajoute rien" in vus["prompt"].lower()


# ── La bibliographie ne peut plus être inventée ───────────────────────────────
def test_domaines_de_extrait_sans_doublon_dans_lordre():
    from src.agents.deep.graphe import domaines_de

    contenu = ("[Unity](https://docs.unity3d.com/x) et encore "
               "[Unity](https://docs.unity3d.com/y) puis [Wiki](https://en.wikipedia.org/z)")

    assert domaines_de(contenu) == ["docs.unity3d.com", "en.wikipedia.org"]


def test_chaque_trouvaille_porte_ses_domaines():
    """Extraits UNE fois, à la source — pas redevinés plus tard sur un texte
    fusionnant plusieurs rapports."""
    repondre, _, _ = _faux(decoupe='["a"]')
    sortie = _lancer(
        repondre, lambda s: f"voir [X](https://exemple-{s}.test/page)")

    assert sortie["trouvailles"][0]["domaines"] == [f"exemple-a.test"]


def test_la_bibliographie_ajoutee_ne_cite_que_ce_qui_a_ete_trouve():
    """Le bug vécu : fusionner dix rapports dont les citations 【1】…【6】
    repartent de zéro à chaque appel forçait le modèle à reconstruire une
    bibliographie qu'il ne pouvait pas connaître — il comblait par des noms de
    domaine plausibles mais jamais consultés (`app.studyraid.com`,
    `learntutorials.net`, vécu sur « c'est quoi des quaternions en Unity »).

    La correction porte sur la BIBLIOGRAPHIE AJOUTÉE, construite en Python à
    partir des seuls domaines réellement extraits — pas sur la prose du
    modèle, qu'aucun post-traitement ne filtre : s'il ignorait l'instruction et
    citait un domaine inventé DANS son texte, rien ici ne l'en empêcherait. Ce
    que ce test garantit : la section ajoutée par le code, elle, ne peut
    contenir que du réel."""
    repondre, _, _ = _faux(decoupe='["a"]')

    sortie = _lancer(repondre, lambda s: f"[Unity](https://docs.unity3d.com/{s})")

    ligne_bibliographie = sortie["rapport"].rsplit("Sources consultées", 1)[-1]
    assert "app.studyraid.com" not in ligne_bibliographie
    assert "learntutorials.net" not in ligne_bibliographie
    assert "docs.unity3d.com" in ligne_bibliographie


def test_sans_url_aucune_section_sources_nest_ajoutee():
    """Une trouvaille sans lien ne doit pas produire une bibliographie vide."""
    repondre, _, _ = _faux(decoupe='["a"]')

    sortie = _lancer(repondre, lambda s: "contenu sans aucun lien")

    assert "Sources consultées" not in sortie["rapport"]


def test_le_prompt_de_synthese_interdit_les_numeros():
    """La cause du bug, coupée à la racine : demander des citations numérotées
    sur un texte fusionné les rendait indéchiffrables."""
    vus = {}

    def repondre(prompt):
        if "Rédige une synthèse" in prompt:
            vus["prompt"] = prompt
            return "SYNTHÈSE"
        return '["a"]' if "Découpe" in prompt else "[]"

    _lancer(repondre, lambda s: f"contenu({s})")
    assert "jamais de numéro" in vus["prompt"]


# ── L'outil ──────────────────────────────────────────────────────────────────
def test_une_question_vide_est_refusee():
    from src.agents.deep.tools import deep_research

    assert "vide" in deep_research.invoke({"question": "   "}).lower()


def test_l_outil_DECLARE_l_intention_et_ne_cherche_pas():
    """Le travail est fait par le nœud, pas par l'outil. Un outil est atomique
    pour le moteur : la recherche n'y serait ni checkpointée ni interruptible."""
    import json

    from src.agents.deep.noeud import MARQUEUR, question_a_creuser
    from src.agents.deep.tools import deep_research

    rendu = json.loads(deep_research.invoke({"question": "le RAG en 2026"}))
    assert rendu["status"] == MARQUEUR
    assert rendu["question"] == "le RAG en 2026"


def test_le_routeur_mene_au_noeud():
    import inspect

    from src.orchestrator.noeuds.clarification import apres_les_outils

    assert "approfondir" in inspect.getsource(apres_les_outils)


def test_le_graphe_declare_le_noeud():
    import inspect

    from src.orchestrator import graph as g

    source = inspect.getsource(g)
    assert 'g.add_node("approfondir"' in source
    assert 'g.add_edge("approfondir", "chatbot")' in source


def test_une_etape_deja_faite_n_est_pas_REJOUEE_a_la_reprise():
    """La propriété qu'un outil ne pouvait pas offrir.

    Le sous-graphe est compilé sans checkpointer : invoqué depuis un nœud, il
    hérite de celui du parent, donc ses étapes sont checkpointées. Une recherche
    interrompue reprend sans refaire les appels déjà payés.
    """
    from typing import TypedDict

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    faits = []

    class Fils(TypedDict, total=False):
        resultat: str

    def coute_cher(_):
        faits.append("appels web")
        return {"resultat": "partiel"}

    def demande(_):
        rep = interrupt({"questions": [{"texte": "Quel angle ?"}]})
        return {"resultat": f"final {rep}"}

    f = StateGraph(Fils)
    f.add_node("coute_cher", coute_cher)
    f.add_node("demande", demande)
    f.add_edge(START, "coute_cher")
    f.add_edge("coute_cher", "demande")
    f.add_edge("demande", END)
    fils = f.compile()          # sans checkpointer : il héritera de celui du parent

    class Parent(TypedDict, total=False):
        sortie: str

    def noeud(_):
        return {"sortie": fils.invoke({})["resultat"]}

    p = StateGraph(Parent)
    p.add_node("noeud", noeud)
    p.add_edge(START, "noeud")
    p.add_edge("noeud", END)
    app = p.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "reprise"}}

    premier = app.invoke({}, cfg)
    assert premier.get("__interrupt__"), "l'interruption du sous-graphe ne remonte pas"

    app.invoke(Command(resume=["technique"]), cfg)
    assert faits == ["appels web"], f"étape rejouée : {faits}"


def test_l_outil_dit_quand_prendre_l_autre():
    """Sans cette borne, une question factuelle coûterait cinq recherches."""
    from src.agents.deep.tools import deep_research

    assert "web_research_report" in deep_research.description


def test_l_outil_est_enregistre_et_dans_le_groupe_search():
    from src.orchestrator.routage.registry import build_all_tools
    from src.orchestrator.routage.tool_retriever import TOOL_GROUPS

    assert "deep_research" in {t.name for t in build_all_tools()}
    assert "deep_research" in TOOL_GROUPS["search"].tools


@pytest.mark.parametrize("requete", [
    "fais-moi une recherche approfondie sur les LLM open source",
    "creuse le sujet des bases vectorielles",
])
def test_une_demande_approfondie_atteint_l_outil(requete):
    """Deux formulations sur quatre seulement — « monte-moi un dossier complet »
    et « compare en profondeur » partent ailleurs, et `search` ne figure même pas
    dans les quatre premiers groupes. C'est la faiblesse connue de l'étage 1, pas
    un défaut de l'outil : des mots-clés ont été essayés, sans gain mesurable et
    au prix d'une régression sur `memory`."""
    from src.orchestrator.routage.registry import build_all_tools
    from src.orchestrator.routage.tool_retriever import ToolRetriever

    outils = {t.name for t in ToolRetriever(build_all_tools()).get(requete)}
    assert "deep_research" in outils


# ── note() prend `texte`, pas `content` ───────────────────────────────────────
def test_le_rapport_de_reussite_ne_plante_pas():
    """`erreur : note() got an unexpected keyword argument 'content'` — présent
    depuis la création du fichier, sur les trois issues (échec, rapport vide,
    succès). Reproduit à l'écran sur « c'est quoi des quaternions en unity »."""
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir

    etat = {"messages": [ToolMessage(
        content=json.dumps({"status": MARQUEUR, "question": "les quaternions"}),
        tool_call_id="x", name="deep_research")]}

    with patch("src.agents.deep.graphe.construire") as construire:
        construire.return_value.stream.return_value = iter([
            ("values", {"rapport": "un rapport", "trouvailles": [], "tours": 1}),
        ])
        resultat = approfondir(etat)

    assert "quaternions" in resultat["messages"][0].content


def test_un_rapport_vide_ne_plante_pas():
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir

    etat = {"messages": [ToolMessage(
        content=json.dumps({"status": MARQUEUR, "question": "x"}),
        tool_call_id="x", name="deep_research")]}

    with patch("src.agents.deep.graphe.construire") as construire:
        construire.return_value.stream.return_value = iter([
            ("values", {"rapport": "", "trouvailles": []}),
        ])
        resultat = approfondir(etat)

    assert "aucune synthèse" in resultat["messages"][0].content


def test_une_exception_ne_plante_pas():
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir

    etat = {"messages": [ToolMessage(
        content=json.dumps({"status": MARQUEUR, "question": "x"}),
        tool_call_id="x", name="deep_research")]}

    with patch("src.agents.deep.graphe.construire") as construire:
        construire.return_value.stream.side_effect = ValueError("boom")
        resultat = approfondir(etat)

    assert "échoué" in resultat["messages"][0].content


# ── progrès en direct, un événement par recherche ─────────────────────────────
def test_chaque_recherche_notifie_meme_en_parallele():
    """Vécu : « je n'ai plus accès aux sites qu'il consulte en temps réel ».
    `.invoke()` masquait tout jusqu'au retour du sous-graphe entier. Avec
    `stream_mode=['updates', 'values']`, chaque `chercher_une` notifie DÈS
    QU'IL FINIT — même lancé en parallèle via `Send` (vérifié empiriquement :
    trois tâches simultanées donnent trois événements `updates` distincts)."""
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir, set_progress_callback

    evenements = []
    set_progress_callback(lambda n, p: evenements.append((n, p)))
    try:
        etat = {"messages": [ToolMessage(
            content=json.dumps({"status": MARQUEUR, "question": "x"}),
            tool_call_id="x", name="deep_research")]}

        with patch("src.agents.deep.tools.repondre_avec_modele") as rep, \
             patch("src.agents.deep.tools.chercher_web") as chr_:
            reponses = iter(['["a", "b"]', "[]", "synthèse"])
            rep.return_value = lambda p: next(reponses)
            chr_.side_effect = lambda s: f"contenu {s}"
            approfondir(etat)
    finally:
        set_progress_callback(None)

    noms = [n for n, _ in evenements]
    assert noms.count("chercher_une") == 2, noms
    assert "decomposer" in noms and "synthetiser" in noms


def test_le_resultat_final_est_identique_avec_ou_sans_notificateur():
    """Le passage à `.stream()` ne doit rien changer à ce que le modèle reçoit —
    seul l'AFFICHAGE change, pas la donnée."""
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir, set_progress_callback

    def _rejouer():
        etat = {"messages": [ToolMessage(
            content=json.dumps({"status": MARQUEUR, "question": "x"}),
            tool_call_id="x", name="deep_research")]}
        with patch("src.agents.deep.tools.repondre_avec_modele") as rep, \
             patch("src.agents.deep.tools.chercher_web") as chr_:
            reponses = iter(['["a", "b"]', "[]", "synthèse finale"])
            rep.return_value = lambda p: next(reponses)
            chr_.side_effect = lambda s: f"contenu {s}"
            return approfondir(etat)["messages"][0].content

    set_progress_callback(None)
    sans = _rejouer()
    set_progress_callback(lambda n, p: None)
    try:
        avec = _rejouer()
    finally:
        set_progress_callback(None)

    assert sans == avec


def test_un_notificateur_qui_plante_ne_casse_pas_la_recherche():
    from unittest.mock import patch

    from src.agents.deep.noeud import approfondir, set_progress_callback

    def _casse(n, p):
        raise RuntimeError("boom")

    set_progress_callback(_casse)
    try:
        etat = {"messages": [ToolMessage(
            content=json.dumps({"status": MARQUEUR, "question": "x"}),
            tool_call_id="x", name="deep_research")]}
        with patch("src.agents.deep.tools.repondre_avec_modele") as rep, \
             patch("src.agents.deep.tools.chercher_web") as chr_:
            rep.return_value = lambda p: "[]"
            chr_.side_effect = lambda s: "contenu"
            resultat = approfondir(etat)
    finally:
        set_progress_callback(None)

    assert resultat["messages"]


# ── détail de l'échec, pas juste « — échec » ────────────────────────────────
# Vécu : cinq recherches en échec d'affilée sur `/deep`, sans un seul indice
# de CE qui avait échoué — Tavily hors service ? clé absente ? DNS ? La
# raison existait déjà dans `contenu`, seul l'écran la taisait.

def test_une_recherche_qui_leve_porte_le_message_dans_contenu():
    def chercher(sujet: str) -> str:
        raise ConnectionError("Tavily: 503 Service Unavailable")

    resultat = _lancer(*_faux()[:1] + (chercher,))
    trouvaille = resultat["trouvailles"][0]
    assert trouvaille["contenu"] == "[recherche échouée : Tavily: 503 Service Unavailable]"


def test_une_exception_sans_message_montre_au_moins_son_type():
    """`str(ConnectionError())` est vide — sans repli, l'écran afficherait
    « — échec : » sans rien derrière, aussi inexploitable qu'avant le fix."""
    def chercher(sujet: str) -> str:
        raise ConnectionError

    resultat = _lancer(*_faux()[:1] + (chercher,))
    trouvaille = resultat["trouvailles"][0]
    assert trouvaille["contenu"] == "[recherche échouée : ConnectionError]"
