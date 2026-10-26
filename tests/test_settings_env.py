"""src/infra/settings.py — `.env` l'emporte sur `configs/base.yaml`."""
from __future__ import annotations


def test_l_environnement_l_emporte_sur_la_configuration_partagee(monkeypatch):
    from src.infra import settings as module
    monkeypatch.setattr(module, "_load_yaml_config", lambda: {"mistral": {"model": "mistral-small-2603"}})
    monkeypatch.setenv("MISTRAL_MODEL", "ministral-14b-2512")
    assert module._merge_yaml_into_settings().mistral_model == "ministral-14b-2512"


def test_sans_variable_d_environnement_le_yaml_fait_foi(monkeypatch):
    from src.infra import settings as module
    monkeypatch.setattr(module, "_load_yaml_config", lambda: {"mistral": {"model": "mistral-small-2603"}})
    monkeypatch.delenv("MISTRAL_MODEL", raising=False)
    assert module._merge_yaml_into_settings().mistral_model == "mistral-small-2603"
