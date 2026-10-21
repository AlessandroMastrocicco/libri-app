# -*- coding: utf-8 -*-
"""
pdf_viewer.py - Widget per visualizzare un PDF in CustomTkinter.

Comportamento:
- di default: auto-fit alla larghezza disponibile (le pagine riempiono
  lo spazio orizzontale, con margini);
- i pulsanti + / - passano in modalita' manuale;
- il pulsante "Fit" torna in auto-fit;
- ad ogni resize del viewer (in auto-fit) la larghezza viene ricalcolata;
- le pagine sono centrate con un bordo leggero e spazio verticale.

Dipende da:
    pip install pymupdf pillow
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

import customtkinter as ctk

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from app.ui import tema


class PdfViewer(ctk.CTkFrame):
    """
    Visualizzatore PDF basato su PyMuPDF con auto-fit alla larghezza.

    API pubblica:
        carica(path)
        svuota()
        zoom_in() / zoom_out() / zoom_fit()
        vai_a_pagina(n)      # 1-based
        pagina_corrente() -> int
        n_pagine() -> int
    """

    ZOOM_MIN = 0.30
    ZOOM_MAX = 4.00
    ZOOM_STEP = 0.15

    PADDING_X = 40          # padding orizzontale totale (lato sx + dx)
    PADDING_SCROLLBAR = 20  # spazio per la scrollbar verticale
    SPAZIO_PAGINE = 14      # spazio verticale tra una pagina e la successiva
    DEBOUNCE_MS = 200       # debounce per il resize

    def __init__(self, parent, larghezza_utile: int = 700):
        super().__init__(parent, fg_color="transparent")

        self._doc = None
        self._path: Path | None = None
        self._zoom = 1.0
        self._zoom_auto = True      # default: fit alla larghezza
        self._photos: list = []
        self._labels: list = []
        self._render_job = None     # debounce resize
        self._auto_zoom_job = None  # tentativi auto-zoom post-load

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_canvas()

        # ascolta i resize del canvas (per auto-fit)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color=tema.BG_INPUT, corner_radius=8)
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        bar.grid_columnconfigure(4, weight=1)

        ctk.CTkButton(
            bar, text="-", width=34, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.zoom_out,
        ).grid(row=0, column=0, padx=(8, 2), pady=6)

        self.btn_zoom = ctk.CTkButton(
            bar, text="100%", width=80, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.zoom_fit,
        )
        self.btn_zoom.grid(row=0, column=1, padx=2, pady=6)

        ctk.CTkButton(
            bar, text="+", width=34, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.zoom_in,
        ).grid(row=0, column=2, padx=2, pady=6)

        ctk.CTkButton(
            bar, text="Fit", width=60, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.zoom_fit,
        ).grid(row=0, column=3, padx=(8, 2), pady=6)

        self.lbl_pagina = ctk.CTkLabel(
            bar, text="pagina - / -",
            text_color=tema.TESTO_TENUE,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.lbl_pagina.grid(row=0, column=4, sticky="w", padx=(16, 0))

        ctk.CTkButton(
            bar, text="<", width=34, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._pagina_prec,
        ).grid(row=0, column=5, padx=2, pady=6)

        ctk.CTkButton(
            bar, text=">", width=34, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._pagina_succ,
        ).grid(row=0, column=6, padx=(2, 8), pady=6)

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------

    def _build_canvas(self):
        wrap = ctk.CTkFrame(self, corner_radius=8, fg_color=tema.BG_INPUT)
        wrap.grid(row=1, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            wrap, bg=tema.BG_APP, highlightthickness=0, bd=0,
        )
        self.scroll_y = tk.Scrollbar(
            wrap, orient="vertical", command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scroll_y.grid(row=0, column=1, sticky="ns")

        # frame interno dove impilo le pagine
        self.inner = tk.Frame(self.canvas, bg=tema.BG_APP)
        self._inner_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw",
        )

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            ),
        )

        # scroll col mouse: attivo solo quando il mouse e' sopra il canvas
        self.canvas.bind("<Enter>", self._abilita_mousewheel)
        self.canvas.bind("<Leave>", self._disabilita_mousewheel)

        # messaggio iniziale
        self.lbl_vuoto = tk.Label(
            self.inner,
            text="(nessun PDF caricato)",
            bg=tema.BG_APP, fg=tema.TESTO_MOLTO_TENUE,
            font=("Segoe UI", 12),
            padx=40, pady=40,
        )
        self.lbl_vuoto.pack(anchor="nw")

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def carica(self, path: Path):
        if not _HAS_FITZ:
            self._mostra_messaggio(
                "PyMuPDF non installato.\nEsegui:  pip install pymupdf"
            )
            return
        if not _HAS_PIL:
            self._mostra_messaggio(
                "Pillow non installato.\nEsegui:  pip install pillow"
            )
            return

        path = Path(path)
        if not path.exists():
            self._mostra_messaggio(f"File non trovato: {path}")
            return

        self.svuota()
        self._path = path
        try:
            self._doc = fitz.open(str(path))
        except Exception as e:
            self._mostra_messaggio(f"Errore aprendo il PDF: {e}")
            return

        # ogni nuovo PDF riparte in auto-fit
        self._zoom_auto = True
        self._zoom = 1.0

        # render iniziale a zoom 1.0; poi, appena il widget ha la sua
        # larghezza, applica l'auto-fit e ri-renderizza
        self._renderizza_tutte()
        self._aggiorna_label_pagina()
        self._tenta_auto_zoom()

    def svuota(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self._photos.clear()
        self._labels.clear()
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
        self._doc = None
        self._path = None
        self.canvas.yview_moveto(0)
        self.lbl_pagina.configure(text="pagina - / -")
        self._aggiorna_label_zoom()

    def zoom_in(self):
        if self._doc is None:
            return
        self._zoom_auto = False
        self._zoom = min(self.ZOOM_MAX, self._zoom + self.ZOOM_STEP)
        self._renderizza_tutte()
        self._aggiorna_label_pagina()
        self._aggiorna_label_zoom()

    def zoom_out(self):
        if self._doc is None:
            return
        self._zoom_auto = False
        self._zoom = max(self.ZOOM_MIN, self._zoom - self.ZOOM_STEP)
        self._renderizza_tutte()
        self._aggiorna_label_pagina()
        self._aggiorna_label_zoom()

    def zoom_fit(self):
        """Torna in auto-fit alla larghezza."""
        if self._doc is None:
            return
        self._zoom_auto = True
        self._applica_auto_zoom()

    def vai_a_pagina(self, n: int):
        if self._doc is None:
            return
        n = max(1, min(n, len(self._doc)))
        try:
            self.canvas.update_idletasks()
            frazione = (n - 1) / max(1, len(self._doc))
            self.canvas.yview_moveto(frazione)
        except Exception:
            pass
        self._aggiorna_label_pagina()

    def n_pagine(self) -> int:
        return len(self._doc) if self._doc is not None else 0

    def pagina_corrente(self) -> int:
        if self._doc is None:
            return 0
        try:
            self.canvas.update_idletasks()
            y = self.canvas.canvasy(0)
            bbox = self.canvas.bbox("all")
            totale = bbox[3] if bbox else 1
            frazione = y / max(1, totale)
            return max(1, int(frazione * len(self._doc)) + 1)
        except Exception:
            return 1

    # ------------------------------------------------------------------
    # Auto-zoom
    # ------------------------------------------------------------------

    def _tenta_auto_zoom(self, tentativi: int = 10):
        """Aspetta che il canvas abbia una larghezza sensata, poi applica fit."""
        if self._doc is None or not self._zoom_auto:
            return
        try:
            w = self.canvas.winfo_width()
        except Exception:
            w = 0
        if w < 100 and tentativi > 0:
            self._auto_zoom_job = self.after(
                80, lambda: self._tenta_auto_zoom(tentativi - 1)
            )
            return
        self._applica_auto_zoom()

    def _calcola_zoom_fit(self) -> float:
        """Calcola lo zoom per far entrare la prima pagina nella larghezza."""
        if self._doc is None or len(self._doc) == 0:
            return self._zoom
        try:
            w_disponibile = self.canvas.winfo_width()
        except Exception:
            return self._zoom

        w_disponibile -= self.PADDING_SCROLLBAR
        w_disponibile -= self.PADDING_X
        if w_disponibile < 100:
            return self._zoom

        try:
            page = self._doc[0]
            larghezza_pagina_punti = page.rect.width  # punti PDF (72 dpi)
        except Exception:
            return self._zoom
        if larghezza_pagina_punti <= 0:
            return self._zoom

        zoom = w_disponibile / larghezza_pagina_punti
        return max(self.ZOOM_MIN, min(self.ZOOM_MAX, zoom))

    def _applica_auto_zoom(self):
        if self._doc is None or not self._zoom_auto:
            return
        nuovo = self._calcola_zoom_fit()
        # arrotonda a 0.01 per evitare micro-render inutili
        nuovo = round(nuovo, 2)
        if abs(nuovo - self._zoom) < 0.005:
            self._aggiorna_label_zoom()
            return
        self._zoom = nuovo
        self._renderizza_tutte()
        self._aggiorna_label_pagina()
        self._aggiorna_label_zoom()

    def _on_canvas_resize(self, event=None):
        if self._doc is None or not self._zoom_auto:
            return
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
        self._render_job = self.after(
            self.DEBOUNCE_MS, self._applica_auto_zoom
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _renderizza_tutte(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self._photos.clear()
        self._labels.clear()

        if self._doc is None:
            return

        mat = fitz.Matrix(self._zoom, self._zoom)

        for i, page in enumerate(self._doc):
            try:
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes(
                    "RGB", (pix.width, pix.height), pix.samples
                )
                photo = ImageTk.PhotoImage(img)
                self._photos.append(photo)

                # bordo attorno alla pagina per staccarla dallo sfondo
                lbl = tk.Label(
                    self.inner, image=photo,
                    bg="#e6e6e6", bd=1, relief="solid",
                    highlightthickness=0,
                )
                lbl.pack(anchor="center",
                         pady=(self.SPAZIO_PAGINE // 2,
                               self.SPAZIO_PAGINE // 2))
                self._labels.append(lbl)
            except Exception as e:
                tk.Label(
                    self.inner,
                    text=f"[errore pagina {i+1}: {e}]",
                    bg=tema.BG_APP, fg=tema.ERRORE,
                    font=("Segoe UI", 10),
                    padx=20, pady=20,
                ).pack(anchor="center")

        # allinea l'inner frame alla larghezza del canvas per il centraggio
        self.canvas.update_idletasks()
        try:
            larghezza_canvas = self.canvas.winfo_width()
            self.canvas.itemconfigure(
                self._inner_id, width=larghezza_canvas
            )
        except Exception:
            pass

        self.canvas.yview_moveto(0)

    def _mostra_messaggio(self, testo: str):
        for w in self.inner.winfo_children():
            w.destroy()
        tk.Label(
            self.inner, text=testo,
            bg=tema.BG_APP, fg=tema.TESTO_TENUE,
            font=("Segoe UI", 11),
            padx=40, pady=40, justify="left",
        ).pack(anchor="nw")

    # ------------------------------------------------------------------
    # Label di stato
    # ------------------------------------------------------------------

    def _aggiorna_label_pagina(self):
        if self._doc is None:
            self.lbl_pagina.configure(text="pagina - / -")
            return
        curr = self.pagina_corrente()
        tot = len(self._doc)
        self.lbl_pagina.configure(text=f"pagina {curr} / {tot}")

    def _aggiorna_label_zoom(self):
        pct = int(round(self._zoom * 100))
        if self._zoom_auto:
            self.btn_zoom.configure(text=f"{pct}% · Fit")
        else:
            self.btn_zoom.configure(text=f"{pct}%")

    # ------------------------------------------------------------------
    # Navigazione pagine
    # ------------------------------------------------------------------

    def _pagina_prec(self):
        self.vai_a_pagina(self.pagina_corrente() - 1)

    def _pagina_succ(self):
        self.vai_a_pagina(self.pagina_corrente() + 1)

    # ------------------------------------------------------------------
    # Mouse wheel
    # ------------------------------------------------------------------

    def _abilita_mousewheel(self, event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _disabilita_mousewheel(self, event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except Exception:
            pass