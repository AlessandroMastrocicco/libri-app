# -*- coding: utf-8 -*-
"""
ai - Infrastruttura per la generazione assistita dei paragrafi (BOZZA).

Moduli:
  catalogo  : modelli gratuiti disponibili, classi di capacita', quote/giorno
  tokeni    : stima token CJK-safe, troncamento, budget assembler
  router    : scelta modello per classe + switch automatico su quota esaurita
  prompt    : compressione pattern, cache statica/dinamica, boilerplate locale
  contesto  : memoria (digest, indice figure, schede slide)
  pipeline  : orchestrazione draft -> valida -> auto-ripara -> commit sicuro

Integrazione UI prevista in Fase C (docs/BOZZA_SISTEMA_AI.md): selettore
manuale/assistita in SchermataCreaParagrafo. Nessun collegamento runtime
ancora attivo: la modalita' manuale attuale resta l'unica esposta.
"""

from app.core.ai.catalogo import CLASSI, MODELLI, Modello, modelli_per_classe
from app.core.ai.tokeni import (BloccoContesto, assembla_contesto, stima_token,
                                stima_token_messaggi, troncava_per_righe)
from app.core.ai.router import Router, QuotaEsauritaException
from app.core.ai.prompt import pattern_compresso, costruisci_messaggi
from app.core.ai.pipeline import EsitoTask, genera_paragrafo_assistito

__all__ = [
    "CLASSI", "MODELLI", "Modello", "modelli_per_classe",
    "BloccoContesto", "assembla_contesto", "stima_token",
    "stima_token_messaggi", "troncava_per_righe",
    "Router", "QuotaEsauritaException",
    "pattern_compresso", "costruisci_messaggi",
    "EsitoTask", "genera_paragrafo_assistito",
]
