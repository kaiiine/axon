"""Une fiche générée ne doit contenir aucune syntaxe Markdown littérale.

Vécu : « refais-en une fiche de cours » a produit un fichier avec des
astérisques visibles partout — `**wide**`, `**deep**`, `**règle d'or**` —
au lieu de `<strong>`. Le correctif de la veille avait unifié les deux modes
de `save_study_file` sur le même pipeline, mais n'avait pas touché ce
défaut : le skill interdisait le Markdown AUTOUR du HTML (« aucun bloc
markdown, aucune explication »), jamais DEDANS. Le modèle gardait son
réflexe de conversation en écrivant le texte des balises.

Vérifié manuellement contre un vrai modèle avant ce commit :

    PYTHONPATH=. venv/bin/python -c "
    from src.agents.study.tools import _generer_via_skill
    html = _generer_via_skill('fiche', 'Wide & Deep : wide = ...')
    print(html.count('**'))"   # 0 après le correctif, non nul avant

Ce test-ci ne rejoue PAS l'appel modèle — la suite reste hors ligne, comme le
veut le dépôt (`outils/mesure_filet.py` est hors de `tests/` pour la même
raison). Il fige seulement que la consigne existe.
"""
from __future__ import annotations

from pathlib import Path


def test_le_skill_interdit_le_markdown_dans_le_html():
    for nom in ("fiche", "exo"):
        texte = Path(f"skills/{nom}.md").read_text(encoding="utf-8")
        assert "syntaxe Markdown" in texte
        assert "à l'intérieur du HTML" in texte
