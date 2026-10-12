"""src/ui/streaming.py — verrou anti-doublon de génération fiche/exo (§1, lot 3).

Teste seulement `_generation_deja_en_cours`, la fonction pure qui consulte
`store.generation_active` avant de lancer une fiche/un exo. `_handle_fiche`/
`_handle_exo` eux-mêmes ne sont PAS testés automatiquement ici : ils
appellent un vrai LLM via `_run_letter_stream`, ce qui nécessite un graphe
réel — couverts par la validation manuelle du lot (§5), pas par ce fichier.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def streaming(monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_STATE_DIR", str(tmp_path))
    import src.infra.chemins as chemins
    import src.agents.study.store as store
    import src.ui.streaming as module

    for m in (chemins, store, module):
        importlib.reload(m)
    monkeypatch.setattr(module.pont, "etat", lambda *a, **k: None)
    return module, store


def test_aucune_generation_active_ne_bloque_rien(streaming):
    module, _store = streaming
    assert module._generation_deja_en_cours(None, "fiche", "/fiche") is False


def test_une_generation_en_cours_bloque_le_meme_suivi_et_type(streaming):
    module, store = streaming
    store.demarrer_generation("suivi_a", "fiche")

    assert module._generation_deja_en_cours("suivi_a", "fiche", "/fiche") is True


def test_un_type_different_sur_le_meme_suivi_nest_pas_bloque(streaming):
    """Une fiche en cours sur un suivi ne doit jamais bloquer des exercices
    sur ce même suivi — le verrou est spécifique à (suivi_id, type)."""
    module, store = streaming
    store.demarrer_generation("suivi_a", "fiche")

    assert module._generation_deja_en_cours("suivi_a", "exo", "/exo") is False


def test_un_autre_suivi_nest_pas_bloque(streaming):
    module, store = streaming
    store.demarrer_generation("suivi_a", "fiche")

    assert module._generation_deja_en_cours("suivi_b", "fiche", "/fiche") is False


def test_une_generation_terminee_ne_bloque_plus_un_nouveau_lancement(streaming):
    """Il doit rester possible de lancer volontairement une nouvelle
    génération après la précédente (§1) — le verrou ne porte que sur ce qui
    est RÉELLEMENT en cours, jamais sur l'historique."""
    module, store = streaming
    generation = store.demarrer_generation(None, "fiche")
    store.terminer_generation(generation["id"], "gen_x")

    assert module._generation_deja_en_cours(None, "fiche", "/fiche") is False


def test_une_generation_echouee_ne_bloque_plus_un_nouveau_lancement(streaming):
    module, store = streaming
    generation = store.demarrer_generation(None, "exo")
    store.echouer_generation(generation["id"], "panne LLM")

    assert module._generation_deja_en_cours(None, "exo", "/exo") is False
