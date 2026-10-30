import tempfile
import unittest
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Paragraph, SimpleDocTemplate

from motore.fonts import fix_simboli, registra_font
from motore.stili import STILI


class TestMathSymbolRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        registra_font()

    def test_math_and_logic_blocks_use_unicode_fallback(self):
        fixed = fix_simboli(
            "∀ ∃ ¬ ∧ ∨ ⇒ ⇔ ⊆ ∈ ∉ ∅ ℕ ℤ ℚ ℝ ℂ ∑ ∫ ⋈ 𝔄 𝒜 𝟘"
        )

        for symbol in (
            "∀", "⇒", "⊆", "∑", "⋈", "𝔄", "𝒜", "𝟘",
        ):
            self.assertIn(
                f'<font name="LibroSimboli">{symbol}</font>',
                fixed,
            )
        self.assertEqual(fix_simboli(fixed), fixed)

    def test_preserves_reportlab_markup_and_escapes_comparisons(self):
        fixed = fix_simboli("<b>x < y & y > 0</b> ∀x")

        self.assertIn("<b>", fixed)
        self.assertIn("</b>", fixed)
        self.assertIn("x &lt; y &amp; y > 0", fixed)
        self.assertIn('<font name="LibroSimboli">∀</font>', fixed)

    def test_pdf_embeds_math_font_and_extracts_symbols(self):
        testo = "∀x ∈ ℝ: x ≠ ∅ ⇒ ℤ ⊆ ℂ"
        with tempfile.TemporaryDirectory() as directory:
            percorso = Path(directory) / "simboli.pdf"
            documento = SimpleDocTemplate(str(percorso), pagesize=A4)
            documento.build([
                Paragraph(fix_simboli(testo), STILI["Testo"]),
            ])

            with fitz.open(percorso) as pdf:
                pagina = pdf[0]
                fonts = pagina.get_fonts(full=True)
                testo_estratto = pagina.get_text()

        self.assertTrue(
            any("NotoSansMath" in str(font) for font in fonts),
            fonts,
        )
        for symbol in ("∀", "∈", "ℝ", "≠", "∅", "⇒", "ℤ", "⊆", "ℂ"):
            self.assertIn(symbol, testo_estratto)

    def test_mathematical_alphanumeric_glyphs_are_available(self):
        registra_font()
        font = pdfmetrics.getFont("LibroSimboli")
        for codepoint in (0x1D504, 0x1D49C, 0x1D7D8):
            self.assertIn(codepoint, font.face.charWidths)


if __name__ == "__main__":
    unittest.main()
