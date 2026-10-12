"""Generic arrow-key option picker (prompt_toolkit)."""
from __future__ import annotations

from typing import List

from prompt_toolkit import Application
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

_ACCENT_PT = "ansiyellow"

_PT_STYLE = Style.from_dict({
    "selected": f"bold {_ACCENT_PT}",
    "normal":   "ansiwhite",
    "hint":     f"{_ACCENT_PT}",
    "title":    f"bold {_ACCENT_PT}",
})


def pick(options: List[str], title: str = "", current: str = "") -> str | None:
    """
    Vertical list navigable with ↑↓. Returns selected option or None if cancelled.
    Pre-selects `current` if present in the list.

    Essaie d'abord l'île si elle est connectée — même protocole que les autres
    demandes (`src/orchestrator/commun/hitl.py`), pas un canal à part. Avant
    ce correctif, /backend, /model, /mode et le wizard /spec ne proposaient ce
    choix qu'au terminal, jamais à l'île, même avec elle ouverte et connectée.
    Si l'île ne répond pas (absente, hors délai, déconnectée en cours de
    route), on retombe sur le picker terminal ci-dessous — jamais de blocage
    silencieux en attendant une île qui ne viendra pas.
    """
    if not options:
        return None

    from src.ui.pont_overlay import pont
    if pont.connecte:
        from src.orchestrator.commun.hitl import CLARIFICATION, Demande, Question
        demande = Demande(
            genre=CLARIFICATION, cle=title,
            # libre=False : une valeur hors `options` n'a pas de sens ici (pas
            # de "backend personnalisé"), donc pas d'« Autre » à proposer —
            # contrairement à une vraie clarification, où `libre` reste True.
            questions=(Question(texte=title or "Choisis une option", choix=tuple(options), libre=False),),
        )
        reponses = pont.demander(demande.en_clair())
        if reponses is not None:
            # Une réponse "Autre" côté île qui ne correspond à aucune option
            # n'est pas une vraie sélection ici — annulé plutôt qu'accepté
            # au hasard, et surtout pas re-proposé au terminal (l'utilisateur
            # vient de répondre, le re-demander ailleurs serait déroutant).
            return reponses[0] if reponses[0] in options else None

    try:
        start = options.index(current)
    except ValueError:
        start = 0

    idx = [start]

    def get_tokens():
        parts: list = []
        if title:
            parts.append(("class:title", f"  {title}\n\n"))
        for i, opt in enumerate(options):
            star = "  ★" if opt == current else ""
            if i == idx[0]:
                parts.append(("class:selected", f"  ▶  {opt}{star}\n"))
            else:
                parts.append(("class:normal",   f"     {opt}{star}\n"))
        parts.append(("class:hint", "\n  ↑↓ · Entrée · Échap"))
        return parts

    kb = KeyBindings()

    @kb.add("down")
    @kb.add("tab")
    def _fwd(event):
        idx[0] = (idx[0] + 1) % len(options)

    @kb.add("up")
    @kb.add("s-tab")
    def _bwd(event):
        idx[0] = (idx[0] - 1) % len(options)

    @kb.add("enter")
    def _ok(event):
        event.app.exit(result=options[idx[0]])

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit(result=None)

    height = len(options) + (3 if title else 1) + 2
    app = Application(
        layout=Layout(
            Window(
                FormattedTextControl(get_tokens, focusable=True),
                height=height,
            )
        ),
        key_bindings=kb,
        style=_PT_STYLE,
        full_screen=False,
        mouse_support=False,
    )
    return app.run()
