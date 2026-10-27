"""La consigne des skills dans le prompt, et l'indice de rédaction des outils gmail.

Mesurés sur le vrai modèle (`outils/mesure_prompt.py`) : la règle seule fait
charger `redaction` avant un mail dans 4 à 6 cas sur 8 au lieu de 0, l'indice de
l'outil porte le reste. Ces tests protègent la CONSTRUCTION, pas le comportement.
"""
from datetime import date

import pytest

from src.agents.gmail.tools import gmail_reply, gmail_send_email
from src.llm.prompts import _SKILLS, build_system_prompt


def _prompt(outils: list[str]) -> str:
    return build_system_prompt(outils, date.today().isoformat(), "Kaine", lang="fr")


def test_la_regle_designe_ce_qu_on_produit_pas_l_outil_sous_la_main():
    assert "PRODUCE, not the tool at hand" in _SKILLS


def test_rediger_est_une_tache_meme_avec_un_outil_d_envoi_lie():
    assert "Wording is a task" in _SKILLS and "send tool is bound" in _SKILLS


def test_load_skill_part_seul_avant_l_outil_d_action():
    assert "ALONE in its turn" in _SKILLS and "THEN call the action tool" in _SKILLS


def test_un_texte_dicte_n_a_pas_besoin_de_skill():
    assert "word for word needs no skill" in _SKILLS


def test_la_section_n_apparait_qu_avec_load_skill():
    assert "MANDATORY FIRST STEP" in _prompt(["load_skill", "gmail_send_email"])
    assert "MANDATORY FIRST STEP" not in _prompt(["gmail_send_email"])


def test_la_section_emails_ne_force_plus_trois_paragraphes():
    p = _prompt(["gmail_send_email"])
    assert "Min. 3-4 paragraphs" not in p and "Length fits the message" in p


def test_la_section_emails_renvoie_au_skill_d_ecriture():
    assert "writing skill first" in _prompt(["gmail_send_email"])


@pytest.mark.parametrize("outil", [gmail_send_email, gmail_reply])
def test_les_outils_de_mail_demandent_le_skill_avant_d_ecrire(outil):
    assert 'load_skill(stack="redaction")' in outil.description
    assert "SEUL dans son tour" in outil.description


def test_l_interdiction_de_mentir_n_est_dite_qu_une_fois_dans_le_noyau():
    assert _prompt([]).count("Never claim something was created") == 1
