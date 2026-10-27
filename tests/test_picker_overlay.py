"""src/ui/picker.py — `pick()` pose son choix au terminal ET à l'île.

Mis à jour : la demande était EXCLUSIVE à l'île dès qu'elle était connectée,
ce qui éteignait le terminal (voir course_hitl.py). Historique ci-dessous.

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


def _terminal_interrompu_par_l_ile():
    """`Application.run` tel que le vit le picker quand l'île répond : il
    attend une touche jusqu'à ce que l'île lève l'annulation."""
    from src.ui.course_hitl import ANNULATION, ReponseAilleurs

    def run():
        assert ANNULATION.wait(2), "l'île n'a jamais interrompu le terminal"
        raise ReponseAilleurs
    return run


def test_ile_connectee_le_choix_de_l_ile_interrompt_le_terminal():
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=["ollama"]) as demander, \
                patch.object(pont, "abandonner"):
            with patch("src.ui.picker.Application") as app_cls:
                app_cls.return_value.run.side_effect = _terminal_interrompu_par_l_ile()
                resultat = pick(["groq", "ollama"], title="backend LLM")
        app_cls.assert_called_once()  # le terminal a bien posé la question aussi
        demander.assert_called_once()
        assert resultat == "ollama"
        # Un backend qui n'existe pas serait juste rejeté — pas de « Autre »
        # à proposer pour ce genre de choix fermé (voir hitl.py:Question.libre).
        demande_envoyee = demander.call_args[0][0]
        assert demande_envoyee["questions"][0]["libre"] is False
    finally:
        pont.sock = ancien_sock


def test_reponse_ile_hors_options_est_une_annulation():
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=["n'importe quoi"]), \
                patch.object(pont, "abandonner"):
            with patch("src.ui.picker.Application") as app_cls:
                app_cls.return_value.run.side_effect = _terminal_interrompu_par_l_ile()
                resultat = pick(["groq", "ollama"], title="backend LLM")
        assert resultat is None
    finally:
        pont.sock = ancien_sock


def test_ile_connectee_le_terminal_repond_et_ferme_la_carte_de_l_ile():
    """Le correctif : île connectée, le terminal pose TOUJOURS la question."""
    ancien_sock = pont.sock
    pont.sock = object()
    try:
        with patch.object(pont, "demander", return_value=None) as demander, \
                patch.object(pont, "abandonner") as abandonner:
            with patch("src.ui.picker.Application") as app_cls:
                app_cls.return_value.run.return_value = "ollama"
                resultat = pick(["groq", "ollama"], title="backend LLM")
        app_cls.assert_called_once()
        assert resultat == "ollama"
        abandonner.assert_called_once()
        assert demander.call_count <= 1
    finally:
        pont.sock = ancien_sock


def test_liste_vide_court_circuite_sans_jamais_consulter_l_ile():
    with patch.object(pont, "demander") as demander:
        assert pick([], title="vide") is None
    demander.assert_not_called()
