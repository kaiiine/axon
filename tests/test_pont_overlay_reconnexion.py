"""src/ui/pont_overlay.py — l'île lancée APRÈS le CLI finit par être jointe.

Avant : le CLI ne tentait la connexion qu'au démarrage, puis à chaque envoi.
Une île démarrée quelques secondes plus tard restait « hors ligne » tant que
le CLI, en attente de saisie, n'avait rien à dire.
"""
from __future__ import annotations

import socket
import time

import src.ui.pont_overlay as module
from src.ui.pont_overlay import PontOverlay


def test_une_ile_lancee_apres_le_cli_est_jointe_sans_envoi(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_DELAI_RECONNEXION", 0.05)
    chemin = tmp_path / "overlay.sock"
    pont = PontOverlay(chemin)
    assert pont.activer() is False          # pas encore d'île

    serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    serveur.bind(str(chemin))
    serveur.listen(1)
    serveur.settimeout(2)
    try:
        client, _ = serveur.accept()        # le CLI vient de lui-même
        client.close()
    finally:
        pont.actif = False
        pont.actif = False
        serveur.close()


def test_un_pont_jamais_active_ne_tente_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "_DELAI_RECONNEXION", 0.05)
    chemin = tmp_path / "overlay.sock"
    serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    serveur.bind(str(chemin))
    serveur.listen(1)
    serveur.settimeout(0.3)
    PontOverlay(chemin)                     # importé par un test ou un script
    try:
        time.sleep(0.2)
        try:
            serveur.accept()
            raise AssertionError("un pont inactif s'est connecté à l'île")
        except socket.timeout:
            pass
    finally:
        serveur.close()
