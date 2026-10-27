"""Un `HumanMessage` interne ne doit pas relancer la compression proactive.

Vécu à l'écran : une confirmation shell refusée pendant `/deep`, puis un
« compiling… » qui ne semble plus finir. `chatbot()` remettait
`_compressed_this_turn = False` sur TOUT `HumanMessage`, y compris ceux que
`note_interne.note()` produit pour réinjecter un compte rendu — confirmation
refusée, plan validé, revue de fichier. Le contexte restant chargé après une
grosse pièce jointe, la compression se redéclenchait en plein milieu du même
tour utilisateur.

`est_interne()` existait déjà pour exactement cette distinction — utilisée
ailleurs (l'affichage), jamais ici.
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.orchestrator.commun.note_interne import est_interne, note


def _reset_du_a(message) -> bool:
    """La condition telle que `chatbot()` la pose désormais."""
    return isinstance(message, HumanMessage) and not est_interne(message)


def test_un_vrai_message_utilisateur_reinitialise():
    assert _reset_du_a(HumanMessage(content="et pour Unity ?"))


def test_une_note_interne_ne_reinitialise_plus():
    """Le cas vécu : la confirmation refusée réinjectée par `note()`."""
    assert not _reset_du_a(note("confirmation refusée"))


def test_un_message_qui_nest_pas_humain_ne_reinitialise_pas():
    assert not _reset_du_a(AIMessage(content="je réponds"))
    assert not _reset_du_a(SystemMessage(content="système"))


def test_note_produit_bien_un_humanmessage():
    """Sinon `est_interne()` sur un AUTRE type de message ne protégerait rien —
    la garde suppose que les notes internes restent des HumanMessage."""
    assert isinstance(note("x"), HumanMessage)
