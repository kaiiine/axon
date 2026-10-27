"""La ligne de saisie : son clavier, son prompt, son historique.

Sortie de `streaming.py`, où elle cohabitait avec la boucle de streaming, le
rendu des fiches et l'export des lettres — quatre métiers dans un fichier de
2 079 lignes. Celui-ci ne parle qu'à `prompt_toolkit` : aucune notion de graphe,
d'état de conversation ni de modèle.
"""
from __future__ import annotations

import os

from prompt_toolkit import PromptSession
from prompt_toolkit.filters import Condition
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from src.infra import chemins as _chemins

from .attachments import attachments as _attachments
from .completer import SlashCompleter
from .suggest import HistorySuggest

_pt_style = Style.from_dict({
    "axon":       "bold ansiyellow",
    "sep":        "ansiyellow",
    # Plan mode badge in the prompt
    "plan-badge": "bold bg:#1a0d00 fg:#ffaf00",
    # Completion dropdown — dark, minimal, orange accent on selection
    "completion-menu":                         "bg:#1a1a1a #606060",
    "completion-menu.completion":              "bg:#1a1a1a #606060",
    "completion-menu.completion.current":      "bg:#242424 bold fg:#ffaf00",
    "completion-menu.meta.completion":         "bg:#141414 #404040",
    "completion-menu.meta.completion.current": "bg:#1e1e1e #606060",
    "scrollbar.background":                    "bg:#1a1a1a",
    "scrollbar.button":                        "bg:#404040",
    # Suggestion de saisie — délibérément plus sombre que tout le reste : elle
    # doit se lire comme une ombre, jamais se confondre avec ce qui est tapé.
    "auto-suggestion":                         "#4a4a4a",
})

@Condition
def _suggestion_affichee() -> bool:
    """Une suggestion est-elle visible et acceptable à cet instant ?

    Filtre de la liaison Tab. Quand il rend faux, prompt_toolkit retombe sur la
    liaison par défaut — Tab redevient la complétion du menu. C'est ce qui permet
    aux deux mécanismes de partager la touche sans se marcher dessus : le menu
    garde `/commande` et `@fichier`, la suggestion prend le reste.
    """
    from prompt_toolkit.application import get_app

    try:
        buf = get_app().current_buffer
    except Exception:
        return False
    return (buf.suggestion is not None
            and bool(buf.suggestion.text)
            and buf.complete_state is None
            and buf.document.is_cursor_at_the_end)


def _make_keybindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("tab", filter=_suggestion_affichee)
    def _kb_accepter_suggestion(event):
        """Tab écrit la suggestion — le seul geste qui l'insère jamais."""
        buf = event.current_buffer
        if buf.suggestion:
            buf.insert_text(buf.suggestion.text)

    @kb.add("c-o")
    def _kb_attach(event):
        event.current_buffer.text = "/attach"
        event.current_buffer.validate_and_handle()

    @kb.add("c-p")
    def _kb_paste(event):
        from .attachments import get_clipboard_image
        img = get_clipboard_image()
        if img:
            _attachments.add_clipboard_image(img)
        event.app.invalidate()

    @kb.add("c-t")
    def _kb_plan(event):
        from .plan_mode import toggle
        toggle()
        event.app.invalidate()

    @kb.add("c-d")
    def _kb_detach(event):
        _attachments.pop_all()
        event.app.invalidate()

    # ── Saisie multi-ligne ────────────────────────────────────────────────────
    #
    # La session passe en `multiline=True`, ce qui INVERSE le rôle d'Entrée :
    # par défaut elle insérerait un retour à la ligne et plus rien n'enverrait.
    # Ces deux liaisons rétablissent le geste attendu — Entrée envoie, une autre
    # touche va à la ligne.
    #
    # Plusieurs touches pour aller à la ligne, et ce n'est pas de la générosité.
    #
    # prompt_toolkit 3.0.52 NE CONNAÎT PAS Maj+Entrée : `enter` est un alias de
    # `c-m`, et l'énumération des touches n'a aucune variante shift pour elle —
    # vérifié, `s-tab` et `s-left` existent, rien pour entrée. La raison est en
    # amont : la plupart des terminaux envoient le même octet `\r` pour Entrée et
    # Maj+Entrée, donc il n'y a rien à distinguer.
    #
    # Deux réponses, complémentaires :
    #   · Alt+Entrée et Ctrl+J, que TOUT terminal émet distinctement — ce sont
    #     elles qui garantissent que la fonctionnalité marche partout ;
    #   · la séquence du protocole clavier kitty (`ESC [ 13 ; 2 u`), qu'émettent
    #     kitty, ghostty, WezTerm et foot quand le protocole est actif. Là où
    #     c'est le cas, Maj+Entrée marche vraiment ; ailleurs la séquence
    #     n'arrive jamais et la liaison dort sans gêner personne.

    @kb.add("enter")
    def _kb_envoyer(event):
        """Entrée envoie, toujours.

        Une version précédente validait d'abord la complétion ouverte, en croyant
        éviter qu'Entrée n'envoie au lieu d'insérer `/build`. C'était faux et
        mesuré comme tel : dans prompt_toolkit, Tab INSÈRE déjà la complétion
        dans le tampon tout en laissant `current_completion` renseigné. La
        condition ne distinguait donc pas « en attente » de « déjà écrite »,
        Entrée réappliquait la complétion, et la saisie ne se terminait jamais —
        deux tests de complétion restaient bloqués indéfiniment.
        """
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    @kb.add("c-j")
    @kb.add("escape", "[", "1", "3", ";", "2", "u")
    def _kb_nouvelle_ligne(event):
        """Alt+Entrée · Ctrl+J · Maj+Entrée (terminaux au protocole kitty)."""
        event.current_buffer.insert_text("\n")

    return kb


