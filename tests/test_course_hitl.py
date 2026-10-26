"""src/ui/course_hitl.py — une demande HITL au terminal ET à l'île.

Avant : exclusive à l'île dès qu'elle était connectée. Le CLI s'y reconnectant
en permanence, le terminal n'affichait plus aucune demande.
"""
from __future__ import annotations

import threading

import pytest

import src.ui.pont_overlay as module_pont
from src.ui.course_hitl import ANNULATION, ReponseAilleurs, en_course

DEMANDE = {"genre": "autorisation", "questions": [{"texte": "?", "choix": ["Oui", "Non"]}]}


class _FauxPont:
    def __init__(self, connecte=True, reponse=None):
        self.connecte = connecte
        self.reponse = reponse
        self.recu = threading.Event()
        self.abandons: list[str] = []
        self._stop = threading.Event()

    def demander(self, demande, delai=300, id_=None):
        self.recu.set()
        if self.reponse is not None:
            return self.reponse
        self._stop.wait(5)
        return None

    def abandonner(self, id_):
        self.abandons.append(id_)
        self._stop.set()


@pytest.fixture
def faux(monkeypatch):
    def _installer(**kw):
        pont = _FauxPont(**kw)
        monkeypatch.setattr(module_pont, "pont", pont)
        return pont
    return _installer


def test_sans_ile_seul_le_terminal_repond(faux):
    pont = faux(connecte=False)
    assert en_course(DEMANDE, lambda: ["Oui"], lambda r: r) == ["Oui"]
    assert not pont.recu.is_set()


def test_ile_connectee_le_terminal_pose_quand_meme_la_question(faux):
    """Le cœur du correctif : l'île connectée n'éteint plus le terminal."""
    pont = faux()
    vu = []
    assert en_course(DEMANDE, lambda: vu.append(1) or ["Non"], lambda r: r) == ["Non"]
    assert vu == [1]
    assert pont.recu.wait(1)
    assert len(pont.abandons) == 1          # la carte de l'île se ferme


def test_une_reponse_de_l_ile_interrompt_le_terminal(faux):
    faux(reponse=["Oui"])
    annonces = []

    def terminal():
        assert ANNULATION.wait(2)
        raise ReponseAilleurs

    assert en_course(DEMANDE, terminal, lambda r: ("ile", r),
                     lambda: annonces.append(1)) == ("ile", ["Oui"])
    assert annonces == [1]
    assert not ANNULATION.is_set()          # remis à zéro pour la suivante


def test_attendre_touche_leve_quand_l_ile_repond():
    import os
    from src.ui.course_hitl import attendre_touche
    lecture, ecriture = os.pipe()
    try:
        ANNULATION.set()
        with pytest.raises(ReponseAilleurs):
            attendre_touche(lecture)
    finally:
        ANNULATION.clear()
        os.close(lecture)
        os.close(ecriture)
