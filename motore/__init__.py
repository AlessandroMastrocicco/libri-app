# -*- coding: utf-8 -*-
"""
motore - Framework ReportLab condiviso per la generazione dei PDF.

Punti di ingresso principali:
- motore.builder.costruisci_libro(nome_libro, percorso_output=None)
- motore.fonts.registra_font()
- motore.stili.STILI
- motore.componenti (P, regola, tabella, codice, ecc.)

Nota: il bootstrap dei font avviene automaticamente al primo import
di motore.stili (che chiama registra_font() a livello di modulo).
"""

__version__ = "1.0.0"