def _continuation(largeur: int, ligne: int, doit_envelopper: bool):
    """Le préfixe des lignes 2 et suivantes d'une saisie multi-ligne.

    Aligné sur le « › » de la première ligne : sans lui, prompt_toolkit met des
    points de suite qui ne ressemblent à rien de la DA, et le texte se décale
    d'une colonne à chaque nouvelle ligne.
    """
    from prompt_toolkit.formatted_text import ANSI

    return ANSI("\033[2m\033[38;5;214m│ \033[0m")


def _prompt_tokens():
    """Dynamic prompt: separator line + indicator, using raw ANSI codes to match Rich exactly."""
    import shutil
    from prompt_toolkit.formatted_text import ANSI
    from .plan_mode import is_active as _plan_active

    try:
        width = shutil.get_terminal_size((120, 24)).columns
    except Exception:
        width = 120

    DIM = "\033[2m\033[38;5;214m"  # dim color(214) — exactly what Rich emits
    RST = "\033[0m"

    items: list[str] = []
    if _plan_active():
        items.append("◆ PLAN")
    for a in _attachments.items:
        icon = "📷" if a.is_image else "📎"
        items.append(f"{icon} {a.name}  [{a.size_hint}]")

    if items:
        title = "  ·  ".join(items)
        title_display = f" {title} "
        tlen = sum(2 if ord(c) > 0x2000 else 1 for c in title_display)
        pad_l = max(1, (width - tlen) // 2)
        pad_r = max(1, width - pad_l - tlen)
        sep = DIM + "·" * pad_l + RST + title_display + DIM + "·" * pad_r + RST
    else:
        sep = DIM + "·" * width + RST

    indicator = "\033[33m› \033[0m" if not _plan_active() else "\033[1m\033[38;5;214m PLAN \033[0m  "

    return ANSI(sep + "\n" + indicator)


def _historique():
    """Historique de saisie, persistant entre les sessions.

    Une suggestion tirée d'un historique en mémoire ne servirait à rien : elle
    n'existerait qu'après avoir déjà retapé la phrase dans la MÊME session. Le
    fichier vit dans `~/.axon/`, avec la base de threads — il contient donc tout
    ce qui a été saisi, en clair, et se supprime sans conséquence.

    Un disque en lecture seule ou un `$HOME` absent retombe en mémoire : la
    saisie doit démarrer même sans persistance.
    """
    try:
        chemin = _chemins.historique_saisie()
        chemin.parent.mkdir(parents=True, exist_ok=True)
        return FileHistory(str(chemin))
    except Exception:
        return InMemoryHistory()


def build_session(**overrides) -> PromptSession:
    """Fabrique la session de saisie — un seul endroit la configure.

    Les `overrides` servent aux tests, qui rejouent des frappes sur une session
    identique à celle du produit avec une entrée/sortie factice. Sans cette
    fabrique, la liaison Tab ne serait vérifiable que manuellement.
    """
    options = dict(
        history=_historique(),
        style=_pt_style,
        mouse_support=False,
        key_bindings=_make_keybindings(),
        completer=SlashCompleter(),
        complete_while_typing=True,
        auto_suggest=HistorySuggest(),
        # Le tampon accepte les retours à la ligne ; ce sont les liaisons de
        # `_make_keybindings` qui décident quelle touche envoie et laquelle va à
        # la ligne. Sans `multiline`, aucune touche ne peut insérer de retour.
        # Bascule de DIAGNOSTIC : `AXON_SAISIE_SIMPLE=1` revient à la saisie
        # d'une seule ligne. Elle sert à trancher une question qu'on ne peut
        # pas trancher sans vrai terminal — le multi-ligne change la hauteur
        # de l'invite, donc la position où Rich croit démarrer sa région.
        multiline=not os.getenv("AXON_SAISIE_SIMPLE"),
        prompt_continuation=_continuation,
    )
    options.update(overrides)
    return PromptSession(**options)


_session: PromptSession = build_session()


def _attachment_hint() -> str:
    if not _attachments:
        return ""
    names = "  ·  ".join(f"📎 {a.name}" for a in _attachments.items)
    return f"  {names}  "
