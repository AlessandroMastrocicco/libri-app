import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.ui.tutorial import TutorialWizard, coordinate_centro_schermo


class TestPreparazioneTour(unittest.TestCase):
    def test_crea_libro_demo_e_capitolo_fuori_dai_dati_utente(self):
        with tempfile.TemporaryDirectory() as directory:
            root_demo = Path(directory) / "tour"
            wizard = SimpleNamespace(
                _root_demo=root_demo,
                _slug_demo="LibroTourGuidato",
            )
            TutorialWizard._prepara_dati_demo(wizard)
            libro = root_demo / "libri" / "LibroTourGuidato"
            self.assertTrue((libro / "capitoli" / "capitolo_01").is_dir())
            self.assertTrue((libro / "immagini").is_dir())

    def test_centro_schermo_indipendente_dalla_posizione_del_parent(self):
        self.assertEqual(
            coordinate_centro_schermo(570, 310, 1920, 1080),
            (675, 385),
        )


if __name__ == "__main__":
    unittest.main()
