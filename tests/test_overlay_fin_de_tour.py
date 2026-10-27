"""src/ui/streaming.py — l'île suit la réponse en direct et apprend toujours
la fin d'un tour.

Vécu : avec Mistral, qui n'émet que des messages entiers, l'île ne recevait ni
le texte ni « réponse prête » — figée sur « Axon réfléchit » alors que le CLI
avait répondu.
"""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

import src.ui.streaming as streaming


class _Pont:
    def __init__(self):
        self.etats: list[str] = []
        self.messages: list[str] = []
        self.flux: list[str] = []

    def reponse_flux(self, texte):
        self.flux.append(texte)

    def etat(self, etat, texte=""):
        self.etats.append(etat)

    def message(self, texte):
        self.messages.append(texte)

    def outil(self, nom, detail=""):
        pass


class _Graphe:
    def __init__(self, *messages, erreur=None):
        self.messages = messages
        self.erreur = erreur

    def stream(self, entree, config=None, stream_mode=None):
        for m in self.messages:
            yield m, {}
        if self.erreur:
            raise self.erreur


@pytest.fixture
def pont(monkeypatch):
    p = _Pont()
    monkeypatch.setattr(streaming, "pont", p)
    return p


def test_un_backend_sans_streaming_termine_le_tour_dans_l_ile(pont):
    list(streaming._stream_et_publier(_Graphe(AIMessage(content="Voici le plan.", id="a")), None, {}))
    assert pont.messages == ["Voici le plan."]
    assert pont.etats[-1] == "finished"


def test_un_message_deja_relaye_en_morceaux_n_est_pas_double(pont):
    graphe = _Graphe(AIMessageChunk(content="Bon", id="a"), AIMessageChunk(content="jour", id="a"),
                     AIMessage(content="Bonjour", id="a"))
    list(streaming._stream_et_publier(graphe, None, {}))
    assert pont.messages == ["Bonjour"]


def test_une_erreur_en_plein_tour_ne_laisse_pas_l_ile_sur_reflechit(pont):
    graphe = _Graphe(AIMessageChunk(content="Je passe à la", id="a"),
                     erreur=RuntimeError("Internal Server Error"))
    with pytest.raises(RuntimeError):
        list(streaming._stream_et_publier(graphe, None, {}))
    assert pont.etats[-1] == "erreur"


def test_un_tour_sans_texte_finit_quand_meme(pont):
    list(streaming._stream_et_publier(_Graphe(), None, {}))
    assert pont.etats[-1] == "finished"


class _Horloge:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def test_le_texte_en_direct_est_borne_a_un_envoi_par_intervalle(pont):
    horloge = _Horloge()
    relais = streaming._RelaisOverlay(horloge=horloge)
    for morceau in ("Je ", "regarde ", "tes "):
        relais.recevoir(AIMessageChunk(content=morceau, id="a"))
    horloge.t += 2 * streaming._RelaisOverlay.INTERVALLE
    relais.recevoir(AIMessageChunk(content="dépôts", id="a"))
    relais.finir(termine=True)

    assert pont.flux == ["Je ", "Je regarde tes dépôts"]
    assert pont.messages == ["Je regarde tes dépôts"]


def test_deux_reponses_d_un_meme_tour_restent_deux_paragraphes(pont):
    relais = streaming._RelaisOverlay()
    relais.recevoir(AIMessage(content="Je lance les tests.", id="a"))
    relais.recevoir(AIMessage(content="Tout passe.", id="b"))
    relais.finir(termine=True)
    assert pont.messages == ["Je lance les tests.\n\nTout passe."]
