"""Une fiche demandée en conversation n'était pas de la même qualité qu'une
fiche demandée depuis un PDF — et ce n'était pas une impression.

`save_study_file` avait DEUX modes qui divergeaient :

    pdf_path=...   extrait le PDF, rend via `templates.charger("fiche", ...)`
                   → le skill complet, 315 lignes : analyse de contenu
                   obligatoire, pièges d'examen, checklist anti-oubli, PUIS
                   le design.
    html=...       le modèle écrit le HTML lui-même, guidé par ~26 lignes de
                   règles de DESIGN SEULEMENT recopiées dans le prompt
                   système (`_STUDY`) — aucune discipline de contenu.

Le prompt système poussait explicitmenet vers `html=` comme mode par défaut,
y compris pour une demande venue d'une conversation sans PDF. Vécu : « Refais,
la fiche n'est pas belle et pas assez précise ».

Le correctif : un seul chemin. `content=` (le résumé structuré du modèle,
PAS du HTML) passe par le MÊME `_generer_via_skill` que `pdf_path=`.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _pas_de_navigateur():
    """Le navigateur ne doit jamais s'ouvrir pendant les tests."""
    with patch("src.agents.study.tools._open_browser"):
        yield


@pytest.fixture
def dossier_isole(tmp_path, monkeypatch):
    from src.agents.study import tools

    monkeypatch.setattr(tools, "_output_dir", lambda: tmp_path)
    return tmp_path


# ── le cœur du correctif ───────────────────────────────────────────────────
def test_content_passe_par_le_meme_generateur_que_pdf_path(dossier_isole):
    """Le test qui aurait dû exister avant le bug : les deux modes appellent
    la même fonction, donc ne peuvent plus diverger en qualité."""
    from src.agents.study.tools import save_study_file

    with patch("src.agents.study.tools._generer_via_skill",
              return_value="<html>" + "x" * 200 + "</html>") as generer:
        save_study_file.invoke({"content": "Définition : X. Modèle : Y.",
                                "filename": "essai"})

    generer.assert_called_once()
    assert generer.call_args[0][1] == "Définition : X. Modèle : Y."


def test_content_appelle_reellement_le_skill_fiche(dossier_isole):
    """Un cran plus bas : `_generer_via_skill` charge bien `templates.charger`,
    pas un prompt improvisé."""
    from src.agents.study.tools import _generer_via_skill

    with patch("src.ui.templates.charger", return_value="prompt") as charger, \
         patch("src.llm.rotation.clients", return_value=[]):
        with pytest.raises(RuntimeError):
            _generer_via_skill("fiche", "du contenu")

    charger.assert_called_once()
    assert charger.call_args[0][0] == "fiche"


def test_pdf_path_utilise_toujours_le_meme_pipeline(dossier_isole, tmp_path):
    """Non-régression : le mode historique continue de fonctionner à
    l'identique — `_generer_via_skill` est maintenant PARTAGÉ, pas remplacé."""
    from src.agents.study.tools import save_study_file

    faux_pdf = tmp_path / "cours.pdf"
    faux_pdf.write_bytes(b"%PDF-1.4 factice")

    with patch("src.ui.attachments._extract_pdf", return_value="texte du cours"), \
         patch("src.agents.study.tools._generer_via_skill",
              return_value="<html>" + "y" * 200 + "</html>") as generer:
        save_study_file.invoke({"pdf_path": str(faux_pdf)})

    generer.assert_called_once_with("fiche", "texte du cours")


# ── l'échappatoire reste fonctionnelle, mais n'est plus le défaut ─────────
def test_html_direct_fonctionne_toujours():
    """L'échappatoire existe pour une raison délibérée — elle ne doit pas
    casser, seulement ne plus être le premier réflexe du modèle."""
    from src.agents.study.tools import save_study_file

    with patch("src.agents.study.tools._output_dir") as out_dir, \
         patch("src.agents.study.tools._open_browser"):
        import tempfile
        d = tempfile.mkdtemp()
        out_dir.return_value.__truediv__ = lambda self, x: __import__("pathlib").Path(d) / x

        resultat = save_study_file.invoke(
            {"html": "<html>" + "z" * 200 + "</html>", "filename": "brut"})

    assert resultat["status"] == "ok"


def test_html_explicite_gagne_sur_content_si_les_deux_sont_donnes(dossier_isole):
    """L'échappatoire est un choix EXPLICITE : si le modèle fournit `html=`
    quand même, c'est qu'il a décidé de bypasser le template en connaissance
    de cause — `content` ne doit pas l'écraser en silence."""
    from src.agents.study.tools import save_study_file

    with patch("src.agents.study.tools._generer_via_skill") as generer:
        resultat = save_study_file.invoke({
            "content": "du contenu structuré",
            "html": "<html>" + "y" * 200 + "</html>",
        })

    generer.assert_not_called()
    assert resultat["status"] == "ok"


# ── ce qui ne doit pas casser ──────────────────────────────────────────────
def test_ni_content_ni_html_ni_pdf_est_une_erreur_propre():
    from src.agents.study.tools import save_study_file

    resultat = save_study_file.invoke({})

    assert resultat["status"] == "error"


def test_un_pdf_introuvable_ne_leve_pas():
    from src.agents.study.tools import save_study_file

    resultat = save_study_file.invoke({"pdf_path": "/inexistant/cours.pdf"})

    assert resultat["status"] == "error"
    assert "introuvable" in resultat["error"].lower()


def test_un_html_trop_court_est_refuse(dossier_isole):
    from src.agents.study.tools import save_study_file

    resultat = save_study_file.invoke({"html": "<p>trop court</p>"})

    assert resultat["status"] == "error"


# ── le prompt système ne pousse plus vers html= ───────────────────────────
def test_le_prompt_systeme_instruit_content_pas_html():
    from src.llm.prompts import _STUDY

    assert "content=" in _STUDY
    assert '"...", file_type' in _STUDY  # save_study_file(content="...", …)
