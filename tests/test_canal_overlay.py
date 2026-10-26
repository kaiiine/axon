"""src/infra/canal_overlay.py et src/infra/notifications.py — le même
protocole sur Linux, macOS et Windows."""
from __future__ import annotations

import json
import socket
import threading

import pytest

from src.infra import canal_overlay, notifications


def _serveur_unix(chemin):
    serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    serveur.bind(str(chemin))
    serveur.listen(1)
    serveur.settimeout(2)
    return serveur


def test_un_message_ponctuel_arrive_par_le_socket_unix(tmp_path, monkeypatch):
    monkeypatch.setattr(canal_overlay, "dossier", lambda: tmp_path)
    serveur = _serveur_unix(tmp_path / "controle.sock")
    try:
        assert canal_overlay.envoyer_une_fois("controle", {"type": "basculer"})
        client, _ = serveur.accept()
        assert json.loads(client.makefile().readline()) == {"type": "basculer"}
        client.close()
    finally:
        serveur.close()


def test_sans_ile_l_envoi_echoue_sans_lever(tmp_path, monkeypatch):
    monkeypatch.setattr(canal_overlay, "dossier", lambda: tmp_path)
    assert canal_overlay.envoyer_une_fois("controle", {"type": "basculer"}) is False


def test_sous_windows_le_client_presente_le_jeton_publie(tmp_path, monkeypatch):
    monkeypatch.setattr(canal_overlay, "WINDOWS", True)
    monkeypatch.setattr(canal_overlay, "dossier", lambda: tmp_path)
    serveur = socket.create_server(("127.0.0.1", 0))
    serveur.settimeout(2)
    (tmp_path / "controle.json").write_text(
        json.dumps({"port": serveur.getsockname()[1], "jeton": "secret"}), encoding="utf-8")
    recu: list = []

    def accepter():
        client, _ = serveur.accept()
        with client, client.makefile() as flux:
            recu.extend(json.loads(flux.readline()) for _ in range(2))

    fil = threading.Thread(target=accepter)
    fil.start()
    try:
        assert canal_overlay.envoyer_une_fois("controle", {"type": "rappel"})
        fil.join(2)
    finally:
        serveur.close()
    assert recu == [{"jeton": "secret"}, {"type": "rappel"}]


def test_sous_windows_une_adresse_illisible_vaut_ile_absente(tmp_path, monkeypatch):
    monkeypatch.setattr(canal_overlay, "WINDOWS", True)
    monkeypatch.setattr(canal_overlay, "dossier", lambda: tmp_path)
    (tmp_path / "controle.json").write_text("pas du json", encoding="utf-8")
    with pytest.raises(OSError):
        canal_overlay.connecter("controle")


@pytest.mark.parametrize("plateforme, programme", [
    ("linux", "notify-send"), ("darwin", "osascript"), ("win32", "powershell")])
def test_chaque_systeme_a_sa_notification_native(monkeypatch, plateforme, programme):
    monkeypatch.setattr(notifications.sys, "platform", plateforme)
    assert notifications._commande("Titre", "Texte")[0] == programme


def test_le_texte_d_un_rappel_n_est_jamais_interprete(monkeypatch):
    """Arguments séparés (macOS) ou variables d'environnement (Windows) : un
    rappel contenant des guillemets ne peut rien exécuter."""
    piege = 'x" & do shell script "rm -rf ~'
    monkeypatch.setattr(notifications.sys, "platform", "darwin")
    commande = notifications._commande("Titre", piege)
    assert commande[-1] == piege and all(piege not in a for a in commande[:-1])

    monkeypatch.setattr(notifications.sys, "platform", "win32")
    assert all(piege not in a for a in notifications._commande("Titre", piege))
    assert notifications._environnement("Titre", piege)["AXON_TEXTE"] == piege
