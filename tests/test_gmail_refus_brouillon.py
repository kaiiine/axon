"""`gmail_send_email` refuse un brouillon inventé : adresse devinée ou vide, corps à trous."""
import pytest

from src.agents.gmail import tools
from src.agents.gmail.tools import _refus_brouillon, gmail_send_email


def _envoyer(**kw):
    return gmail_send_email.invoke({"to": "a@b.fr", "subject": "Objet", "body": "Bonjour", **kw})


@pytest.mark.parametrize("to", ["", "   ", "manager", "a@b", "a@b.fr c@d.fr"])
def test_un_destinataire_absent_ou_invalide_est_refuse(to):
    assert "ask_clarification" in _refus_brouillon(to, "Objet", "Bonjour")


def test_plusieurs_adresses_valides_passent():
    assert _refus_brouillon("a@b.fr, c@d.fr", "Objet", "Bonjour") is None


@pytest.mark.parametrize("subject,body", [("", "Bonjour"), ("Objet", " ")])
def test_objet_ou_corps_vide_est_refuse(subject, body):
    assert "vide" in _refus_brouillon("a@b.fr", subject, body)


def test_un_champ_a_remplir_dans_le_corps_est_refuse():
    assert "champs à remplir" in _refus_brouillon("a@b.fr", "Objet", "Bonjour [Prénom du manager],")


def test_un_lien_markdown_n_est_pas_un_trou():
    assert _refus_brouillon("a@b.fr", "Objet", "Voir [le doc](https://x.fr) ci-joint") is None


def test_un_refus_ne_touche_pas_au_brouillon_en_cours():
    _envoyer()
    assert "refusé" in _envoyer(to="")
    assert tools._draft["to"] == "a@b.fr"


def test_un_brouillon_valide_est_prepare():
    assert "refusé" not in _envoyer()
    assert tools._draft["has_draft"] is True
