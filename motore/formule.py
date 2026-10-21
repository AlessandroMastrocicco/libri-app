# -*- coding: utf-8 -*-
"""
motore/formule.py

Modulo per renderizzare formule matematiche complesse via matplotlib.

- Usa matplotlib mathtext (sottoinsieme di LaTeX) per generare PNG trasparenti
- Le immagini sono cachate in libri/NOME_LIBRO/formule/
- Supporta integrali, frazioni, sommatorie, matrici, lettere greche, ecc.

Uso:
    from motore.formule import formula

    formula(r"\\int_0^\\infty e^{-x^2} \\, dx = \\frac{\\sqrt{\\pi}}{2}")
    formula(r"f(x) = \\sum_{n=0}^\\infty a_n x^n", numero="(3.1)")

Nota: NON serve \\usepackage, non serve installare LaTeX.
"""
import hashlib
from pathlib import Path

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image as PILImage

from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    Image, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

from motore.fonts import nome_font


RADICE_PROGETTO = Path(__file__).parent.parent
LARGHEZZA_UTILE = 17 * cm

_libro_corrente = None


def set_libro_corrente(nome):
    """Imposta il nome del libro corrente (chiamato da builder.py)."""
    global _libro_corrente
    _libro_corrente = nome


def _cartella_cache():
    if _libro_corrente is None:
        raise RuntimeError(
            "Nessun libro corrente impostato. "
            "Il builder deve chiamare set_libro_corrente()."
        )
    cartella = RADICE_PROGETTO / "libri" / _libro_corrente / "formule"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


def _nome_cache(latex, fontsize, dpi, colore):
    chiave = f"{latex}|{fontsize}|{dpi}|{colore}"
    h = hashlib.md5(chiave.encode("utf-8")).hexdigest()[:16]
    return f"{h}.png"


def _render_formula(latex, path, fontsize, dpi, colore):
    """Renderizza una formula LaTeX-like in PNG trasparente."""
    fig = Figure(figsize=(0.01, 0.01))
    FigureCanvasAgg(fig)
    testo = latex if latex.strip().startswith("$") else f"${latex}$"
    fig.text(0, 0, testo, fontsize=fontsize, color=colore)
    fig.savefig(
        str(path),
        dpi=dpi,
        transparent=True,
        bbox_inches="tight",
        pad_inches=0.03,
    )


def _dimensioni_in_punti(path, dpi):
    """Restituisce larghezza/altezza in punti, dal PNG al DPI specificato."""
    with PILImage.open(path) as im:
        w_px, h_px = im.size
    fattore = 72.0 / dpi
    return w_px * fattore, h_px * fattore


def _stile_numero():
    return ParagraphStyle(
        name="NumeroFormula",
        fontName=nome_font("LibroRegular"),
        fontSize=10, leading=14,
        textColor=HexColor("#555555"),
        alignment=TA_RIGHT,
    )


def formula(latex, numero=None, fontsize=11, dpi=200, colore="#111111",
            allineamento="CENTER"):
    """
    Renderizza una formula matematica come blocco centrato.
    Restituisce una lista di flowables.
    """
    cartella = _cartella_cache()
    nome = _nome_cache(latex, fontsize, dpi, colore)
    path = cartella / nome

    if not path.exists():
        try:
            _render_formula(latex, path, fontsize, dpi, colore)
        except Exception as e:
            print(f"[WARN] Formula non renderizzabile: {latex!r} ({e})")
            stile = ParagraphStyle(
                name="FormulaFallback",
                fontName=nome_font("LibroMono"),
                fontSize=9.5, leading=13,
                textColor=HexColor("#B03A2E"),
            )
            return [
                Spacer(1, 4),
                Paragraph(f"<b>Formula non renderizzabile:</b><br/>"
                          f"<font size='8'>{latex}</font>", stile),
                Spacer(1, 8),
            ]

    w_pt, h_pt = _dimensioni_in_punti(path, dpi)

    if w_pt > LARGHEZZA_UTILE:
        fattore = LARGHEZZA_UTILE / w_pt
        w_pt *= fattore
        h_pt *= fattore

    img = Image(str(path), width=w_pt, height=h_pt)

    if numero:
        col_spacer = (LARGHEZZA_UTILE - w_pt - 3 * cm) / 2
        if col_spacer < 0:
            col_spacer = 0.5 * cm
        col_formula = w_pt
        col_numero = LARGHEZZA_UTILE - col_spacer - col_formula
        tab = Table(
            [["", img, Paragraph(numero, _stile_numero())]],
            colWidths=[col_spacer, col_formula, col_numero],
        )
        tab.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow = tab
    else:
        tab = Table([[img]], colWidths=[LARGHEZZA_UTILE])
        tab.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), allineamento.upper()),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        flow = tab

    return [Spacer(1, 6), KeepTogether([flow]), Spacer(1, 8)]