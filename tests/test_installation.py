"""src/installation — la configuration commune à setup.sh et setup.ps1."""
from __future__ import annotations

import json

import pytest

from src.installation import configuration, services
from src.installation.fichier_env import FichierEnv, est_renseignee


@pytest.fixture
def env(tmp_path):
    chemin = tmp_path / ".env"
    chemin.write_text("# ── REQUIS ──\nTAVILY_API_KEY=tvly-...\n\nGROQ_API_KEY=gsk_vraie\n", encoding="utf-8")
    return FichierEnv(chemin)


def _saisies(monkeypatch, *reponses):
    restantes = list(reponses)
    monkeypatch.setattr("builtins.input", lambda _invite="": restantes.pop(0) if restantes else "")


def test_ecrire_remplace_la_cle_a_sa_place_et_garde_les_commentaires(env):
    env.ecrire("TAVILY_API_KEY", "tvly-abc")
    env.ecrire("JIRA_URL", "https://x.atlassian.net")
    assert env.chemin.read_text(encoding="utf-8").splitlines() == [
        "# ── REQUIS ──", "TAVILY_API_KEY=tvly-abc", "", "GROQ_API_KEY=gsk_vraie",
        "JIRA_URL=https://x.atlassian.net"]


@pytest.mark.parametrize("valeur, attendu", [
    ("gsk_vraie", True), ("", False), ("tvly-...", False), ("your_key", False),
    ("Ton Prénom Nom", False)])
def test_une_valeur_d_exemple_ne_compte_pas_comme_renseignee(valeur, attendu):
    assert est_renseignee(valeur) is attendu


def test_une_saisie_vide_conserve_la_cle(env, monkeypatch):
    _saisies(monkeypatch, "")
    services.demander_cle(env, services.Champ("GROQ_API_KEY", "Clé", "Format"))
    assert env.lire("GROQ_API_KEY") == "gsk_vraie"


def test_un_service_simple_n_est_configure_que_si_toutes_ses_cles_le_sont(env, tmp_path):
    ctx = services.Contexte(racine=tmp_path, env=env)
    jira = next(s for s in services.SERVICES if s.titre.startswith("Jira"))
    env.ecrire("JIRA_URL", "https://x.atlassian.net")
    assert not jira.est_configure(ctx)
    env.ecrire("JIRA_EMAIL", "moi@x.fr")
    env.ecrire("JIRA_API_KEY", "ATATT3x1")
    assert jira.est_configure(ctx)


def test_declarer_blender_ne_touche_pas_aux_autres_serveurs(tmp_path):
    chemin = tmp_path / "mcp_servers.json"
    chemin.write_text(json.dumps({"servers": {"github": {"command": "gh"}}}), encoding="utf-8")
    assert services.declarer_blender(chemin) is True
    assert services.declarer_blender(chemin) is False
    serveurs = json.loads(chemin.read_text(encoding="utf-8"))["servers"]
    assert set(serveurs) == {"github", "blender"}


def test_le_menu_quitte_sur_q_et_sur_fin_de_saisie(env, tmp_path, monkeypatch):
    ctx = services.Contexte(racine=tmp_path, env=env)
    _saisies(monkeypatch, "q")
    configuration.menu(ctx)
    _saisies(monkeypatch)
    configuration.menu(ctx)


def test_un_nouveau_env_part_du_modele(tmp_path, monkeypatch):
    (tmp_path / ".env.sample").write_text("USER_NAME=Ton Prénom Nom\n", encoding="utf-8")
    monkeypatch.setattr(configuration, "RACINE", tmp_path)
    ctx = configuration.contexte()
    assert ctx.env.lire("USER_NAME") == "Ton Prénom Nom"
    assert not ctx.env.renseignee("USER_NAME")


def test_une_variable_exportee_survit_a_une_apostrophe(tmp_path, monkeypatch):
    import subprocess

    from src.installation import systeme
    monkeypatch.setattr(systeme, "WINDOWS", False)
    monkeypatch.setattr(systeme, "MACOS", False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SHELL", "/bin/bash")
    temoin = tmp_path / "execute"
    piege = f"cl'é; touch {temoin}"
    profil = systeme.exporter_variable("AXON_TEST", piege, "test")
    assert profil == str(tmp_path / ".bashrc")
    assert systeme.variable_exportee("AXON_TEST")
    sortie = subprocess.run(["bash", "-c", f"source {profil}; printf %s \"$AXON_TEST\""],
                            capture_output=True, text=True, check=True).stdout
    assert sortie == piege
    assert not temoin.exists()


def test_le_dossier_de_telechargements_suit_la_langue_du_systeme(tmp_path, monkeypatch):
    from src.installation import systeme
    monkeypatch.setenv("HOME", str(tmp_path))
    assert systeme.dossier_telechargements() == tmp_path / "Downloads"
    (tmp_path / "Téléchargements").mkdir()
    assert systeme.dossier_telechargements() == tmp_path / "Téléchargements"
