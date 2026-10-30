# -*- coding: utf-8 -*-
"""
test_scaletta.py - Test per l'estrazione della scaletta capitolo (scaletta.py).

Copre i tre livelli della strategia a costo crescente:
  1. schede da testo PDF (euristica locale, zero token);
  2. partizione + titoli via pianificatore (scaletta_locale);
  3. raffinamento AI dei titoli con provider stub (scelta strategica,
     gestione errori: risposta malformata o quota esaurita => fallback).

Nessun accesso di rete: il provider e' sempre uno stub iniettabile.
"""

import json
import tempfile
import unittest
from pathlib import Path

from app.core.ai.router import Router
from app.core.ai.scaletta import (estrai_scaletta,
                                  leggi_scaletta, raffinamento_con_ai,
                                  salva_scaletta, scaletta_locale,
                                  schede_da_testo)

PAGINE = [
    "Introduzione ai sistemi operativi\n• Cos'e' un SO\n• Kernel e shell",
    "Struttura del kernel\n• Monolitico\n• Microkernel",
    "Gestione dei processi\n• Stati del processo\n• Scheduler",
    "Scheduler a round robin\n• Quantum\n• Context switch",
    "Gestione della memoria\n• Paginazione\n• Segmentazione",
    "Memoria virtuale\n• Page fault\n• TLB",
    "Sincronizzazione\n• Mutex\n• Semaphore",
    "Deadlock\n• Condizioni di Coffman",
]


class StubProvider:
    """Provider finto: conta le chiamate e ritorna risposte prefissate."""

    def __init__(self, risposta: str, esito: str = "ok", token: int = 120):
        self.risposta, self.esito, self.token = risposta, esito, token
        self.chiamate = 0

    def __call__(self, modello, messaggi, max_tokens):
        self.chiamate += 1
        return self.risposta, self.token, self.esito


def _titoli_ok(n: int) -> str:
    return json.dumps([{"titolo": f"Titolo editoriale {i + 1}"}
                       for i in range(n)])


class TestSchedeDaTesto(unittest.TestCase):
    def test_titolo_e_punti(self):
        schede = schede_da_testo(PAGINE)
        self.assertEqual(len(schede), len(PAGINE))
        self.assertTrue(schede[0]["titolo"].startswith("Introduzione"))
        self.assertIn("Kernel e shell", schede[0]["punti"])
        # numeri di slide progressivi dalla pagina 1
        self.assertEqual([s["slide"] for s in schede], list(range(1, 9)))

    def test_pagina_vuota_non_esplode(self):
        schede = schede_da_testo(["", None])
        self.assertEqual(len(schede), 2)
        self.assertTrue(schede[0]["titolo"])   # fallback "Slide n"


class TestScalettaLocale(unittest.TestCase):
    def test_partizione_in_3_6_blocchi_contigui(self):
        sc = scaletta_locale(schede_da_testo(PAGINE), dispensa="L01",
                             fonte="pdf-locale")
        self.assertTrue(3 <= len(sc.voci) <= 6)
        coperte = sorted(n for v in sc.voci for n in v.slide)
        self.assertEqual(coperte, list(range(1, 9)))   # nessuna slide persa

    def test_markdown_e_persistenza(self):
        sc = scaletta_locale(schede_da_testo(PAGINE), dispensa="Lez 01")
        md = sc.to_markdown()
        self.assertIn("# Scaletta", md)
        self.assertIn("(slide ", md)
        with tempfile.TemporaryDirectory() as d:
            cartella = Path(d)
            salva_scaletta(cartella, sc)
            letta = leggi_scaletta(cartella, "Lez 01")
            self.assertIsNotNone(letta)
            self.assertEqual([v.titolo for v in letta.voci],
                             [v.titolo for v in sc.voci])
            self.assertEqual(letta.n_slide, sc.n_slide)


class TestRaffinamentoAI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.router = Router(path_stato=Path(self.tmp.name) / "_q.json")
        self.sc = scaletta_locale(schede_da_testo(PAGINE), dispensa="D")

    def test_titoli_sostituiti_una_sola_chiamata(self):
        stub = StubProvider(_titoli_ok(len(self.sc.voci)))
        out = raffinamento_con_ai(router=self.router, provider=stub,
                                  scaletta=self.sc)
        self.assertEqual(stub.chiamate, 1)
        self.assertEqual(out.fonte, "ai")
        self.assertEqual(out.token_spesi, stub.token)
        self.assertTrue(all(v.titolo.startswith("Titolo editoriale")
                            for v in out.voci))

    def test_risposta_malformata_fallback_locale(self):
        stub = StubProvider("non sono json")
        out = raffinamento_con_ai(router=self.router, provider=stub,
                                  scaletta=self.sc)
        self.assertEqual(out.fonte, "locale")
        self.assertTrue(any("non interpretabile" in n for n in out.note))

    def test_quota_esaurita_fallback_locale(self):
        stub = StubProvider("", esito="quota_esaurita")
        out = raffinamento_con_ai(router=self.router, provider=stub,
                                  scaletta=self.sc)
        self.assertEqual(out.fonte, "locale")
        self.assertTrue(any("saltato" in n for n in out.note))

    def test_conteggio_diverso_rifiutato(self):
        stub = StubProvider(_titoli_ok(len(self.sc.voci) + 2))
        out = raffinamento_con_ai(router=self.router, provider=stub,
                                  scaletta=self.sc)
        self.assertEqual(out.fonte, "locale")


class TestEstraiScalettaEndToEnd(unittest.TestCase):
    """API pubblica usata dalla UI, senza PDF ne' rete: via cache schede."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.libro_dir = self.root / "libri" / "SO"
        (self.libro_dir / "slide_estratte").mkdir(parents=True)

    def _scrivi_schede(self):
        from app.core.ai.contesto import salva_schede
        salva_schede(self.libro_dir,
                     {"L1": schede_da_testo(PAGINE)})

    def test_cache_colpita_raffinamento_una_chiamata(self):
        self._scrivi_schede()
        r = Router(path_stato=self.root / "_q.json")
        n_voci = len(scaletta_locale(schede_da_testo(PAGINE)).voci)
        stub = StubProvider(_titoli_ok(n_voci))
        sc = estrai_scaletta(root=self.root, slug="SO",
                             dispensa="Lezione 01", router=r, provider=stub)
        self.assertTrue(sc.voci)
        self.assertEqual(stub.chiamate, 1)          # una sola chiamata AI
        self.assertEqual(sc.fonte, "ai")

    def test_senza_router_zero_chiamate(self):
        self._scrivi_schede()
        sc = estrai_scaletta(root=self.root, slug="SO",
                             dispensa="Lezione 01")
        self.assertTrue(sc.voci)
        self.assertEqual(sc.token_spesi, 0)         # percorso gratuito

    def test_niente_schede_niente_pdf_notifica_ui(self):
        sc = estrai_scaletta(root=self.root, slug="SO",
                             dispensa="Lezione 09")
        self.assertFalse(sc.voci)
        self.assertTrue(any("Estrai prima" in n for n in sc.note))

    def test_forza_ai_rigenera_dalla_cache(self):
        self._scrivi_schede()
        r = Router(path_stato=self.root / "_q.json")
        stub = StubProvider(_titoli_ok(4))
        sc = estrai_scaletta(root=self.root, slug="SO",
                             dispensa="Lezione 01", router=r,
                             provider=stub, forza_ai=True)
        self.assertGreaterEqual(stub.chiamate, 1)
        self.assertEqual(sc.fonte, "ai")


if __name__ == "__main__":
    unittest.main()
