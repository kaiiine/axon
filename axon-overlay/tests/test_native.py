"""Contrat de fenêtre testé sans GTK : exécute la vraie classe avec des doublures."""
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

source = Path(__file__).resolve().parents[1] / "overlay.py"
tree = ast.parse(source.read_text())
overlay = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Overlay")


class Application:
    def __init__(self, **kwargs):
        pass


scope = {"Gtk": SimpleNamespace(Application=Application), "GLib": SimpleNamespace(idle_add=Mock(), Error=RuntimeError), "json": json, "TAILLE_ACCUEIL": (680, 184), "TAILLE_DETAIL": (680, 420)}
exec(compile(ast.Module(body=[overlay], type_ignores=[]), str(source), "exec"), scope)


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.app = scope["Overlay"]()
        self.app.vue = Mock()
        self.app.fenetre = Mock()
        self.app.fenetre.get_visible.return_value = False
        self.app.pont = Mock()

    def test_no_present_before_front_ready(self):
        self.app.basculer()
        self.app.fenetre.present.assert_not_called()
        self.app.vue.evaluate_javascript.assert_not_called()

    def test_queued_request_replayed_before_present(self):
        self.app.depuis_axon({"type": "demande", "id": 0})
        self.assertTrue(self.app.ouvert)
        self.app.fenetre.present.assert_not_called()
        self.app.page_prete = True
        self.app.synchroniser()
        script = self.app.vue.evaluate_javascript.call_args.args[0]
        self.assertIn('"id": 0', script)
        self.assertIn('window.axon.ouvrir(true)', script)
        self.app.vue.evaluate_javascript_finish.return_value.to_boolean.return_value = True
        self.app.page_synchronisee(self.app.vue, None, self.app.generation)
        self.app.fenetre.present.assert_called_once()

    def test_close_wins_over_late_callback(self):
        self.app.page_prete = True
        self.app.basculer()
        generation = self.app.generation
        self.app.basculer()
        self.app.page_synchronisee(self.app.vue, None, generation)
        self.app.fenetre.present.assert_not_called()

    def test_resize_only_on_mode_change(self):
        self.app.definir_mode("detail")
        self.app.definir_mode("detail")
        self.app.vue.set_size_request.assert_called_once_with(680, 420)
        self.app.definir_mode("accueil")
        self.app.vue.set_size_request.assert_called_with(680, 184)

    def test_single_load_and_real_clip(self):
        text = source.read_text()
        self.assertEqual(text.count("self.vue.load_uri("), 1)
        self.assertIn("snapshot.push_rounded_clip(clip)", text)
        self.assertNotIn("self.vue.reload(", text)


if __name__ == "__main__":
    unittest.main()
