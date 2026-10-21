# -*- coding: utf-8 -*-
"""
motore/builder.py

Costruisce il PDF per un libro specifico.

Supporta un parametro opzionale `report` (BuildReport). Se fornito:
- protegge la chiamata a story() di ciascun capitolo con try/except;
- cattura stdout/stderr emessi dal motore durante multiBuild;
- raccoglie eventuali WARN/ERR nel report;
- produce comunque il PDF, anche in presenza di errori.

Se `report` e' None, il comportamento e' identico alla versione
precedente (nessuna cattura, nessuna protezione aggiuntiva).
"""
import contextlib
import importlib
import io
import sys
import traceback
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    NextPageTemplate, PageBreak, Spacer, Paragraph,
)

from motore.fonts import registra_font, nome_font, fix_simboli
from motore.stili import STILI
from motore.indice import crea_indice, stile_titolo_indice
from motore.discovery import scopri_capitoli
from motore import immagini as _mod_immagini
from motore import formule as _mod_formule
from motore import grafici as _mod_grafici
from motore import diagrammi as _mod_diagrammi


RADICE_PROGETTO = Path(__file__).parent.parent


# ======================================================================
# Utility
# ======================================================================

def _assicura_radice_nel_path():
    r = str(RADICE_PROGETTO)
    if r not in sys.path:
        sys.path.insert(0, r)


def _carica_config(nome_libro):
    _assicura_radice_nel_path()
    mod = importlib.import_module(f"libri.{nome_libro}.config")
    return {
        "TITOLO":      getattr(mod, "TITOLO", "Senza titolo"),
        "SOTTOTITOLO": getattr(mod, "SOTTOTITOLO", ""),
        "AUTORE":      getattr(mod, "AUTORE", ""),
        "ANNO":        getattr(mod, "ANNO", ""),
        "NOME_FILE":   getattr(mod, "NOME_FILE", "libro.pdf"),
    }


def _carica_capitoli(nome_libro):
    _assicura_radice_nel_path()
    package_capitoli = f"libri.{nome_libro}.capitoli"
    cartella_capitoli = RADICE_PROGETTO / "libri" / nome_libro / "capitoli"
    return scopri_capitoli(package_capitoli, cartella_capitoli)


def _carica_disegnatore_copertina(nome_libro, meta):
    _assicura_radice_nel_path()
    try:
        mod = importlib.import_module(f"libri.{nome_libro}.copertina")
        if hasattr(mod, "crea_disegnatore_copertina"):
            return mod.crea_disegnatore_copertina(meta)
    except ModuleNotFoundError:
        pass
    from motore.copertina import crea_disegnatore_copertina
    return crea_disegnatore_copertina(meta)


# ======================================================================
# DocTemplate personalizzato
# ======================================================================

