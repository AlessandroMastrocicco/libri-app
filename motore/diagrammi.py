# -*- coding: utf-8 -*-
"""
motore/diagrammi.py

Modulo per generare diagrammi avanzati nei libri.

- Diagrammi di Venn (2 o 3 insiemi) — richiede matplotlib-venn
- Alberi (gerarchie, alberi binari, alberi decisionali) — networkx
- Grafi (reti, reticoli) — networkx
- Array illustrati (ricerca sequenziale, ricerca binaria, ordinamento)
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
    cartella = RADICE_PROGETTO / "libri" / _libro_corrente / "diagrammi"
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
        name="DidascaliaDiagramma",
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


# ---------------------------------------------------------------------------
# DIAGRAMMI DI VENN
# ---------------------------------------------------------------------------
def diagramma_venn(gruppi, etichette=None, titolo=None,
                   didascalia=None, dpi=150):
    try:
        from matplotlib_venn import venn2, venn3
    except ImportError:
        print("[ERR] matplotlib-venn non installato. "
              "Esegui: pip install matplotlib-venn")
        return []

    if len(gruppi) not in (2, 3):
        print(f"[WARN] diagramma_venn supporta 2 o 3 insiemi, "
              f"ricevuti {len(gruppi)}")
        return []

    insiemi = [set(g) for g in gruppi]

    nomi_default = ["A", "B", "C"][:len(insiemi)]
    labels = []
    for i, nome in enumerate(nomi_default):
        if etichette and nome in etichette:
            labels.append(etichette[nome])
        else:
            labels.append(nome)

    parametri = dict(
        tipo="venn", n=len(insiemi), etichette=labels,
        sizes=[len(s) for s in insiemi], titolo=titolo, dpi=dpi,
        set_a=sorted(insiemi[0]),
        set_b=sorted(insiemi[1]),
        set_c=sorted(insiemi[2]) if len(insiemi) == 3 else None,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(6.0, 4.5))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        if len(insiemi) == 2:
            venn2(insiemi, set_labels=labels, ax=ax)
        else:
            venn3(insiemi, set_labels=labels, ax=ax)

        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


# ---------------------------------------------------------------------------
# ALBERI
# ---------------------------------------------------------------------------
def _layout_albero(radice, figli):
    posizioni = {}
    archi = []
    nodi_ordinati = []

    counter = [0]

    def posiziona(nodo, profondita):
        bambini = figli.get(nodo, [])
        if not bambini:
            x = counter[0]
            counter[0] += 1
        else:
            xs = [posiziona(b, profondita + 1) for b in bambini]
            x = sum(xs) / len(xs)
            for b in bambini:
                archi.append((nodo, b))
        posizioni[nodo] = (x, -profondita)
        nodi_ordinati.append(nodo)
        return x

    posiziona(radice, 0)
    return posizioni, archi, nodi_ordinati


def albero(radice, figli, titolo=None, didascalia=None,
           colore_nodi="#1F5C8B", colore_archi="#666666",
           forma_nodo="o", dpi=150):
    parametri = dict(
        tipo="albero", radice=radice,
        figli=tuple((k, tuple(v)) for k, v in sorted(figli.items())),
        titolo=titolo, dpi=dpi, colore_nodi=colore_nodi,
        forma_nodo=forma_nodo,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(figsize=(7.0, 4.5))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        posizioni, archi, nodi = _layout_albero(radice, figli)

        for padre, figlio in archi:
            x1, y1 = posizioni[padre]
            x2, y2 = posizioni[figlio]
            ax.plot([x1, x2], [y1, y2], color=colore_archi,
                    linewidth=1.2, zorder=1)

        for nodo in nodi:
            x, y = posizioni[nodo]
            ax.scatter([x], [y], s=600, marker=forma_nodo,
                       facecolor="#EAF3FA", edgecolor=colore_nodi,
                       linewidth=1.5, zorder=2)
            ax.text(x, y, str(nodo), ha="center", va="center",
                    fontsize=10, color="#0A1B2E", zorder=3,
                    fontweight="bold")

        ax.set_aspect("equal")
        ax.axis("off")
        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


# ---------------------------------------------------------------------------
# GRAFI
# ---------------------------------------------------------------------------
def grafo(nodi, archi, titolo=None, didascalia=None,
          orientato=False, layout="circular",
          colore_nodi="#1F5C8B", colore_archi="#666666", dpi=150):
    parametri = dict(
        tipo="grafo", nodi=tuple(nodi),
        archi=tuple(sorted(tuple(e) for e in archi)),
        titolo=titolo, dpi=dpi, orientato=orientato,
        layout=layout, colore_nodi=colore_nodi,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        try:
            import networkx as nx
        except ImportError:
            print("[WARN] networkx non installato. "
                  "Esegui: pip install networkx")
            return []

        _stile_matplotlib()
        fig = Figure(figsize=(6.5, 5.0))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)

        if orientato:
            G = nx.DiGraph()
        else:
            G = nx.Graph()
        G.add_nodes_from(nodi)
        G.add_edges_from(archi)

        if layout == "circular":
            pos = nx.circular_layout(G)
        elif layout == "spring":
            pos = nx.spring_layout(G, seed=42)
        elif layout == "kamada_kawai":
            pos = nx.kamada_kawai_layout(G)
        elif layout == "shell":
            pos = nx.shell_layout(G)
        else:
            pos = nx.circular_layout(G)

        nx.draw_networkx_nodes(
            G, pos, ax=ax,
            node_color="#EAF3FA",
            edgecolors=colore_nodi,
            node_size=800,
            linewidths=1.5,
        )
        nx.draw_networkx_labels(
            G, pos, ax=ax,
            font_size=10,
            font_color="#0A1B2E",
            font_weight="bold",
        )
        nx.draw_networkx_edges(
            G, pos, ax=ax,
            edge_color=colore_archi,
            width=1.2,
            arrows=orientato,
            arrowsize=12,
        )

        ax.set_aspect("equal")
        ax.axis("off")
        if titolo:
            ax.set_title(titolo)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)


# ---------------------------------------------------------------------------
# ARRAY ILLUSTRATI
# ---------------------------------------------------------------------------
def array_illustrato(
    valori,
    indice_evidenziato=None,
    valore_cercato=None,
    etichetta_risultato=None,
    mostra_indici=True,
    titolo=None,
    didascalia=None,
    dpi=150,
):
    from matplotlib.patches import Rectangle, Ellipse

    n = len(valori)
    if n == 0:
        return []

    larghezza_cella = 1.0
    altezza_cella = 1.0

    spazio_ellisse = 1.6 if (valore_cercato or etichetta_risultato) else 0.3
    margine_sinistro = spazio_ellisse if valore_cercato else 0.3
    margine_destro = spazio_ellisse if etichetta_risultato else 0.3
    margine_superiore = 0.9 if indice_evidenziato is not None else 0.3
    margine_inferiore = 0.8 if mostra_indici else 0.3

    larghezza_tot = margine_sinistro + n * larghezza_cella + margine_destro
    altezza_tot = margine_superiore + altezza_cella + margine_inferiore

    scala = 0.55

    parametri = dict(
        tipo="array_illustrato",
        valori=tuple(valori),
        indice_evidenziato=indice_evidenziato,
        valore_cercato=valore_cercato,
        etichetta_risultato=etichetta_risultato,
        mostra_indici=mostra_indici,
        titolo=titolo,
        dpi=dpi,
    )
    path = _cartella_cache() / _hash_immagine(parametri)

    if not path.exists():
        _stile_matplotlib()
        fig = Figure(
            figsize=(larghezza_tot * scala, altezza_tot * scala),
            dpi=dpi,
        )
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_xlim(0, larghezza_tot)
        ax.set_ylim(0, altezza_tot)
        ax.set_aspect("equal")
        ax.axis("off")

        colore_bordo = "#8B1A1A"
        colore_testo = "#222222"

        y_base = margine_inferiore
        for i, v in enumerate(valori):
            x = margine_sinistro + i * larghezza_cella
            rect = Rectangle(
                (x, y_base), larghezza_cella, altezza_cella,
                facecolor="#FFFFFF",
                edgecolor=colore_bordo,
                linewidth=1.8,
            )
            ax.add_patch(rect)
            ax.text(
                x + larghezza_cella / 2,
                y_base + altezza_cella / 2,
                str(v),
                ha="center", va="center",
                fontsize=11, color=colore_testo,
            )
            if mostra_indici:
                ax.text(
                    x + larghezza_cella / 2,
                    y_base - 0.15,
                    f"{i}",
                    ha="center", va="top",
                    fontsize=9, color="#555555",
                )

        if indice_evidenziato is not None and 0 <= indice_evidenziato < n:
            x_centro = (
                margine_sinistro
                + indice_evidenziato * larghezza_cella
                + larghezza_cella / 2
            )
            y_fine = y_base + altezza_cella
            y_inizio = y_fine + 0.6
            ax.annotate(
                "",
                xy=(x_centro, y_fine),
                xytext=(x_centro, y_inizio),
                arrowprops=dict(
                    arrowstyle="-|>",
                    color=colore_bordo,
                    linewidth=2.0,
                    mutation_scale=18,
                ),
            )

        if valore_cercato:
            x_ell = margine_sinistro / 2
            y_ell = y_base + altezza_cella / 2
            ell = Ellipse(
                (x_ell, y_ell), 1.0, 0.7,
                facecolor="#FFFFFF",
                edgecolor=colore_bordo,
                linewidth=1.8,
            )
            ax.add_patch(ell)
            ax.text(
                x_ell, y_ell, str(valore_cercato),
                ha="center", va="center",
                fontsize=10, color=colore_bordo,
            )

        if etichetta_risultato:
            x_ell = larghezza_tot - margine_destro / 2
            y_ell = y_base + altezza_cella / 2
            ell = Ellipse(
                (x_ell, y_ell), 1.1, 0.7,
                facecolor="#FFFFFF",
                edgecolor=colore_bordo,
                linewidth=1.8,
            )
            ax.add_patch(ell)
            ax.text(
                x_ell, y_ell, str(etichetta_risultato),
                ha="center", va="center",
                fontsize=10, color=colore_bordo,
            )

        if titolo:
            ax.set_title(titolo, fontsize=11, color=colore_testo, pad=8)

        fig.tight_layout()
        fig.savefig(str(path), dpi=dpi)

    return _flowable_immagine(path, didascalia, dpi)