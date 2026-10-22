import json
import tempfile
import unittest
from pathlib import Path

from app.core.slide_extract import (
    elenca_estratti,
    leggi_mappatura_immagine,
    riferimento_slide_da_nome,
    salva_mappatura_immagine,
)
from app.core.paragrafo import estrai_immagini_referenziate, valida_contenuto


class TestMappaturaSlide(unittest.TestCase):
    def _aggiungi_estrazione(self, root: Path, nome: str):
        cartella = root / "libri" / "Libro" / "slide_estratte" / nome
        cartella.mkdir(parents=True)
        (cartella / "pagina_003.png").write_bytes(b"slide")
        return cartella

    def test_assegna_id_alle_estrazioni_preesistenti_e_persistenti(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._aggiungi_estrazione(root, "L1")
            self._aggiungi_estrazione(root, "L2")

            estratti = elenca_estratti(root, "Libro")

            self.assertEqual(
                [(e["dispensa"], e["id_lezione"]) for e in estratti],
                [("L1", "L1"), ("L2", "L2")],
            )
            mappa = json.loads(
                (root / "libri" / "Libro" / "slide_estratte"
                 / "_mappatura_lezioni.json").read_text(encoding="utf-8")
            )
            self.assertEqual(mappa["lezioni"], {"L1": "L1", "L2": "L2"})

    def test_migra_estrazioni_con_nomi_libero_e_non_rinomina_id_esistenti(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._aggiungi_estrazione(root, "Dispensa iniziale")
            self._aggiungi_estrazione(root, "Dispensa avanzata")
            prima = {
                e["dispensa"]: e["id_lezione"]
                for e in elenca_estratti(root, "Libro")
            }
            self.assertEqual(prima, {
                "Dispensa avanzata": "L1",
                "Dispensa iniziale": "L2",
            })

            self._aggiungi_estrazione(root, "A nuova dispensa")
            dopo = {
                e["dispensa"]: e["id_lezione"]
                for e in elenca_estratti(root, "Libro")
            }
            self.assertEqual(dopo["Dispensa iniziale"], "L2")
            self.assertEqual(dopo["Dispensa avanzata"], "L1")
            self.assertEqual(dopo["A nuova dispensa"], "L3")

    def test_riconosce_riferimento_e_persistenza_della_sorgente_reale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            riferimento = riferimento_slide_da_nome(
                "L2_S003_architettura.png"
            )
            self.assertEqual(riferimento, {
                "id_lezione": "L2",
                "slide": 3,
            })
            self.assertIsNone(riferimento_slide_da_nome("figura_generica.png"))

            salvata = salva_mappatura_immagine(
                root, "Libro", 1, "L2_S003_architettura.png",
                "L1", "Dispensa corretta", 8,
            )
            self.assertTrue(salvata["ok"])
            self.assertEqual(
                leggi_mappatura_immagine(
                    root, "Libro", 1, "L2_S003_architettura.png"
                ),
                {
                    "id_lezione": "L1",
                    "slide": 8,
                    "dispensa": "Dispensa corretta",
                },
            )

    def test_validatore_riconosce_figure_con_helper_del_prompt(self):
        contenuto = '''from pathlib import Path
from reportlab.lib.units import cm
from reportlab.platypus import Image
from motore.stili import STILI
from motore.componenti import P

def figura(nome_file):
    percorso = Path(__file__).resolve().parents[1] / "immagini" / nome_file
    return Image(str(percorso), width=15*cm, height=10*cm,
                 kind="proportional")

def story():
    return [figura("L1_S003_schema.png")]
'''
        risultato = valida_contenuto(contenuto)
        self.assertTrue(risultato["ok"], risultato)
        self.assertEqual(
            estrai_immagini_referenziate(contenuto),
            [{"nome": "L1_S003_schema.png", "riga": 13}],
        )


if __name__ == "__main__":
    unittest.main()
