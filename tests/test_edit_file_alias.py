"""`edit_file` accepte `old_fragment`/`new_fragment` en plus des vrais noms.

Vécu à l'écran : un modèle a appelé `edit_file` avec `old_fragment=`/
`new_fragment=` au lieu de `old_string=`/`new_string=`. L'erreur Pydantic
levée était pourtant CLAIRE et CORRECTE — « old_string : Field required »,
« new_string : Field required » — mais le modèle a expliqué l'échec en
inventant une cause sans rapport (« les valeurs contenaient des caractères de
mise en forme ») et a répété EXACTEMENT le même appel sur « réessaye »,
sans jamais se corriger.

Retenter n'aurait rien réparé : ce n'était pas un hasard, c'était le même nom
à chaque appel. Compter sur le modèle pour lire un message d'erreur et s'auto-
corriger s'est mesuré peu fiable toute cette session (voir `mesure_filet.py`,
0 appel à `obtenir_outil` sur 10 occasions) — le même remède déjà appliqué à
`shell_run` pour `command`/`cmd` (« relevé trois fois sur un seul "supprime
tout ce que contient ce dossier" ») s'applique ici : ACCEPTER le nom probable
plutôt que de compter sur l'auto-correction.
"""
from __future__ import annotations

import pytest

from src.agents.coding.pending import dev_plan, pending_changes
from src.agents.coding.tools import edit_file


@pytest.fixture(autouse=True)
def _pile_propre():
    dev_plan.clear()
    pending_changes.clear()
    yield
    dev_plan.clear()
    pending_changes.clear()


@pytest.fixture
def fichier(tmp_path):
    p = tmp_path / "cours.md"
    p.write_text("Ligne 1\nTODO: A compléter\nLigne 3\n", encoding="utf-8")
    return p


# ── le cas vécu ────────────────────────────────────────────────────────────
def test_les_mauvais_noms_marchent_quand_meme(fichier):
    resultat = edit_file.invoke({
        "path": str(fichier),
        "old_fragment": "TODO: A compléter",
        "new_fragment": "Un paragraphe complété.",
    })

    assert resultat["status"] == "proposed"


def test_le_contenu_propose_est_correct_via_lalias(fichier):
    edit_file.invoke({
        "path": str(fichier),
        "old_fragment": "TODO: A compléter",
        "new_fragment": "Un paragraphe complété.",
    })

    propose = pending_changes.items[0].proposed
    assert "Un paragraphe complété." in propose
    assert "TODO" not in propose


# ── ce qui ne doit pas casser ──────────────────────────────────────────────
def test_les_vrais_noms_marchent_toujours(fichier):
    resultat = edit_file.invoke({
        "path": str(fichier),
        "old_string": "TODO: A compléter",
        "new_string": "Un vrai remplacement.",
    })

    assert resultat["status"] == "proposed"


def test_melanger_un_bon_et_un_mauvais_nom_marche(fichier):
    """`old_string` correct, `new_fragment` non — chaque champ a son propre
    alias, indépendamment de l'autre."""
    resultat = edit_file.invoke({
        "path": str(fichier),
        "old_string": "TODO: A compléter",
        "new_fragment": "Mélange de noms.",
    })

    assert resultat["status"] == "proposed"


def test_le_schema_annonce_garde_les_vrais_noms():
    """L'alias rattrape, il n'enseigne pas : le modèle doit voir `old_string`/
    `new_string` dans le schéma qu'on lui montre, pas l'alias de secours."""
    schema = edit_file.args_schema.model_json_schema()

    assert "old_string" in schema["properties"]
    assert "new_string" in schema["properties"]
    assert "old_fragment" not in schema["properties"]
    assert "new_fragment" not in schema["properties"]


def test_un_nom_totalement_inconnu_reste_refuse(fichier):
    """L'alias couvre un cas mesuré, pas n'importe quel nom : une vraie faute
    de frappe doit continuer à produire une erreur exploitable."""
    with pytest.raises(Exception):
        edit_file.invoke({
            "path": str(fichier),
            "texte_a_remplacer": "TODO",
            "texte_de_remplacement": "fait",
        })
