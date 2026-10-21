# -*- coding: utf-8 -*-
"""
motore/copertina.py

Copertina del libro.

La copertina è parametrica: riceve un dizionario `meta` con i metadati
del libro (TITOLO, SOTTOTITOLO, AUTORE, ANNO) e restituisce una callback
onPage pronta per ReportLab.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import cm

from motore.fonts import nome_font


def _gradiente_verticale(c, x, y, w, h, colore_top, colore_bottom, steps=300):
    for i in range(steps):
        t = i / (steps - 1)
        r = colore_top.red   + (colore_bottom.red   - colore_top.red)   * t
        g = colore_top.green + (colore_bottom.green - colore_top.green) * t
        b = colore_top.blue  + (colore_bottom.blue  - colore_top.blue)  * t
        c.setFillColorRGB(r, g, b)
        c.rect(x, y + h - (i + 1) * h / steps, w, h / steps + 0.6,
               stroke=0, fill=1)


def _cilindro_database(c, cx, cy, rx, ry, h_body):
    c.setFillColor(HexColor("#5AA9E6"))
    c.rect(cx - rx, cy - h_body / 2, 2 * rx, h_body, stroke=0, fill=1)

    c.setFillColor(HexColor("#2E6FA8"))
    c.ellipse(cx - rx, cy - h_body / 2 - ry,
              cx + rx, cy - h_body / 2 + ry, stroke=0, fill=1)

    c.setFillColor(HexColor("#5AA9E6"))
    c.ellipse(cx - rx, cy + h_body / 2 - ry,
              cx + rx, cy + h_body / 2 + ry, stroke=0, fill=1)

    c.setFillColor(HexColor("#0A1B2E"))
    c.ellipse(cx - rx * 0.75, cy + h_body / 2 - ry * 0.65,
              cx + rx * 0.75, cy + h_body / 2 + ry * 0.65,
              stroke=0, fill=1)

    c.setStrokeColor(HexColor("#0A1B2E"))
    c.setLineWidth(1.2)
    for dy in (-0.35 * h_body, 0.0, 0.35 * h_body):
        c.line(cx - rx * 0.85, cy + dy,
               cx + rx * 0.85, cy + dy)


def crea_disegnatore_copertina(meta):
    """
    Restituisce una callback onPage per disegnare la copertina.

    Parametri
    ---------
    meta : dict
        Dizionario con chiavi: TITOLO, SOTTOTITOLO, AUTORE, ANNO.
    """
    TITOLO      = meta.get("TITOLO", "")
    SOTTOTITOLO = meta.get("SOTTOTITOLO", "")
    AUTORE      = meta.get("AUTORE", "")
    ANNO        = meta.get("ANNO", "")

    def disegna_copertina(c, doc):
        w, h = A4

        # 1) sfondo gradiente
        _gradiente_verticale(c, 0, 0, w, h,
                             HexColor("#0A1B2E"),
                             HexColor("#1F5C8B"))

        # 2) banda diagonale
        c.saveState()
        c.setFillColor(HexColor("#00B4D8"))
        p = c.beginPath()
        p.moveTo(0, h * 0.30)
        p.lineTo(w, h * 0.24)
        p.lineTo(w, h * 0.20)
        p.lineTo(0, h * 0.26)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
        c.restoreState()

        # 3) pattern di puntini
        c.saveState()
        c.setFillColor(HexColor("#1E6FA8"))
        for i in range(6):
            for j in range(6):
                c.circle(1.2 * cm + i * 0.35 * cm,
                         h - 1.2 * cm - j * 0.35 * cm,
                         0.04 * cm, stroke=0, fill=1)
        c.restoreState()

        # 4) icona database
        _cilindro_database(c, cx=w / 2, cy=h * 0.66,
                           rx=2.4 * cm, ry=0.55 * cm, h_body=2.6 * cm)

        # 5) titolo
        c.setFillColor(white)
        c.setFont(nome_font("LibroBold"), 46)
        c.drawCentredString(w / 2, h * 0.47, TITOLO)

        # 6) sottotitolo
        c.setFillColor(HexColor("#00B4D8"))
        c.setFont(nome_font("LibroBold"), 22)
        c.drawCentredString(w / 2, h * 0.41, SOTTOTITOLO)

        # 7) linea decorativa
        c.setStrokeColor(HexColor("#00B4D8"))
        c.setLineWidth(2)
        c.line(w * 0.32, h * 0.375, w * 0.68, h * 0.375)

        # 8) autore
        c.setFillColor(HexColor("#B8D4E8"))
        c.setFont(nome_font("LibroRegular"), 14)
        c.drawCentredString(w / 2, h * 0.32, AUTORE)

        # 9) anno
        c.setFillColor(HexColor("#7FA8C9"))
        c.setFont(nome_font("LibroItalic"), 12)
        c.drawCentredString(w / 2, h * 0.08, ANNO)

    return disegna_copertina