class LibroDocTemplate(BaseDocTemplate):
    """
    DocTemplate personalizzato che:
    - registra un bookmark PDF per ciascun titolo;
    - notifica le voci di indice (TOCEntry);
    - aggiunge voci all'outline PDF (segnalibri).
    """

    _STILI_TITOLO = {
        "Capitolo":      0,
        "Paragrafo":     1,
        "Sottoparagrafo": 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._chiavi_per_flowable = {}
        self._contatore_chiavi = 0

    def _chiave_per(self, flowable):
        fid = id(flowable)
        if fid not in self._chiavi_per_flowable:
            self._contatore_chiavi += 1
            self._chiavi_per_flowable[fid] = f"toc_{self._contatore_chiavi}"
        return self._chiavi_per_flowable[fid]

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style = flowable.style.name
        if style not in self._STILI_TITOLO:
            return

        livello = self._STILI_TITOLO[style]
        testo = fix_simboli(flowable.getPlainText())
        chiave = self._chiave_per(flowable)

        self.canv.bookmarkPage(chiave)
        self.notify("TOCEntry", (livello, testo, self.page, chiave))

        if livello <= 1:
            self.canv.addOutlineEntry(testo, chiave,
                                      level=livello, closed=False)


# ======================================================================
# Callback di pagina
# ======================================================================

def _crea_callback_pagina(titolo_libro, sottotitolo_libro):
    def pagina_contenuto(canvas, doc):
        canvas.saveState()
        w, h = A4

        canvas.setStrokeColor(HexColor("#CCCCCC"))
        canvas.setLineWidth(0.5)
        canvas.line(2 * cm, h - 1.8 * cm, w - 2 * cm, h - 1.8 * cm)
        canvas.setFont(nome_font("LibroItalic"), 9)
        canvas.setFillColor(HexColor("#666666"))
        canvas.drawString(2 * cm, h - 1.5 * cm, titolo_libro)
        canvas.drawRightString(w - 2 * cm, h - 1.5 * cm, sottotitolo_libro)

        canvas.line(2 * cm, 1.8 * cm, w - 2 * cm, 1.8 * cm)
        canvas.setFont(nome_font("LibroRegular"), 9)
        canvas.setFillColor(HexColor("#666666"))
        canvas.drawCentredString(w / 2, 1.3 * cm, str(doc.page))

        canvas.restoreState()

    return pagina_contenuto


# ======================================================================
# Placeholder per capitoli che esplodono
# ======================================================================

def _placeholder_capitolo(nome_cap: str, eccezione, tb: str):
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Table, TableStyle

    stile = ParagraphStyle(
        name="ErroreCapitolo",
        fontName=nome_font("LibroMono"), fontSize=8.5, leading=11,
        textColor=HexColor("#7B241C"),
    )
    testo = (
        f"<b>Errore nel {nome_cap}</b><br/>"
        f"{eccezione}<br/><br/>"
        f'<font size="7" color="#888888">{tb[:400]}</font>'
    )
    par = Paragraph(testo, stile)
    tab = Table([[par]], colWidths=[17 * cm])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FDECEA")),
        ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#C0392B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [Spacer(1, 6), tab, Spacer(1, 10)]


# ======================================================================
# Costruzione libro
# ======================================================================

def costruisci_libro(nome_libro, percorso_output=None, report=None):
    """
    Costruisce il PDF del libro.

    Parametri
    ---------
    nome_libro : str
    percorso_output : Path | None
    report : BuildReport | None
    """
    registra_font()
    _mod_immagini.set_libro_corrente(nome_libro)
    _mod_formule.set_libro_corrente(nome_libro)
    _mod_grafici.set_libro_corrente(nome_libro)
    _mod_diagrammi.set_libro_corrente(nome_libro)

    cartella_libro = RADICE_PROGETTO / "libri" / nome_libro
    if not cartella_libro.exists():
        raise FileNotFoundError(f"Libro non trovato: {cartella_libro}")

    meta = _carica_config(nome_libro)
    capitoli = _carica_capitoli(nome_libro)

    if percorso_output is None:
        percorso_output = cartella_libro / meta["NOME_FILE"]
    percorso_output = Path(percorso_output)

    print(f"[build] {nome_libro} -> {percorso_output}")

    doc = LibroDocTemplate(
        str(percorso_output),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.5 * cm, bottomMargin=2.2 * cm,
        title=meta["TITOLO"],
        author=meta["AUTORE"],
        subject=meta["SOTTOTITOLO"],
    )

    frame_cover = Frame(
        0, 0, A4[0], A4[1], id="cover_frame",
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )
    frame_content = Frame(
        2 * cm, 2.2 * cm,
        A4[0] - 4 * cm,
        A4[1] - 2.5 * cm - 2.2 * cm,
        id="content_frame",
    )

    doc.addPageTemplates([
        PageTemplate(id="cover",
                     frames=[frame_cover],
                     onPage=_carica_disegnatore_copertina(nome_libro, meta)),
        PageTemplate(id="content",
                     frames=[frame_content],
                     onPage=_crea_callback_pagina(meta["TITOLO"],
                                                  meta["SOTTOTITOLO"])),
    ])

    story = []
    story.append(NextPageTemplate("content"))
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    story.append(Paragraph("Indice", stile_titolo_indice()))
    story.append(crea_indice())
    story.append(PageBreak())

    for i, capitolo in enumerate(capitoli, start=1):
        nome_cap = f"Capitolo {i:02d}"

        try:
            flowables_cap = capitolo.story()
        except Exception as e:
            tb = traceback.format_exc()
            if report is not None:
                report.errore(
                    origine="paragrafo",
                    contesto=nome_cap,
                    messaggio=f"story() esplode: {e}",
                    dettaglio=tb,
                )
            story.extend(_placeholder_capitolo(nome_cap, e, tb))
            story.append(PageBreak())
            if report is not None:
                report.n_paragrafi_falliti += 1
            continue

        if not isinstance(flowables_cap, list):
            msg = (f"story() ha restituito {type(flowables_cap).__name__} "
                   f"invece di una lista")
            if report is not None:
                report.errore(
                    origine="paragrafo",
                    contesto=nome_cap,
                    messaggio=msg,
                )
            story.append(Paragraph(msg, STILI["Testo"]))
            story.append(PageBreak())
            continue

        story.extend(flowables_cap)
        story.append(PageBreak())

        if report is not None:
            report.n_paragrafi_ok += 1

    if report is None:
        doc.multiBuild(story)
    else:
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        build_error = None

        with contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            try:
                doc.multiBuild(story)
            except Exception as e:
                build_error = e
                tb = traceback.format_exc()
                report.errore(
                    origine="sistema",
                    contesto="multiBuild",
                    messaggio=str(e),
                    dettaglio=tb,
                )

        for buf in (stdout_buf, stderr_buf):
            for riga in buf.getvalue().splitlines():
                riga = riga.strip()
                if not riga:
                    continue
                if riga.startswith("[WARN]"):
                    report.warn(
                        origine="motore",
                        contesto="build",
                        messaggio=riga,
                    )
                elif riga.startswith("[ERR]") or riga.startswith("[errore]"):
                    report.errore(
                        origine="motore",
                        contesto="build",
                        messaggio=riga,
                    )

        if build_error is not None:
            raise

    print(f"[ok] PDF generato: {percorso_output}")
    return percorso_output