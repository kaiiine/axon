"""src/ui/attachments.py — l'île s'efface pendant le sélecteur de fichier natif.

Sans ce signal, l'île (couche layer-shell TOP) recouvre le dialogue zenity/
kdialog. Le retour au premier plan doit arriver même si le dialogue lève.
"""
from __future__ import annotations

import pytest

import src.ui.attachments as attachments
from src.ui.pont_overlay import pont


@pytest.fixture
def envois(monkeypatch):
    messages: list[dict] = []
    monkeypatch.setattr(pont, "envoyer", lambda **m: messages.append(m) or True)
    return messages


def test_l_ile_s_efface_pendant_le_choix_puis_revient(monkeypatch, envois):
    monkeypatch.setattr(attachments, "_ouvrir_selecteur_natif", lambda dossier=False: "/tmp/cours.pdf")

    assert attachments.open_file_picker() == "/tmp/cours.pdf"
    assert envois == [
        {"type": "selecteur_fichier", "ouvert": True},
        {"type": "selecteur_fichier", "ouvert": False},
    ]


def test_l_ile_revient_meme_si_le_selecteur_echoue(monkeypatch, envois):
    def plantage(dossier=False):
        raise RuntimeError("dialogue indisponible")
    monkeypatch.setattr(attachments, "_ouvrir_selecteur_natif", plantage)

    with pytest.raises(RuntimeError):
        attachments.open_file_picker()
    assert envois[-1] == {"type": "selecteur_fichier", "ouvert": False}


def test_annuler_zenity_n_ouvre_pas_un_second_dialogue(monkeypatch):
    """zenity présent mais annulé (code 1) : on s'arrête là, sans enchaîner
    sur kdialog puis tkinter — sinon un deuxième dialogue surgit."""
    import subprocess
    appels = []

    def faux_run(commande, **_k):
        appels.append(commande[0])
        return subprocess.CompletedProcess(commande, 1, stdout="", stderr="")
    monkeypatch.setattr(subprocess, "run", faux_run)

    assert attachments._ouvrir_selecteur_natif(dossier=True) is None
    assert appels == ["zenity"]


def test_le_mode_dossier_demande_un_dossier_a_zenity(monkeypatch):
    import subprocess
    commandes = []

    def faux_run(commande, **_k):
        commandes.append(commande)
        return subprocess.CompletedProcess(commande, 0, stdout="/home/moi/projet\n", stderr="")
    monkeypatch.setattr(subprocess, "run", faux_run)

    assert attachments._ouvrir_selecteur_natif(dossier=True) == "/home/moi/projet"
    assert "--directory" in commandes[0]
