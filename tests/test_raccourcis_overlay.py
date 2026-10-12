"""src/ui/raccourcis_overlay.py — raccourcis lecture seule pour l'île.

Ce que ces tests protègent :
  - chaque action appelle le vrai tool (pas de duplication de logique Gmail/
    Jira/Calendar) et transforme sa sortie en `{stats, rows}` exploitable
    directement par les composants Stat/Row de l'île ;
  - une boîte vide ou une erreur côté tool ne fait jamais planter `executer` ;
  - la liste blanche `ACTIONS` ne contient que des actions de lecture — aucun
    tool d'écriture (`gmail_send_email`, `calendar_create_event`, ...) ne doit
    pouvoir y être ajouté sans que ce test échoue.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ui.raccourcis_overlay import ACTIONS, executer


def test_actions_est_une_liste_blanche_lecture_seule():
    noms_ecriture = {
        "gmail_send_email", "gmail_reply", "gmail_edit_draft", "gmail_confirm_send",
        "calendar_create_event", "calendar_update_event", "calendar_delete_event",
        "drive_delete_file", "jira_create_issue", "jira_update_issue",
    }
    assert set(ACTIONS) & noms_ecriture == set()
    assert set(ACTIONS) == {
        "gmail_non_lus", "gmail_resumer_mail",
        "jira_mes_tickets", "jira_detail_ticket",
        "workspace_aujourdhui",
        # Études : lecture du store local. `etudes_ouvrir_fiche` lance
        # `xdg-open` sur un fichier déjà généré, sans rien modifier.
        "etudes_fiches_recentes", "etudes_ouvrir_fiche", "etudes_suivis",
        "etudes_echeances", "etudes_detail_suivi",
    }


def test_executer_action_inconnue_leve():
    with pytest.raises(ValueError):
        executer("gmail_envoyer_un_mail")


def test_gmail_non_lus_vide():
    with patch("src.agents.gmail.tools.gmail_search.func", return_value="📭 Aucun mail trouvé."):
        resultat = executer("gmail_non_lus")
    assert resultat["stats"][0]["value"] == "0"
    assert resultat["rows"] == []


def test_gmail_non_lus_parse_le_tableau_markdown():
    table = (
        "📬 **2 mail(s)**\n\n"
        "| # | ID | De | Objet | Date |\n"
        "|---|----|----|-------|------|\n"
        "| 1 | `abc` | Camille <c@ex.com> | Point hebdo | Mon, 1 Jan |\n"
        "| 2 | `def` | Hugo <h@ex.com> | Build cassé | Tue, 2 Jan |"
    )
    with patch("src.agents.gmail.tools.gmail_search.func", return_value=table):
        resultat = executer("gmail_non_lus")
    assert resultat["stats"][0] == {"label": "Non lus", "value": "2", "accent": True}
    assert resultat["rows"][0]["title"] == "Point hebdo"
    assert "Camille" in resultat["rows"][0]["meta"]
    assert resultat["rows"][0]["id"] == "abc"
    assert resultat["rows"][1]["id"] == "def"


def test_gmail_resumer_mail_sans_id_leve():
    with pytest.raises(ValueError):
        executer("gmail_resumer_mail", None)


def test_gmail_resumer_mail_appelle_le_tool_avec_le_bon_id():
    with patch("src.agents.gmail.tools.gmail_summarize.func", return_value="# Résumé\nContenu.") as mocked:
        resultat = executer("gmail_resumer_mail", "abc123")
    mocked.assert_called_once_with(message_id="abc123")
    assert resultat == {"text": "# Résumé\nContenu."}


def test_jira_mes_tickets_distingue_en_cours_et_termine():
    reponse = {
        "status": "ok", "count": 2,
        "issues": [
            {"key": "AXON-1", "summary": "A", "status": "In Progress", "priority": "High", "updated": "2026-01-01"},
            {"key": "AXON-2", "summary": "B", "status": "Done", "priority": "Low", "updated": "2026-01-02"},
        ],
    }
    with patch("src.agents.jira.tools.jira_get_my_issues.func", return_value=reponse):
        resultat = executer("jira_mes_tickets")
    stats = {s["label"]: s["value"] for s in resultat["stats"]}
    assert stats["Assignés à toi"] == "2"
    assert stats["En cours"] == "1"
    assert resultat["rows"][0]["accent"] is True
    assert resultat["rows"][1]["accent"] is False
    assert resultat["rows"][0]["id"] == "AXON-1"


def test_jira_detail_ticket_sans_cle_leve():
    with pytest.raises(ValueError):
        executer("jira_detail_ticket", None)


def test_jira_detail_ticket_compose_un_texte_lisible():
    issue = {
        "status": "ok",
        "issue": {
            "key": "AXON-1", "status": "In Progress", "priority": "High",
            "assignee": "Camille", "due": "2026-02-01",
            "description_text": "Corriger le flash au démarrage.",
            "url": "https://ex.atlassian.net/browse/AXON-1",
        },
    }
    with patch("src.agents.jira.tools.jira_get_issue.func", return_value=issue):
        resultat = executer("jira_detail_ticket", "AXON-1")
    assert "In Progress" in resultat["text"]
    assert "Camille" in resultat["text"]
    assert "Corriger le flash" in resultat["text"]


def test_jira_detail_ticket_erreur_leve_avec_message():
    with patch("src.agents.jira.tools.jira_get_issue.func",
               return_value={"status": "error", "error": "404 introuvable"}):
        with pytest.raises(RuntimeError, match="404"):
            executer("jira_detail_ticket", "AXON-404")


def test_jira_mes_tickets_erreur_leve_avec_message():
    with patch("src.agents.jira.tools.jira_get_my_issues.func",
               return_value={"status": "error", "error": "401 non autorisé"}):
        with pytest.raises(RuntimeError, match="401"):
            executer("jira_mes_tickets")


def test_workspace_aujourdhui_accentue_le_premier_evenement():
    reponse = {
        "status": "ok", "count": 2,
        "events": [
            {"title": "Point hebdo", "start": "2026-01-01T14:00:00Z", "location": "Salle A", "description": "RAS"},
            {"title": "Revue", "start": "2026-01-01"},
        ],
    }
    with patch("src.agents.google_calendar.tools.calendar_list_events.func", return_value=reponse):
        resultat = executer("workspace_aujourdhui")
    assert resultat["stats"][0]["value"] == "2"
    assert resultat["rows"][0]["meta"] == "14:00"
    assert resultat["rows"][0]["accent"] is True
    assert resultat["rows"][1]["meta"] == "toute la journée"
    assert resultat["rows"][1]["accent"] is False
    assert "Salle A" in resultat["rows"][0]["detail"]
    assert resultat["rows"][1]["detail"] is None
