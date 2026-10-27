"""Les canaux locaux entre Axon et l'île, quel que soit le système.

Deux canaux nommés, un même protocole (une ligne JSON par message) :

- `overlay` : la session CLI. L'île n'accepte qu'un client à la fois.
- `controle` : les messages ponctuels — rappels du démon, bascule de l'île.

Seul le transport dépend du système :

- Linux, macOS : un socket Unix `<dossier>/<nom>.sock`, protégé par ses droits
  (dossier 0700, socket 0600).
- Windows : TCP sur 127.0.0.1. Le serveur publie `<dossier>/<nom>.json`
  (`port`, `jeton`) dans le profil de l'utilisateur ; le client envoie le jeton
  en première ligne, l'île ferme toute connexion qui ne le présente pas.

Côté Python, ce module n'est que client : les serveurs sont l'île GTK (Linux)
et l'enveloppe Tauri (dépôt `axon-overlay`, `src-tauri`). Bibliothèque standard uniquement —
l'île et le démon cron tournent sans le reste d'Axon.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from pathlib import Path

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"

OVERLAY = "overlay"
CONTROLE = "controle"


def dossier() -> Path:
    """Le dossier d'exécution partagé avec l'île (sockets, adresses, PID)."""
    if WINDOWS:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "axon" / "run"
    if MACOS:
        # `$TMPDIR` est propre à l'utilisateur sous macOS, et assez court pour
        # rester sous la limite de 104 octets d'un chemin de socket Unix.
        return Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / "axon"
    return Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "axon"


def chemin_unix(nom: str) -> Path:
    return dossier() / f"{nom}.sock"


def adresse_windows(nom: str) -> Path:
    return dossier() / f"{nom}.json"


def connecter(nom: str, *, delai: float | None = None,
              chemin: Path | None = None) -> socket.socket:
    """Ouvre le canal `nom`. Lève `OSError` si l'île n'écoute pas.

    `chemin` force un socket Unix précis (tests, île lancée ailleurs).
    """
    if WINDOWS and chemin is None:
        return _connecter_tcp(nom, delai)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        if delai is not None:
            s.settimeout(delai)
        s.connect(str(chemin or chemin_unix(nom)))
        s.settimeout(None)
    except OSError:
        s.close()
        raise
    return s


def _connecter_tcp(nom: str, delai: float | None) -> socket.socket:
    try:
        adresse = json.loads(adresse_windows(nom).read_text(encoding="utf-8"))
        port, jeton = int(adresse["port"]), str(adresse["jeton"])
    except (ValueError, KeyError, TypeError) as erreur:
        raise OSError(f"adresse de l'île illisible : {erreur}") from erreur
    s = socket.create_connection(("127.0.0.1", port), timeout=delai)
    try:
        s.sendall((json.dumps({"jeton": jeton}) + "\n").encode("utf-8"))
        s.settimeout(None)
    except OSError:
        s.close()
        raise
    return s


def envoyer_une_fois(nom: str, message: dict, delai: float = 2.0) -> bool:
    """Envoie un message isolé puis ferme. False si l'île n'écoute pas."""
    ligne = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with connecter(nom, delai=delai) as s:
            s.sendall(ligne)
        return True
    except OSError:
        return False
