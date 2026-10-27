"""Une panne serveur se réessaie ; elle ne tue pas le tour.

Vécu, en plein nettoyage disque :

    erreur : Internal Server Error (ref: 31d9307d-…) (status code: -1)

Le tour était perdu, avec l'erreur brute à l'écran. Or `classify()` rangeait ce
cas dans `unknown`, dont l'échelle est faite pour « le provider REFUSE notre
requête » — modèle retiré, schéma d'outil invalide. Elle fait tourner les clés,
puis retire les outils. Aucun de ces remèdes ne répare une panne serveur, et le
second dégrade le tour pour rien.

Un 500 est pourtant de la même nature qu'une coupure de flux, déjà traitée :
le serveur a échoué APRÈS avoir accepté, rien n'a été livré, aucun outil n'a pu
s'exécuter. Réémettre est sûr — c'est le raisonnement que le module tenait déjà
pour `IncompleteRead`, et il vaut mot pour mot ici.

Une seule chose change : la CLASSIFICATION. J'avais aussi voulu faire basculer
les réessais épuisés sur l'échelle dégradée ; un test existant l'a refusé, à
raison — cette échelle retire les outils, et répondre sans outils à « supprime
ces fichiers » produit un texte plausible au lieu d'une action.
"""
import pytest

from src.orchestrator.modele.invocation import MAX_TRANSIENT_RETRIES, classify


@pytest.mark.parametrize("message", [
    "Internal Server Error (ref: 31d9307d-8967-4426-aae8-e12f9550e199) (status code: -1)",
    "HTTP 500 Internal Server Error",
    "502 Bad Gateway",
    "503 Service Unavailable",
    "504 Gateway Timeout",
    "overloaded_error: the model is overloaded",
])
def test_une_panne_serveur_est_passagere(message):
    """Le serveur a accepté puis échoué : réémettre est sûr et suffisant."""
    assert classify(Exception(message)) == "transient"


def test_le_message_exact_de_l_incident():
    """Celui qui a tué le tour, mot pour mot."""
    exc = Exception("Internal Server Error (ref: 31d9307d-8967-4426-aae8-e12f9550e199) "
                    "(status code: -1)")

    assert classify(exc) == "transient"


# ── Les autres classes ne bougent pas ─────────────────────────────────────────
@pytest.mark.parametrize("message, attendu", [
    ("429 Too Many Requests", "rate_limit"),
    ("quota exceeded", "rate_limit"),
    ("maximum context length exceeded", "context"),
    ("IncompleteRead(66316 bytes read)", "transient"),
    ("connection reset by peer", "transient"),
    ("ValueError: argument invalide", "unknown"),
])
def test_les_autres_classes_restent_intactes(message, attendu):
    """Élargir `transient` ne doit pas avaler ce qui appelait un autre remède :
    un rate-limit veut une clé, un contexte trop long veut une compression."""
    assert classify(Exception(message)) == attendu


def test_une_erreur_de_code_reste_inconnue():
    """Réessayer un bug de programmation trois fois ne le répare pas — et
    masquerait la cause derrière un délai."""
    assert classify(TypeError("can only concatenate str")) == "unknown"


# ── L'échelle ne renonce plus trop tôt ────────────────────────────────────────
def test_les_reessais_epuises_renoncent_franchement():
    """J'avais d'abord fait basculer les réessais épuisés sur l'échelle dégradée.
    Un test existant l'a refusé, et il avait raison : cette échelle finit par
    RETIRER LES OUTILS, et répondre sans outils à « supprime ces fichiers »
    produit un texte plausible au lieu d'une action.

    Face à un réseau qui reste coupé, une erreur franche vaut mieux qu'une
    réponse qui fait semblant. Le correctif utile était la classification, pas
    l'obstination.
    """
    import inspect

    from src.orchestrator.modele import invocation

    source = inspect.getsource(invocation.invoke_with_recovery)
    # On borne au bloc `transient` lui-même — jusqu'au `continue` qui le clôt —
    # plutôt qu'à un nombre de caractères : un commentaire ajouté décalerait la
    # fenêtre et ferait tomber le test sans que le code ait changé. C'est
    # exactement ce qui vient de m'arriver.
    debut = source.index('if genre == "transient"')
    bloc = source[debut:source.index("continue", debut)]

    assert "raise" in bloc


def test_le_plafond_de_reessais_reste_borne():
    """Sans borne, une panne durable boucle au lieu de rendre la main."""
    assert 1 <= MAX_TRANSIENT_RETRIES <= 5


