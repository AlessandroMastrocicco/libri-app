# -*- coding: utf-8 -*-
"""
motore/componenti.py

Riquadri didattici riutilizzabili + helper per paragrafi con simboli
+ tabelle ben impaginate.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    Table, TableStyle, Paragraph, Spacer, KeepTogether,
    ListFlowable, ListItem, HRFlowable,
)

from motore.stili import STILI, COLORE_ACCENTO, COLORE_PRIMARIO, COLORE_TESTO
from motore.fonts import nome_font, fix_simboli


LARGHEZZA_UTILE = A4[0] - 4 * cm


# ---------------------------------------------------------------------------
# Helper per paragrafi con simboli matematici
# ---------------------------------------------------------------------------
def P(testo: str, stile=None):
    """
    Crea un Paragraph applicando automaticamente fix_simboli.
    Da usare al posto di Paragraph(...) per testi che contengono ℤ, ℝ, ⊆, →, ecc.
    Se stile è None, usa STILI["Testo"].
    """
    if stile is None:
        stile = STILI["Testo"]
    return Paragraph(fix_simboli(testo), stile)


# ---------------------------------------------------------------------------
# Palette dei riquadri
# ---------------------------------------------------------------------------
PALETTE = {
    "regola":       {"bordo": HexColor("#1F5C8B"), "bg": HexColor("#EAF3FA"),
                     "titolo": HexColor("#0A3D62"), "label": "REGOLA"},
    "definizione":  {"bordo": HexColor("#5A3E8E"), "bg": HexColor("#F0EBF8"),
                     "titolo": HexColor("#3A2560"), "label": "DEFINIZIONE"},
    "esempio":      {"bordo": HexColor("#2E8B57"), "bg": HexColor("#EAF7EF"),
                     "titolo": HexColor("#1B5E3A"), "label": "ESEMPIO"},
    "attenzione":   {"bordo": HexColor("#D97706"), "bg": HexColor("#FEF6E7"),
                     "titolo": HexColor("#8A4B00"), "label": "ATTENZIONE"},
    "errore":       {"bordo": HexColor("#C0392B"), "bg": HexColor("#FDECEA"),
                     "titolo": HexColor("#7B241C"), "label": "ERRORE COMUNE"},
    "recap":        {"bordo": HexColor("#0E7490"), "bg": HexColor("#E6F7FB"),
                     "titolo": HexColor("#0B4F5F"), "label": "RECAP"},
    "collegamento": {"bordo": HexColor("#7C3AED"), "bg": HexColor("#F3EEFF"),
                     "titolo": HexColor("#4B1FA8"), "label": "COLLEGAMENTO CON"},
    "ppt":          {"bordo": HexColor("#B45309"), "bg": HexColor("#FFF7ED"),
                     "titolo": HexColor("#7C3D07"), "label": "RIFERIMENTO AL PPT"},
    "dritta":       {"bordo": HexColor("#0D9488"), "bg": HexColor("#E7FBF7"),
                     "titolo": HexColor("#0A6E63"), "label": "DRITTA"},
}


def _stile_label(tipo: str):
    p = PALETTE[tipo]
    return ParagraphStyle(
        name=f"Label_{tipo}",
        fontName=nome_font("LibroBold"), fontSize=9, leading=12,
        textColor=p["titolo"], spaceAfter=6,
    )


def _normalizza_contenuto(contenuto):
    if contenuto is None:
        return []
    if isinstance(contenuto, str):
        return [Paragraph(fix_simboli(contenuto), STILI["Testo"])]
    return list(contenuto)


def _riquadro(tipo: str, contenuto, titolo_extra: str = None):
    p = PALETTE[tipo]
    label = p["label"]
    if titolo_extra:
        label = f"{label} \u2014 {titolo_extra}"

    corpo = [Paragraph(label, _stile_label(tipo))]
    corpo.extend(_normalizza_contenuto(contenuto))

    tab = Table([["", corpo]], colWidths=[5, LARGHEZZA_UTILE - 5])
    tab.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), p["bordo"]),
        ("BACKGROUND",    (1, 0), (1, 0), p["bg"]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (0, 0), 0),
        ("RIGHTPADDING",  (0, 0), (0, 0), 0),
        ("TOPPADDING",    (0, 0), (0, 0), 0),
        ("BOTTOMPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING",   (1, 0), (1, 0), 12),
        ("RIGHTPADDING",  (1, 0), (1, 0), 12),
        ("TOPPADDING",    (1, 0), (1, 0), 10),
        ("BOTTOMPADDING", (1, 0), (1, 0), 10),
    ]))
    return KeepTogether([Spacer(1, 5), tab, Spacer(1, 5)])


# ---------------------------------------------------------------------------
# API pubblica dei riquadri
# ---------------------------------------------------------------------------
def regola(contenuto, titolo=None):      return _riquadro("regola", contenuto, titolo)
def definizione(contenuto, termine=None): return _riquadro("definizione", contenuto, termine)
def esempio(contenuto, titolo=None):     return _riquadro("esempio", contenuto, titolo)
def attenzione(contenuto, titolo=None):  return _riquadro("attenzione", contenuto, titolo)
def errore(contenuto, titolo=None):      return _riquadro("errore", contenuto, titolo)
def collegamento(contenuto, con=None):   return _riquadro("collegamento", contenuto, con)
def dritta(contenuto, titolo=None):      return _riquadro("dritta", contenuto, titolo)


def ppt(slide, nota=None):
    testo = f"Vedi <b>slide {slide}</b> del PPT originale."
    if nota:
        testo += f" <i>{nota}</i>"
    return _riquadro("ppt", testo, None)


def recap(punti, titolo=None):
    items = [ListItem(P(p, STILI["ElencoPuntato"]), leftIndent=14) for p in punti]
    lista = ListFlowable(items, bulletType="bullet", start="\u2022", leftIndent=14)
    return _riquadro("recap", [lista], titolo)


def codice(testo: str):
    return Paragraph(fix_simboli(testo).replace("\n", "<br/>"), STILI["Codice"])


def separatore():
    return HRFlowable(width="100%", thickness=0.7,
                      color=HexColor("#CCCCCC"),
                      spaceBefore=10, spaceAfter=10)


def spazio(cm_altezza: float = 0.4):
    return Spacer(1, cm_altezza * cm)


# ---------------------------------------------------------------------------
# Tabella vera (non ASCII art)
# ---------------------------------------------------------------------------
_ALIGN_MAP = {"LEFT": TA_LEFT, "CENTER": TA_CENTER, "RIGHT": TA_RIGHT}

_STILE_CELLA = ParagraphStyle(
    name="CellaTabella",
    fontName=nome_font("LibroRegular"),
    fontSize=10, leading=14,
    textColor=HexColor("#222222"),
)
_STILE_HEADER = ParagraphStyle(
    name="HeaderTabella",
    fontName=nome_font("LibroBold"),
    fontSize=10, leading=14,
    textColor=HexColor("#FFFFFF"),
)


def _cell_to_flowable(valore, stile, align):
    """Trasforma una cella in un Paragraph con allineamento e fix_simboli."""
    if hasattr(valore, "wrap"):
        return valore
    s = ParagraphStyle(
        name="CellaTemp",
        parent=stile,
        alignment=_ALIGN_MAP.get(align, TA_LEFT),
    )
    return Paragraph(fix_simboli(str(valore)), s)


def tabella(headers, righe, col_widths=None, allineamenti=None,
            font_size=10, leading=14):
    """
    Crea una tabella ReportLab ben impaginata.
    """
    if not righe and not headers:
        return Spacer(1, 0)

    n_cols = len(headers) if headers else len(righe[0])

    if allineamenti is None:
        allineamenti = ["LEFT"] * n_cols
    if len(allineamenti) < n_cols:
        allineamenti = list(allineamenti) + ["LEFT"] * (n_cols - len(allineamenti))

    if col_widths is None:
        col_widths = [LARGHEZZA_UTILE / n_cols] * n_cols

    stile_cella = ParagraphStyle(
        name="CellaTabellaDyn", parent=_STILE_CELLA,
        fontSize=font_size, leading=leading,
    )
    stile_header = ParagraphStyle(
        name="HeaderTabellaDyn", parent=_STILE_HEADER,
        fontSize=font_size, leading=leading,
    )

    dati = []
    if headers:
        dati.append([_cell_to_flowable(h, stile_header, a)
                     for h, a in zip(headers, allineamenti)])
    for riga in righe:
        dati.append([_cell_to_flowable(v, stile_cella, a)
                     for v, a in zip(riga, allineamenti)])

    tab = Table(
        dati,
        colWidths=col_widths,
        repeatRows=1 if headers else 0,
    )

    stile_tab = [
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#1F5C8B")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#DDDDDD")),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, HexColor("#CCCCCC")),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS",
         (0, 1 if headers else 0), (-1, -1),
         [HexColor("#FFFFFF"), HexColor("#F4F8FC")]),
    ]

    if headers:
        stile_tab.append(("BACKGROUND", (0, 0), (-1, 0), HexColor("#1F5C8B")))
        stile_tab.append(("LINEBELOW", (0, 0), (-1, 0), 0.8, HexColor("#0A3D62")))

    tab.setStyle(TableStyle(stile_tab))

    return KeepTogether([Spacer(1, 6), tab, Spacer(1, 8)])