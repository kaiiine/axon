"""La demande du graphe se LIT au même endroit, quel que soit ce qui l'affiche.

Le HITL vivait dans `src/ui/streaming.py`, en six mécanismes éparpillés. Le
défaut mesuré à l'époque : un second transport (l'endpoint compatible OpenAI)
n'en connaissait aucun, et une question posée par le graphe n'y trouvait
personne pour y répondre.

Ce transport-là a été supprimé depuis — il ne servait pas. Ce que ces tests
gardent reste vrai et utile : la lecture de la demande est une fonction à part,
pas du rendu. C'est ce qui rend un second transport possible le jour où il en
faut un, et c'est ce qui empêche le terminal de redevenir le seul endroit qui
sache ce que le graphe attend.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.orchestrator.commun.hitl import Demande, Question


def _instantane(valeur):
    """Un état de graphe factice portant une interruption."""
    return SimpleNamespace(tasks=(SimpleNamespace(
        interrupts=(SimpleNamespace(value=valeur),)),))


class _Graphe:
    def __init__(self, instantane):
        self._i = instantane

    def get_state(self, config):
        return self._i


def test_le_TUI_lit_la_demande_dans_l_etat_du_graphe():
    from src.ui.streaming import _demande_du_graphe

    demande = Demande(genre="autorisation", cle="rm -rf /tmp/x",
                      apercu="Fichier : /tmp/x",
                      questions=(Question("Exécuter ?", ("Non", "Oui"), affirmatif="Oui"),))
    lue = _demande_du_graphe(_Graphe(_instantane(demande.en_clair())), {})

    assert lue == demande, "le TUI ne reconstruit pas fidèlement la demande"


def test_un_graphe_sans_interruption_ne_rend_rien():
    from src.ui.streaming import _demande_du_graphe

    assert _demande_du_graphe(_Graphe(SimpleNamespace(tasks=())), {}) is None


def test_un_graphe_injoignable_ne_casse_pas_le_tour():
    """Un `get_state` qui lève ne doit pas faire tomber la session : au pire on
    ne voit pas la demande, et le tour se termine normalement."""
    from src.ui.streaming import _demande_du_graphe

    class _Cassé:
        def get_state(self, config):
            raise RuntimeError("indisponible")

    assert _demande_du_graphe(_Cassé(), {}) is None


def test_une_panne_d_affichage_ne_vaut_pas_accord(monkeypatch):
    """Le point qui compte pour la sécurité. Si le questionnaire échoue, on rend
    des réponses VIDES — lues comme un refus. Rendre une valeur par défaut, ou
    laisser l'exception filer et reprendre plus tard, produirait un accord que
    personne n'a donné."""
    from src.orchestrator.commun.hitl import accorde
    from src.ui import review

    monkeypatch.setattr(review, "ask_user_questions",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("terminal perdu")))

    question = Question("Exécuter ?", ("Non", "Oui"), affirmatif="Oui")
    reponses = review.servir_demande(Demande(
        genre="autorisation", cle="rm -rf /", questions=(question,)))

    assert reponses == [""]
    assert not accorde(reponses[0], question)


def test_les_reponses_sont_rendues_DANS_L_ORDRE_des_questions(monkeypatch):
    """`ask_user_questions` rend un dict indexé par le texte ; le graphe attend
    l'ordre. Les confondre décalerait les réponses d'une question — silencieux,
    et faux."""
    from src.ui import review

    monkeypatch.setattr(review, "ask_user_questions",
                        lambda posees: {"Deuxième ?": "B", "Première ?": "A"})

    reponses = review.servir_demande(Demande(
        genre="clarification", cle="x",
        questions=(Question("Première ?"), Question("Deuxième ?"))))

    assert reponses == ["A", "B"]


def test_une_reponse_absente_devient_du_vide(monkeypatch):
    from src.ui import review

    monkeypatch.setattr(review, "ask_user_questions", lambda posees: {})
    reponses = review.servir_demande(Demande(
        genre="clarification", cle="x",
        questions=(Question("A ?"), Question("B ?"))))
    assert reponses == ["", ""]


# Les trois tests du client API ont été retirés avec `src/api/` : l'endpoint
# compatible OpenAI (brancher Axon dans Zed, Cursor, Continue.dev) ne servait
# pas. Ce qu'ils gardaient — que la LECTURE de la demande soit commune à tous
# les transports — n'a plus qu'un seul transport à garder : le terminal.