# ── Une panne serveur répétée : une relance reformulée, outils gardés ─────────
class _LLMQuiNote:
    """Lève tant qu'on lui donne des erreurs ; garde ce qu'il a reçu."""

    def __init__(self, *erreurs):
        self.restantes = list(erreurs)
        self.recus: list = []

    def invoke(self, messages):
        self.recus.append(list(messages))
        if self.restantes:
            raise self.restantes.pop(0)
        return "ok"

    def bind_tools(self, tools):
        return self


def _invoquer_sans_attente(llm):
    from src.orchestrator.modele.invocation import invoke_with_recovery
    return invoke_with_recovery(
        llm, [], backend="ollama_cloud", factory=lambda: llm, selected_tools=[],
        force_text=False, on_compress=lambda: None, sleep=lambda _s: None)


def test_quatre_500_d_affilee_donnent_une_relance_reformulee():
    """Vécu : quatre 500 sur la même requête, le tour mourait avec deux
    échéances créées sur cinq. Réémettre à l'identique ne changeait rien."""
    panne = Exception("Internal Server Error (ref: x) (status code: 500)")
    llm = _LLMQuiNote(*[panne] * (MAX_TRANSIENT_RETRIES + 1))

    assert _invoquer_sans_attente(llm).response == "ok"
    derniere = llm.recus[-1]
    assert "[SYSTEME] Le serveur du modèle a échoué" in str(derniere[-1].content)
    assert all("[SYSTEME]" not in str(m) for m in llm.recus[0])


def test_la_relance_reformulee_n_a_lieu_qu_une_fois():
    panne = Exception("Internal Server Error (status code: 500)")
    llm = _LLMQuiNote(*[panne] * (MAX_TRANSIENT_RETRIES + 3))

    with pytest.raises(Exception, match="Internal Server Error"):
        _invoquer_sans_attente(llm)
    assert len(llm.recus) == MAX_TRANSIENT_RETRIES + 2


def test_une_coupure_reseau_ne_declenche_pas_de_reformulation():
    coupure = Exception("connection reset")
    llm = _LLMQuiNote(*[coupure] * (MAX_TRANSIENT_RETRIES + 1))

    with pytest.raises(Exception, match="connection reset"):
        _invoquer_sans_attente(llm)
    assert len(llm.recus) == MAX_TRANSIENT_RETRIES + 1


# ── Un quota sans autre clé : une courte attente, puis on renonce ─────────────
def test_un_quota_sans_autre_cle_attend_puis_reussit(monkeypatch):
    """Vécu : « Hello ça va ? » → 429 de Mistral, une seule clé, abandon
    immédiat. Une limite par seconde se lève en attendant."""
    from src.orchestrator.modele import invocation
    monkeypatch.setattr(invocation, "_log_failure", lambda *a, **k: None)
    attentes = []
    quota = Exception("Error response 429: Rate limit exceeded")
    llm = _LLMQuiNote(quota)
    issue = invocation.invoke_with_recovery(
        llm, [], backend="mistral", factory=lambda: llm, selected_tools=[], force_text=False,
        on_compress=lambda: None, sleep=attentes.append)
    assert issue.response == "ok"
    assert attentes == [invocation.DELAI_QUOTA_S]


def test_un_quota_qui_persiste_finit_par_une_erreur(monkeypatch):
    from src.orchestrator.modele import invocation
    monkeypatch.setattr(invocation, "_log_failure", lambda *a, **k: None)
    attentes = []
    llm = _LLMQuiNote(*[Exception("429 Too Many Requests")] * (invocation.MAX_ATTENTES_QUOTA + 1))
    with pytest.raises(Exception, match="429"):
        invocation.invoke_with_recovery(
            llm, [], backend="mistral", factory=lambda: llm, selected_tools=[], force_text=False,
            on_compress=lambda: None, sleep=attentes.append)
    assert len(attentes) == invocation.MAX_ATTENTES_QUOTA


def test_un_modele_hors_offre_ne_fait_pas_attendre_pour_rien(monkeypatch):
    """Vécu : `mistral-small-2603` répond 429 avec une limite de 0 requête par
    minute — le modèle n'est pas dans l'offre. Attendre ne lève rien."""
    from types import SimpleNamespace

    from src.orchestrator.modele import invocation
    monkeypatch.setattr(invocation, "_log_failure", lambda *a, **k: None)
    hors_offre = Exception("Error response 429: Rate limit exceeded")
    hors_offre.response = SimpleNamespace(headers={"x-ratelimit-limit-req-minute": "0"})
    attentes = []
    llm = _LLMQuiNote(hors_offre)
    with pytest.raises(Exception, match="429"):
        invocation.invoke_with_recovery(
            llm, [], backend="mistral", factory=lambda: llm, selected_tools=[], force_text=False,
            on_compress=lambda: None, sleep=attentes.append)
    assert attentes == []
    assert invocation.modele_hors_offre(hors_offre)
