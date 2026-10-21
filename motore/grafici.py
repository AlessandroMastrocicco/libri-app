# -*- coding: utf-8 -*-
"""
motore/grafici.py

Modulo per generare diagrammi scientifici nei libri.
"""
import hashlib
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from PIL import Image as PILImage

from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    Image, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)

from motore.fonts import nome_font


RADICE_PROGETTO = Path(__file__).parent.parent
LARGHEZZA_UTILE = 17 * cm

_libro_corrente = None


def set_libro_corrente(nome):
    global _libro_corrente
    _libro_corrente = nome


def _cartella_cache():
    if _libro_corrente is None:
        raise RuntimeError(
            "Nessun libro corrente impostato. "
            "Il builder deve chiamare set_libro_corrente()."
        )
    cartella = RADICE_PROGETTO / "libri" / _libro_corrente / "grafici"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


def _hash_immagine(parametri):
    chiave = repr(sorted(parametri.items()))
    h = hashlib.md5(chiave.encode("utf-8")).hexdigest()[:16]
    return f"{h}.png"


def _stile_matplotlib():
    from matplotlib import rcParams
    rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.labelsize": 10,
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": "#DDDDDD",
        "grid.linewidth": 0.5,
        "grid.linestyle": "--",
        "xtick.color": "#333333",
        "ytick.color": "#333333",
        "legend.frameon": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
    })


def _dimensioni_in_punti(path, dpi):
    with PILImage.open(path) as im:
        w_px, h_px = im.size
    fattore = 72.0 / dpi
    return w_px * fattore, h_px * fattore


def _stile_didascalia():
    return ParagraphStyle(
        name="DidascaliaGrafico",
        fontName=nome_font("LibroItalic"),
        fontSize=9, leading=12,
        textColor=HexColor("#555555"),
        alignment=TA_CENTER,
        spaceBefore=4,
    )


def _flowable_immagine(path, didascalia, dpi):
    w_pt, h_pt = _dimensioni_in_punti(path, dpi)

    if w_pt > LARGHEZZA_UTILE:
        fattore = LARGHEZZA_UTILE / w_pt
        w_pt *= fattore
        h_pt *= fattore

    img = Image(str(path), width=w_pt, height=h_pt)
    wrapper = Table([[img]], colWidths=[LARGHEZZA_UTILE])
    wrapper.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    elementi = [wrapper]
    if didascalia:
        elementi.append(Paragraph(didascalia, _stile_didascalia()))
    return [Spacer(1, 6), KeepTogether(elementi), Spacer(1, 8)]


def grafico_funzione(f, x_range=(-5, 5), y_range=None,
                     titolo=None, x_label="x", y_label="y",
                     colore="#1F5C8B", spessore=1.8,
                     punti=400, didascalia=None, dpi=150):
    parametri = dict(
        tipo="funzione", x_range=x_range, y_range=y_range,
        titolo=titolo, x_label=x_label, y_label=y_label,
        colore=colore, spessore=spessore, punti=punti, dpi=dpi,
        f_name=getattr(f, "__name__", "lambda"),
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.5, 4.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        xs = np.linspace(x_range[0], x_range[1], punti)
        try:
            ys = f(xs)
        except Exception as e:
            print(f"[WARN] Errore nel valutare la funzione: {e}")
            return []

        ax.plot(xs, ys, color=colore, linewidth=spessore)
        ax.axhline(0, color="#333333", linewidth=0.7)
        ax.axvline(0, color="#333333", linewidth=0.7)

        if y_range is not None:
            ax.set_ylim(*y_range)
        ax.set_xlim(*x_range)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


def grafico_funzioni(funzioni, x_range=(-5, 5), y_range=None,
                     titolo=None, x_label="x", y_label="y",
                     punti=400, didascalia=None, dpi=150):
    parametri = dict(
        tipo="funzioni_multi", x_range=x_range, y_range=y_range,
        titolo=titolo, x_label=x_label, y_label=y_label,
        n=len(funzioni), punti=punti, dpi=dpi,
        labels=[t[1] for t in funzioni],
        colori=[t[2] for t in funzioni],
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.5, 4.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        xs = np.linspace(x_range[0], x_range[1], punti)
        for f, etichetta, colore in funzioni:
            try:
                ys = f(xs)
                ax.plot(xs, ys, color=colore, linewidth=1.8,
                        label=etichetta)
            except Exception as e:
                print(f"[WARN] Errore nel valutare {etichetta}: {e}")

        ax.axhline(0, color="#333333", linewidth=0.7)
        ax.axvline(0, color="#333333", linewidth=0.7)

        if y_range is not None:
            ax.set_ylim(*y_range)
        ax.set_xlim(*x_range)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if titolo:
            ax.set_title(titolo)
        ax.legend(loc="best")

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


def piano_cartesiano(x_range=(-5, 5), y_range=(-5, 5),
                     punti_griglia=1, titolo=None,
                     x_label="x", y_label="y",
                     didascalia=None, dpi=150):
    parametri = dict(
        tipo="piano", x_range=x_range, y_range=y_range,
        griglia=punti_griglia, titolo=titolo,
        x_label=x_label, y_label=y_label, dpi=dpi,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.0, 6.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        ax.set_xlim(*x_range)
        ax.set_ylim(*y_range)
        ax.set_aspect("equal", adjustable="box")

        ax.set_xticks(np.arange(x_range[0], x_range[1] + 0.001, punti_griglia))
        ax.set_yticks(np.arange(y_range[0], y_range[1] + 0.001, punti_griglia))

        ax.axhline(0, color="#333333", linewidth=1.0)
        ax.axvline(0, color="#333333", linewidth=1.0)

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


def grafico_barre(categorie, valori, colore="#1F5C8B",
                  titolo=None, x_label="", y_label="",
                  didascalia=None, dpi=150):
    parametri = dict(
        tipo="barre", categorie=list(categorie), valori=list(valori),
        colore=colore, titolo=titolo, x_label=x_label, y_label=y_label,
        dpi=dpi,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.5, 4.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        xpos = np.arange(len(categorie))
        ax.bar(xpos, valori, color=colore)
        ax.set_xticks(xpos)
        ax.set_xticklabels(categorie)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if titolo:
            ax.set_title(titolo)
        ax.grid(axis="y", linestyle="--", color="#DDDDDD", linewidth=0.5)
        ax.grid(axis="x", visible=False)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


def grafico_dispersione(xs, ys, colore="#1F5C8B",
                        titolo=None, x_label="x", y_label="y",
                        didascalia=None, dpi=150):
    parametri = dict(
        tipo="scatter", xs=list(xs), ys=list(ys),
        colore=colore, titolo=titolo, x_label=x_label, y_label=y_label,
        dpi=dpi,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.5, 4.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        ax.scatter(xs, ys, color=colore, s=25)
        ax.axhline(0, color="#333333", linewidth=0.7)
        ax.axvline(0, color="#333333", linewidth=0.7)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)