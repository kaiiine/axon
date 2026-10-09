"""Une image jointe ne doit pas être tokenisée par son base64.

Vécu à l'écran : « Que peux tu me dire sur cette photo » puis un
« compiling… résumé du contexte » qui ne semblait plus finir. Le contenu
multimodal d'un `HumanMessage` — `[{"type": "text", ...}, {"type":
"image_url", "image_url": {"url": "data:...;base64,<blob>"}}]` — n'est pas
une chaîne, mais `_estimate_tokens` faisait `str(content)` dessus : le blob
base64 entier partait dans le tokenizer BPE.

Mesuré sur une capture d'écran réaliste de 800 Ko : **728 319 tokens comptés**
pour une seule image — dix fois le budget usable d'un backend par défaut
(128 000 × 0,6 ≈ 77 000). `_should_compress` restait vrai en permanence, et
l'image ne quittant jamais la fenêtre « récente » de la compression (rien ne
la plafonne, contrairement aux `ToolMessage` via `_cap_tool_messages`), rien
ne faisait redescendre le compte sous le seuil.
"""
from __future__ import annotations

import base64
import os

from langchain_core.messages import AIMessage, HumanMessage

from src.orchestrator.modele.context import (
    _TOKENS_PAR_IMAGE, _estimate_tokens, _texte_du_contenu, _usable_budget,
)


def _message_avec_image(taille_octets: int = 800_000) -> HumanMessage:
    blob = base64.b64encode(os.urandom(taille_octets)).decode()
    return HumanMessage(content=[
        {"type": "text", "text": "Que peux tu me dire sur cette photo"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{blob}"}},
    ])


# ── le cas vécu ────────────────────────────────────────────────────────────
def test_une_image_ne_gonfle_plus_le_compte():
    """Avant le correctif : 728 319. Une marge large plutôt qu'un chiffre exact
    — la taille dépend de la capture, l'ORDRE DE GRANDEUR est ce qui compte."""
    n = _estimate_tokens([_message_avec_image()])

    assert n < 5_000


def test_une_image_tient_sous_le_budget_usable():
    """Le test qui aurait dû empêcher le bug : une seule pièce jointe ne doit
    jamais, à elle seule, déclencher la compression."""
    n = _estimate_tokens([_message_avec_image()])

    assert n < _usable_budget("ollama_cloud") * 0.1


def test_plusieurs_images_saccumulent_lineairement():
    contenu = [{"type": "text", "text": "compare"}] + [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}
        for _ in range(3)
    ]
    n = _estimate_tokens([HumanMessage(content=contenu)])

    assert n >= 3 * _TOKENS_PAR_IMAGE


# ── ce qui ne doit pas changer ────────────────────────────────────────────
def test_un_message_texte_seul_est_inchange():
    texte = HumanMessage(content="une question simple, sans pièce jointe")

    assert _estimate_tokens([texte]) < 20


def test_les_tool_calls_restent_comptes():
    ai = AIMessage(content="", tool_calls=[{"name": "x", "args": {"a": 1}, "id": "1"}])

    assert _estimate_tokens([ai]) > 0


def test_un_bloc_de_contenu_sans_type_connu_ne_leve_pas():
    """Un fournisseur peut renvoyer une forme qu'on n'anticipe pas — ça ne doit
    jamais faire planter le compte, seulement le sous-estimer proprement."""
    m = HumanMessage(content=[{"quelque_chose": "d'inattendu"}])

    assert _estimate_tokens([m]) >= 0


# ── l'extraction elle-même ────────────────────────────────────────────────
def test_texte_du_contenu_separe_texte_et_images():
    texte, cout = _texte_du_contenu([
        {"type": "text", "text": "vois-tu ceci ?"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,XXXX"}},
    ])

    assert "vois-tu ceci" in texte
    assert "XXXX" not in texte
    assert cout == _TOKENS_PAR_IMAGE


def test_texte_du_contenu_sur_une_chaine_simple():
    texte, cout = _texte_du_contenu("juste du texte")

    assert texte == "juste du texte"
    assert cout == 0
