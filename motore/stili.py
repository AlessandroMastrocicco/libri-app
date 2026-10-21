# -*- coding: utf-8 -*-
"""
motore/stili.py

Stili ReportLab del libro. Il bootstrap dei font avviene QUI, a
import-time, tramite registra_font().
"""
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.lib.colors import HexColor

from motore.fonts import registra_font, nome_font

# Registra i font UNA VOLTA all'import
registra_font()

# --- Palette del tema ---
COLORE_PRIMARIO   = HexColor("#0A1B2E")
COLORE_ACCENTO    = HexColor("#00B4D8")
COLORE_SECONDARIO = HexColor("#1F5C8B")
COLORE_TESTO      = HexColor("#222222")
COLORE_MUTO       = HexColor("#666666")


def _crea_stili():
    return {
        # --- Titoli gerarchici (i nomi DEVONO restare questi: builder li intercetta) ---
        "Capitolo": ParagraphStyle(
            name="Capitolo",
            fontName=nome_font("LibroBold"), fontSize=24, leading=30,
            textColor=COLORE_PRIMARIO,
            spaceBefore=4, spaceAfter=18,
        ),
        "Paragrafo": ParagraphStyle(
            name="Paragrafo",
            fontName=nome_font("LibroBold"), fontSize=15, leading=20,
            textColor=COLORE_SECONDARIO,
            spaceBefore=16, spaceAfter=8,
        ),
        "Sottoparagrafo": ParagraphStyle(
            name="Sottoparagrafo",
            fontName=nome_font("LibroBold"), fontSize=12, leading=16,
            textColor=COLORE_TESTO,
            spaceBefore=10, spaceAfter=6,
        ),

        # --- Testo ---
        "Testo": ParagraphStyle(
            name="Testo",
            fontName=nome_font("LibroRegular"), fontSize=11, leading=16.5,
            textColor=COLORE_TESTO,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "TestoPiccolo": ParagraphStyle(
            name="TestoPiccolo",
            fontName=nome_font("LibroRegular"), fontSize=9.5, leading=13,
            textColor=COLORE_MUTO,
            alignment=TA_LEFT,
        ),

        # --- Elenchi ---
        "ElencoPuntato": ParagraphStyle(
            name="ElencoPuntato",
            fontName=nome_font("LibroRegular"), fontSize=11, leading=15,
            textColor=COLORE_TESTO,
            alignment=TA_LEFT,
        ),
        "ElencoNumerato": ParagraphStyle(
            name="ElencoNumerato",
            fontName=nome_font("LibroRegular"), fontSize=11, leading=15,
            textColor=COLORE_TESTO,
            alignment=TA_LEFT,
        ),

        # --- Codice ---
        "Codice": ParagraphStyle(
            name="Codice",
            fontName=nome_font("LibroMono"), fontSize=9.5, leading=13,
            textColor=HexColor("#111111"),
            backColor=HexColor("#F4F4F4"),
            borderPadding=6,
            leftIndent=4, rightIndent=4,
        ),
        "CodiceInline": ParagraphStyle(
            name="CodiceInline",
            fontName=nome_font("LibroMonoBold"), fontSize=10.5, leading=14,
            textColor=HexColor("#7B241C"),
        ),

        # --- Titolo sezione ---
        "TitoloSezione": ParagraphStyle(
            name="TitoloSezione",
            fontName=nome_font("LibroBold"), fontSize=18, leading=24,
            textColor=COLORE_PRIMARIO,
            alignment=TA_CENTER,
            spaceBefore=10, spaceAfter=20,
        ),
    }


STILI = _crea_stili()