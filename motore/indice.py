# -*- coding: utf-8 -*-
"""
motore/indice.py

Definizione dell'indice (Table of Contents) del libro.
"""
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import HexColor
from reportlab.platypus.tableofcontents import TableOfContents

from motore.fonts import nome_font


_COLORE_LINK_LIV0 = "#0A1B2E"
_COLORE_LINK_LIV1 = "#1F5C8B"
_COLORE_LINK_LIV2 = "#444444"


def crea_indice():
    """Restituisce un TableOfContents vuoto con stili gerarchici pronti."""
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOC0",
            fontName=nome_font("LibroBold"), fontSize=13, leading=20,
            spaceBefore=8, spaceAfter=2,
            textColor=HexColor(_COLORE_LINK_LIV0),
        ),
        ParagraphStyle(
            name="TOC1",
            fontName=nome_font("LibroRegular"), fontSize=11, leading=16,
            leftIndent=18,
            textColor=HexColor(_COLORE_LINK_LIV1),
        ),
        ParagraphStyle(
            name="TOC2",
            fontName=nome_font("LibroItalic"), fontSize=10, leading=14,
            leftIndent=36,
            textColor=HexColor(_COLORE_LINK_LIV2),
        ),
    ]
    toc.dotsMinLevel = 0
    return toc


def stile_titolo_indice():
    return ParagraphStyle(
        name="TitoloIndice",
        fontName=nome_font("LibroBold"), fontSize=28, leading=34,
        alignment=TA_CENTER,
        textColor=HexColor("#0A1B2E"),
        spaceAfter=22,
    )