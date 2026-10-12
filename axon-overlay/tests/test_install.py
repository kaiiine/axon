import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("installer", ROOT / "installer.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallTests(unittest.TestCase):
    def test_installation_relocation_and_backup(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary:
            project = Path(temporary)
            dest = module.installer(project)
            self.assertEqual(dest, project / ".axon/plugins/axon-overlay")
            self.assertTrue((dest / "ui/dist/axon.js").exists())
            self.assertFalse((dest / "node_modules").exists())
            self.assertEqual(json.loads((dest / "plugin.json").read_text())["id"], "axon-overlay")
            (dest / "local-note.txt").write_text("conserver")
            module.installer(project)
            backups = list(dest.parent.glob("axon-overlay.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "local-note.txt").read_text(), "conserver")

    def test_unknown_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as temporary:
            project = Path(temporary)
            dest = project / ".axon/plugins/axon-overlay"
            dest.mkdir(parents=True)
            (dest / "mine.txt").write_text("intact")
            with self.assertRaises(ValueError):
                module.installer(project)
            self.assertEqual((dest / "mine.txt").read_text(), "intact")


if __name__ == "__main__":
    unittest.main()
