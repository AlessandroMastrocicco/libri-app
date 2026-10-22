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


if __name__ == "__main__":
    unittest.main()
