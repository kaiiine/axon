"""src/ui/picker.py — `pick()` essaie d'abord l'île avant le picker terminal.

Avant ce correctif, /backend, /model, /mode et le wizard /spec ne proposaient
leur choix qu'au terminal — même avec l'île ouverte et connectée, elle ne
voyait jamais rien. Ce que ces tests protègent :
  - l'île n'est interrogée QUE si elle est connectée (`pont.connecte`) ;
  - une réponse valide de l'île est renvoyée directement, sans jamais toucher
    au picker terminal (`Application.run`, qui bloquerait dans un test) ;
  - une réponse de l'île qui ne correspond à aucune option est une
    annulation — pas un re-essai au terminal, qui serait déroutant pour
    quelqu'un qui vient de répondre ailleurs ;
  - si l'île est connectée mais ne répond pas (absente, hors délai,
    déconnectée en cours de route — `pont.demander` renvoie None), on
    retombe bien sur le terminal plutôt que de rester bloqué silencieusement.
"""
from __future__ import annotations

from unittest.mock import patch

from src.ui.picker import pick
from src.ui.pont_overlay import pont


def test_ile_non_connectee_ne_consulte_jamais_pont_demander():
    # `pont` est un singleton process-wide qui tente une vraie connexion au
    # socket à l'import (voir pont_overlay.py) : sur une machine où l'île
    # tourne déjà, `pont.connecte` serait vrai sans ça — on force l'état
    # plutôt que de supposer l'environnement de test vierge.
    ancien_sock = pont.sock
    pont.sock = None
    try:
        assert pont.connecte is False
        with patch("src.ui.picker.Application") as app_cls:
            app_cls.return_value.run.return_value = "groq"
            with patch.object(pont, "demander") as demander:
                resultat = pick(["groq", "ollama"], title="backend LLM")
        demander.assert_not_called()
        assert resultat == "groq"  # vient bien du terminal (mocké), pas de l'île
    finally:
        pont.sock = ancien_sock


def test_ile_connectee_renvoie_directement_le_choix_valide():
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=["ollama"]) as demander:
            with patch("src.ui.picker.Application") as app_cls:
                resultat = pick(["groq", "ollama"], title="backend LLM")
        app_cls.assert_not_called()  # jamais touché au picker terminal
        demander.assert_called_once()
        assert resultat == "ollama"
        # Un backend qui n'existe pas serait juste rejeté — pas de « Autre »
        # à proposer pour ce genre de choix fermé (voir hitl.py:Question.libre).
        demande_envoyee = demander.call_args[0][0]
        assert demande_envoyee["questions"][0]["libre"] is False
    finally:
        pont.sock = ancien_sock


def test_reponse_ile_hors_options_est_une_annulation_pas_un_repli_terminal():
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=["n'importe quoi"]):
            with patch("src.ui.picker.Application") as app_cls:
                resultat = pick(["groq", "ollama"], title="backend LLM")
        app_cls.assert_not_called()
        assert resultat is None
    finally:
        pont.sock = ancien_sock


def test_ile_connectee_mais_sans_reponse_retombe_sur_le_terminal():
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=None) as demander:
            with patch("src.ui.picker.Application") as app_cls:
                app_cls.return_value.run.return_value = "ollama"
                resultat = pick(["groq", "ollama"], title="backend LLM")
        demander.assert_called_once()
        app_cls.assert_called_once()  # bien retombé sur le terminal
        assert resultat == "ollama"
    finally:
        pont.sock = ancien_sock


def test_liste_vide_court_circuite_sans_jamais_consulter_l_ile():
    with patch.object(pont, "demander") as demander:
        assert pick([], title="vide") is None
    demander.assert_not_called()
