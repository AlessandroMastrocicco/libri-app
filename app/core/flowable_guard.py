# -*- coding: utf-8 -*-
"""
flowable_guard.py - Pre-validazione dei flowables prima della build.

Assaggia ogni flowable con .wrap() in condizioni note. Se fallisce,
lo sostituisce con un placeholder leggibile e lo segnala al report.
"""

from __future__ import annotations

import traceback

from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable, PageBreak, FrameBreak, NextPageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)

from motore.fonts import nome_font


def _stile_errore():
    return ParagraphStyle(
        name="FlowableErrore",
        fontName=nome_font("LibroMono"),
        fontSize=8.5, leading=11,
        textColor=HexColor("#7B241C"),
    )


def _placeholder_errore(messaggio: str, dettaglio: str = ""):
    testo = (
        f"<b>Flowable non renderizzabile</b><br/>"
        f"{messaggio}"
    )
    if dettaglio:
        testo += (
            f'<br/><br/><font size="7" color="#888888">'
            f'{dettaglio[:400]}</font>'
        )
    par = Paragraph(testo, _stile_errore())
    tab = Table([[par]], colWidths=[17 * cm])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FDECEA")),
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#C0392B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 4), tab, Spacer(1, 6)]


# Flowable strutturali che non hanno .wrap() significativo
_NON_FLOWABLE = (PageBreak, FrameBreak, NextPageTemplate)


def pre_valida_story(story, report,
                     contesto: str,
                     larghezza_utile: float = 17 * cm,
                     altezza_pagina: float = 20 * cm):
    """
    Assaggia ogni flowable della story chiamando .wrap().

    Ritorna una nuova story in cui i flowable che falliscono sono
    sostituiti da un placeholder. Aggiorna `report`.
    """
    story_valida = []
    for i, f in enumerate(story):
        # oggetti strutturali: passano senza controllo
        if isinstance(f, _NON_FLOWABLE):
            story_valida.append(f)
            continue
        if not isinstance(f, Flowable):
            # non e' un flowable: passa cosi' com'e' (ReportLab lo gestira')
            story_valida.append(f)
            continue

        try:
            f.wrap(larghezza_utile, altezza_pagina)
            story_valida.append(f)
        except Exception as e:
            tipo = type(f).__name__
            msg = f"{tipo}: {e}"
            tb = traceback.format_exc()
            report.errore(
                origine="flowable",
                contesto=f"{contesto} (indice {i})",
                messaggio=msg,
                dettaglio=tb,
            )
            story_valida.extend(
                _placeholder_errore(f"Flowable {tipo} all'indice {i}", tb)
            )
    return story_valida