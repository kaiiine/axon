"""Lire le contenu d'un message, quel que soit sa forme.

Un contenu de message est tantôt une chaîne, tantôt une LISTE de blocs
(`{"type": "text", ...}`, `{"type": "image_url", ...}`) dès qu'une image entre
dans la conversation. `str(content)` sur cette liste rend la représentation
Python de la liste — crochets, accolades et blob base64 compris.

Deux endroits aplatissaient déjà ce contenu chacun de leur côté : une closure
`_content_to_str` dans le nœud `chatbot`, et `_texte_du_contenu` dans
`context.py` — celui-ci rend un couple (texte, coût des images) parce qu'il
compte des tokens, c'est un autre métier. Ici, uniquement le texte.
"""
from __future__ import annotations


def texte_du_contenu(content) -> str:
    """Le texte d'un contenu de message, liste de blocs multimodaux comprise."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p)
            for p in content
        )
    return str(content)
