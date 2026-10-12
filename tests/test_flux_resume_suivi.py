"""Résumé IA d'un suivi en flux : src/ui/flux_overlay.py (protocole générique
vers l'île) et src/agents/study/resume.py (contexte + appel LLM avec rotation
de clés). Aucun vrai LLM : les clients sont remplacés par des faux."""
from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest

import src.ui.flux_overlay as flux_overlay


# ── protocole générique ────────────────────────────────────────────────

def _diffuser(monkeypatch, source, intervalle=0.0):
    envois = []
    monkeypatch.setitem(flux_overlay.FLUX, "test", source)
    monkeypatch.setattr(flux_overlay, "INTERVALLE_ENVOI", intervalle)
    flux_overlay.diffuser("f1", "test", "cible", lambda **m: envois.append(m))
    return envois


def test_un_flux_envoie_ses_morceaux_puis_la_fin(monkeypatch):
    envois = _diffuser(monkeypatch, lambda cible: iter(["Bon", "jour"]))

    assert envois == [
        {"type": "flux_morceau", "id": "f1", "texte": "Bon"},
        {"type": "flux_morceau", "id": "f1", "texte": "jour"},
        {"type": "flux_fin", "id": "f1"},
    ]


def test_les_morceaux_rapides_sont_regroupes(monkeypatch):
    envois = _diffuser(monkeypatch, lambda cible: iter(["a", "b", "c"]), intervalle=60)

    assert [e for e in envois if e["type"] == "flux_morceau"] == [{"type": "flux_morceau", "id": "f1", "texte": "abc"}]


def test_une_erreur_en_cours_de_flux_garde_le_texte_deja_recu(monkeypatch):
    def source(_cible):
        yield "début"
        raise RuntimeError("quota")
    envois = _diffuser(monkeypatch, source, intervalle=60)

    assert envois == [
        {"type": "flux_morceau", "id": "f1", "texte": "début"},
        {"type": "flux_erreur", "id": "f1", "message": "quota"},
    ]


def test_un_flux_inconnu_repond_une_erreur(monkeypatch):
    envois = []
    flux_overlay.diffuser("f2", "nimporte", "x", lambda **m: envois.append(m))

    assert envois == [{"type": "flux_erreur", "id": "f2", "message": "flux inconnu : nimporte"}]


# ── résumé d'un suivi ──────────────────────────────────────────────────

@pytest.fixture
def etudes(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.agents.study.tools_suivi as tools_suivi
    import src.agents.study.resume as resume
    for module in (chemins, store, tools_suivi, resume):
        importlib.reload(module)
    return store, resume


class FauxLLM:
    def __init__(self, morceaux=(), erreur=None, erreur_apres=None):
        self.morceaux, self.erreur, self.erreur_apres = morceaux, erreur, erreur_apres

    def stream(self, _messages):
        if self.erreur:
            raise self.erreur
        for i, m in enumerate(self.morceaux):
            if self.erreur_apres is not None and i == self.erreur_apres:
                raise RuntimeError("coupure")
            yield SimpleNamespace(content=m)


def _clients(monkeypatch, *llms):
    import src.llm.rotation as rotation
    monkeypatch.setattr(rotation, "clients", lambda *_a, **_k: iter([("p", f"k{i}", l) for i, l in enumerate(llms)]))
    monkeypatch.setattr(rotation, "marquer_echec", lambda *_a: None)
    monkeypatch.setattr(rotation, "vaut_la_peine_de_reessayer", lambda _e: True)


def test_le_resume_arrive_en_flux_et_est_garde_dans_le_suivi(etudes, monkeypatch):
    store, resume = etudes
    suivi = store.creer_suivi("Conseil des Sages", "projet")
    _clients(monkeypatch, FauxLLM(["**En bref** ", "une API."]))

    assert list(resume.flux_resume_suivi(suivi["id"])) == ["**En bref** ", "une API."]
    assert store.obtenir_suivi(suivi["id"])["resume"]["texte"] == "**En bref** une API."


def test_une_cle_epuisee_avant_le_premier_morceau_passe_a_la_suivante(etudes, monkeypatch):
    store, resume = etudes
    suivi = store.creer_suivi("P", "projet")
    _clients(monkeypatch, FauxLLM(erreur=RuntimeError("429")), FauxLLM(["ok"]))

    assert list(resume.flux_resume_suivi(suivi["id"])) == ["ok"]


def test_une_coupure_apres_un_morceau_ne_change_pas_de_fournisseur(etudes, monkeypatch):
    """Reprendre sur une autre clé réécrirait le texte déjà affiché."""
    store, resume = etudes
    suivi = store.creer_suivi("P", "projet")
    _clients(monkeypatch, FauxLLM(["début", "suite"], erreur_apres=1), FauxLLM(["autre"]))

    flux = resume.flux_resume_suivi(suivi["id"])
    assert next(flux) == "début"
    with pytest.raises(RuntimeError, match="coupure"):
        next(flux)
    assert store.obtenir_suivi(suivi["id"]).get("resume") is None


def test_le_contexte_inclut_readme_et_spec_d_un_depot(etudes, tmp_path):
    store, resume = etudes
    depot = tmp_path / "fe"; (depot / ".git").mkdir(parents=True)
    (depot / "README.MD").write_text("Front React du Conseil")
    (depot / "SPEC.md").write_text("Le front doit afficher les posts")
    suivi = store.creer_suivi("P", "projet")
    ressource = store.ajouter_ressource("depot_git", "fe", "chemin_externe", str(depot))
    store.associer_ressource(suivi["id"], ressource["id"])

    contexte = resume.contexte_suivi(suivi["id"])

    assert "Front React du Conseil" in contexte and "Le front doit afficher les posts" in contexte
