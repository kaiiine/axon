"""src/skills/catalogue.py — le catalogue montré au modèle, et les annexes."""
from __future__ import annotations

import pytest

from src.skills import catalogue
from src.skills.retriever import SkillRetriever


def _skill(dossier, nom, description, scope="orchestrator", annexe=False, corps="CORPS"):
    en_tete = f"---\nname: {nom}\ndescription: {description}\nscope: {scope}\n"
    en_tete += "annexe: true\n" if annexe else ""
    (dossier / f"{nom}.md").write_text(en_tete + f"---\n{corps}", encoding="utf-8")


@pytest.fixture
def retriever(tmp_path, monkeypatch):
    _skill(tmp_path, "redaction", "Rédiger un texte qui sonne humain")
    _skill(tmp_path, "humanizer-complet", "Annexe de redaction", annexe=True, corps="ANNEXE")
    _skill(tmp_path, "pentest", "Reconnaissance réseau en labo")
    _skill(tmp_path, "nextjs", "Applications Next.js", scope="coding")
    reel = SkillRetriever(tmp_path)
    # Le module des skills garde un retriever unique : on le remplace le temps du test.
    monkeypatch.setattr("src.skills.retriever._retriever", reel)
    monkeypatch.setattr(catalogue, "skills_routables", lambda scope=None: reel.routables(scope))
    monkeypatch.setattr(catalogue, "skills_pertinentes",
                        lambda requete, scope=None, budget=5: reel.list_names(scope)[:budget])
    return reel


def test_une_annexe_reste_chargeable_mais_n_est_pas_au_catalogue(retriever):
    assert "humanizer-complet" in retriever.list_names("orchestrator")
    assert retriever.get("humanizer-complet", scope="orchestrator") == "ANNEXE"
    assert "humanizer-complet" not in [n for n, _ in catalogue.entrees("orchestrator")]


def test_le_catalogue_respecte_la_portee(retriever):
    assert {n for n, _ in catalogue.entrees("orchestrator")} == {"redaction", "pentest"}
    assert {n for n, _ in catalogue.entrees("coding")} == {"nextjs"}


def test_une_ligne_par_skill_sans_saut_de_ligne(retriever, tmp_path):
    _skill(tmp_path, "long", "premier mot " + "très long " * 60)
    retriever._ready = False
    retriever._skills.clear()
    retriever._load()
    for ligne in catalogue.texte("orchestrator").splitlines():
        assert ligne.startswith("  - ") and len(ligne) < 200
    assert catalogue.texte("orchestrator").count("\n") == len(catalogue.entrees("orchestrator")) - 1


def test_une_description_trop_longue_est_tronquee_avec_une_ellipse():
    court = catalogue._ligne("a" * 500)
    assert len(court) == catalogue._MAX_DESCRIPTION and court.endswith("…")
    assert catalogue._ligne("deux\nlignes   espacées") == "deux lignes espacées"


def test_sans_skill_routable_le_catalogue_le_dit(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogue, "skills_routables", lambda scope=None: [])
    assert catalogue.texte("orchestrator") == "  (aucun)"


def test_la_requete_restreint_un_catalogue_trop_large(retriever, monkeypatch):
    large = [(f"skill{i}", "d") for i in range(catalogue.MAX_ENTREES + 8)]
    monkeypatch.setattr(catalogue, "skills_routables", lambda scope=None: large)
    monkeypatch.setattr(catalogue, "skills_pertinentes",
                        lambda requete, scope=None, budget=5: ["skill3", "skill1"])
    assert [n for n, _ in catalogue.entrees("coding", "un site")] == ["skill1", "skill3"]
    assert len(catalogue.entrees("coding")) == len(large)          # sans requête : tout


def test_un_catalogue_court_n_est_jamais_restreint(retriever, monkeypatch):
    monkeypatch.setattr(catalogue, "skills_pertinentes", lambda *a, **k: ["redaction"])
    assert {n for n, _ in catalogue.entrees("orchestrator", "scan de ports")} == {"redaction", "pentest"}


def test_une_restriction_vide_rend_tout_plutot_que_cacher_le_bon_skill(retriever, monkeypatch):
    large = [(f"skill{i}", "d") for i in range(catalogue.MAX_ENTREES + 3)]
    monkeypatch.setattr(catalogue, "skills_routables", lambda scope=None: large)
    monkeypatch.setattr(catalogue, "skills_pertinentes", lambda *a, **k: [])
    assert catalogue.entrees("coding", "n'importe quoi") == large


def test_un_fichier_sans_frontmatter_est_une_annexe_chargeable_mais_hors_catalogue(tmp_path):
    """`style-perso.md` : lu par `redaction`, jamais choisi seul. Sans description
    ni portée, il n'a rien à montrer au catalogue."""
    (tmp_path / "style-perso.md").write_text("MON STYLE", encoding="utf-8")
    _skill(tmp_path, "redaction", "Rédiger un texte")
    reel = SkillRetriever(tmp_path)
    assert "style-perso" in reel.list_names("coding")                 # portée par défaut
    assert reel.get("style-perso", scope="coding") == "MON STYLE"     # chargeable
    assert [n for n, _ in reel.routables("coding")] == []
    assert [n for n, _ in reel.routables("orchestrator")] == ["redaction"]


def test_annexe_false_ou_absente_reste_routable(tmp_path):
    (tmp_path / "a.md").write_text("---\nname: a\ndescription: d\nannexe: false\n---\nC", encoding="utf-8")
    (tmp_path / "b.md").write_text("---\nname: b\ndescription: d\n---\nC", encoding="utf-8")
    assert {n for n, _ in SkillRetriever(tmp_path).routables("coding")} == {"a", "b"}
