import unittest

from app.core.pattern_libro import PATTERN_LIBRO, PATTERN_RISORSE_EXTRA
from app.core.pattern_paragrafo import PATTERN_PARAGRAFO


class TestPromptParagrafi(unittest.TestCase):
    def test_prompt_conservano_prosa_e_riquadri_didattici(self):
        for prompt in (PATTERN_PARAGRAFO, PATTERN_LIBRO):
            self.assertIn("discorsiv", prompt.lower())
            self.assertIn("riquadri", prompt.lower())
            self.assertTrue(
                "non ometterli" in prompt.lower()
                or "non far omettere" in prompt.lower()
                or "non omettere i riquadri" in prompt.lower()
            )

    def test_prompt_risorse_extra_mantiene_riquadri_utili(self):
        self.assertIn("riquadri didattici necessari", PATTERN_RISORSE_EXTRA)

    def test_prompt_mappa_figure_a_lezione_e_slide_selezionabili(self):
        self.assertIn('figura("L1_S003_nome_descrittivo.png")', PATTERN_PARAGRAFO)
        self.assertIn("l'utente può scegliere un'altra lezione", PATTERN_PARAGRAFO)
        self.assertIn("selezioni manualmente lezione e", PATTERN_PARAGRAFO)


if __name__ == "__main__":
    unittest.main()
