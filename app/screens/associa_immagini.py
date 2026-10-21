# -*- coding: utf-8 -*-
"""
associa_immagini.py - Popup di associazione immagini mancanti.

Mostra le immagini referenziate dal codice di un paragrafo ma non
ancora presenti sul filesystem. Per ciascuna, l'utente puo':
- scegliere un'immagine gia' presente nel libro;
- scegliere un file esterno tramite file dialog;
- catturare una regione da una slide di una dispensa estratta
  (visualizzatore con navigazione e ritaglio rettangolare);
- farsi proporre un match automatico (stesso nome file).

Il dialog di cattura e' volutamente implementato in Tk puro
(tk.Toplevel + tk.Canvas + ImageTk.PhotoImage) perche' le CTkToplevel
figlie di altre CTkToplevel non renderizzano immagini su Windows.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from app.ui import tema
from app.ui.widgets import (
    bottone_primario,
    bottone_secondario,
    card,
)
from app.core.paragrafo import (
    associa_immagine,
    elenca_immagini_disponibili,
    estrai_immagini_referenziate,
    immagini_mancanti,
    percorso_immagini_capitolo,
    salva_immagine_da_pil,
)
from app.core.slide_extract import (
    carica_pagine,
    elenca_estratti,
)


class PopupAssociaImmagini(ctk.CTkToplevel):
    """Popup modale per associare le immagini mancanti di un paragrafo."""

    def __init__(self, parent, root_progetto: Path, slug: str,
                 cap: int, contenuto: str,
                 on_completato=None):
        super().__init__(parent)

        self.root_progetto = root_progetto
        self.slug = slug
        self.cap = cap
        self.contenuto = contenuto
        self.on_completato = on_completato
        self.risultato = False

        self.referenziate = estrai_immagini_referenziate(contenuto)
        self.mancanti = immagini_mancanti(
            root_progetto, slug, cap, contenuto
        )
        self.disponibili = elenca_immagini_disponibili(
            root_progetto, slug
        )
        self.associazioni: dict[str, Path] = {}
        self._widgets: dict[str, dict] = {}

        self._build_ui()
        self._popola()

        self.title("Associa immagini")
        self.geometry("980x740")
        self.minsize(800, 580)
        self.configure(fg_color=tema.BG_APP)

        try:
            self.transient(parent)
        except Exception:
            pass

        self._centra_su_parent(parent)

        try:
            self.grab_set()
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self._annulla())

        self.after(80, self.lift)
        self.after(80, self.focus_force)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)

        n = len(self.mancanti)
        etichetta = (
            f"Associa {n} immagine mancante"
            if n == 1 else
            f"Associa {n} immagini mancanti"
        )

        ctk.CTkLabel(
            header,
            text=etichetta,
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text="Il codice del paragrafo referenzia queste immagini "
                 "che non sono ancora presenti nella cartella del "
                 "capitolo. Per ciascuna, scegli un file dal libro, "
                 "dal disco, oppure ritaglia una regione da una "
                 "dispensa di slide estratta.",
            font=ctk.CTkFont(size=12),
            anchor="w", justify="left",
            text_color=tema.TESTO_TENUE,
            wraplength=900,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))

        self.scroll = ctk.CTkScrollableFrame(
            self, corner_radius=8, fg_color=tema.BG_INPUT,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew",
                          padx=18, pady=(0, 8))
        self.scroll.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_stato = ctk.CTkLabel(
            footer, text="",
            font=ctk.CTkFont(size=12),
            text_color=tema.TESTO_TENUE,
            anchor="w", justify="left", wraplength=500,
        )
        self.lbl_stato.grid(row=0, column=0, sticky="w")

        bottone_secondario(
            footer, "  Apri cartella capitolo",
            command=self._apri_cartella_capitolo,
            width=210, height=36,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        bottone_secondario(
            footer, "  Annulla",
            command=self._annulla,
            width=120, height=36,
        ).grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.btn_conferma = bottone_primario(
            footer, "  Conferma e chiudi",
            command=self._conferma,
            width=200, height=36,
            state="disabled",
        )
        self.btn_conferma.grid(row=0, column=3, sticky="e", padx=(8, 0))

    def _popola(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._widgets.clear()

        if not self.mancanti:
            ctk.CTkLabel(
                self.scroll,
                text="(nessuna immagine mancante)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=13),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=20)
            self._aggiorna_conferma()
            return

        auto = self._auto_match()
        for i, ref in enumerate(self.mancanti):
            self._card_immagine(i, ref, preselezione=auto.get(ref["nome"]))
        self._aggiorna_conferma()

    def _auto_match(self) -> dict[str, Path]:
        out: dict[str, Path] = {}
        per_nome: dict[str, Path] = {}
        for p in self.disponibili:
            per_nome.setdefault(p.name.lower(), p)
            per_nome.setdefault(p.stem.lower(), p)

        for ref in self.mancanti:
            nome = ref["nome"]
            chiave_nome = Path(nome).name.lower()
            chiave_stem = Path(nome).stem.lower()
            trovato = per_nome.get(chiave_nome) or per_nome.get(chiave_stem)
            if trovato is not None:
                out[nome] = trovato
        return out

    def _card_immagine(self, indice: int, ref: dict,
                       preselezione: Path | None = None):
        nome = ref["nome"]
        riga = ref.get("riga", "?")

        card_i = ctk.CTkFrame(
            self.scroll, corner_radius=10,
            fg_color=tema.BG_CARD,
            border_width=1, border_color=tema.ERRORE,
        )
        card_i.grid(row=indice, column=0, sticky="ew", pady=6)
        card_i.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_i, text="Referenziata:",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w", text_color=tema.TESTO_MOLTO_TENUE,
        ).grid(row=0, column=0, sticky="w", padx=(14, 4), pady=(12, 0))

        ctk.CTkLabel(
            card_i, text=nome,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            anchor="w", text_color=tema.ERRORE,
        ).grid(row=1, column=0, sticky="w", padx=(14, 4), pady=(0, 12))

        azioni = ctk.CTkFrame(card_i, fg_color="transparent")
        azioni.grid(row=0, column=1, rowspan=2, sticky="ew",
                     padx=(8, 14), pady=10)
        azioni.grid_columnconfigure(0, weight=1)

        lbl_stato = ctk.CTkLabel(
            azioni, text="(non associata)",
            font=ctk.CTkFont(size=12),
            anchor="w", text_color=tema.TESTO_MOLTO_TENUE,
        )
        lbl_stato.grid(row=0, column=0, sticky="w", pady=(0, 6))

        btns = ctk.CTkFrame(azioni, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            btns, text="  Dal libro…",
            width=130, height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda n=nome: self._scegli_dal_libro(n),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btns, text="  Sfoglia file…",
            width=140, height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda n=nome: self._scegli_da_disco(n),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btns, text="  Cattura da dispensa…",
            width=190, height=32,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda n=nome: self._cattura_da_dispensa(n),
        ).pack(side="left", padx=(0, 6))

        thumb_wrap = ctk.CTkFrame(
            card_i, fg_color=tema.BG_INPUT,
            corner_radius=6, width=130, height=95,
        )
        thumb_wrap.grid(row=0, column=2, rowspan=2, sticky="e",
                         padx=(0, 14), pady=10)
        thumb_wrap.grid_propagate(False)

        lbl_thumb = ctk.CTkLabel(thumb_wrap, text="anteprima",
                                 text_color=tema.TESTO_MOLTO_TENUE,
                                 font=ctk.CTkFont(size=10))
        lbl_thumb.place(relx=0.5, rely=0.5, anchor="center")

        self._widgets[nome] = {
            "card": card_i,
            "lbl_stato": lbl_stato,
            "lbl_thumb": lbl_thumb,
            "thumb_wrap": thumb_wrap,
            "riga": riga,
        }

        if preselezione is not None:
            self._applica_associazione(nome, preselezione, salva=False)

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _scegli_dal_libro(self, nome_ref: str):
        if not self.disponibili:
            messagebox.showinfo(
                "Nessuna immagine disponibile",
                "Il libro non contiene immagini salvate in "
                "libri/<slug>/immagini/, slide_estratte/ o catture/.\n\n"
                "Cattura prima una regione da una dispensa, oppure "
                "usa «Sfoglia file…».",
                parent=self,
            )
            return
        SelettoreImmagine(
            self,
            self.disponibili,
            titolo=f"Scegli immagine per {nome_ref}",
            on_scelta=lambda p: self._applica_associazione(nome_ref, p),
        )

    def _scegli_da_disco(self, nome_ref: str):
        default = self._cartella_immagini_libro()
        percorso = filedialog.askopenfilename(
            parent=self,
            title=f"Scegli immagine per {nome_ref}",
            initialdir=str(default) if default.is_dir() else None,
            filetypes=[
                ("Immagini", "*.png *.jpg *.jpeg *.gif *.bmp"),
                ("Tutti i file", "*.*"),
            ],
        )
        if not percorso:
            return
        self._applica_associazione(nome_ref, Path(percorso))

    def _cattura_da_dispensa(self, nome_ref: str):
        if not _HAS_PIL:
            messagebox.showerror(
                "Cattura non disponibile",
                "Pillow non installato. Esegui: pip install pillow",
                parent=self,
            )
            return

        dispense = elenca_estratti(self.root_progetto, self.slug)
        if not dispense:
            messagebox.showinfo(
                "Nessuna dispensa",
                "Non ci sono dispense estratte per questo libro.\n\n"
                "Usa «Estrattore slide» dal libro per estrarre un PDF, "
                "oppure usa «Sfoglia file…» per selezionare un file "
                "esterno.",
                parent=self,
            )
            return

        dialog = DialogCatturaDaDispensa(
            self,
            root_progetto=self.root_progetto,
            slug=self.slug,
            nome_ref=nome_ref,
            dispense=dispense,
            on_conferma=lambda img: self._salva_ritaglio(nome_ref, img),
        )
        self.wait_window(dialog)

    def _salva_ritaglio(self, nome_ref: str, image_pil):
        res = salva_immagine_da_pil(
            self.root_progetto, self.slug, self.cap,
            nome_ref, image_pil,
        )
        if not res["ok"]:
            messagebox.showerror(
                "Errore salvataggio",
                res["errore"] or "Errore sconosciuto.",
                parent=self,
            )
            return
        self.associazioni[nome_ref] = res["path"]
        w = self._widgets.get(nome_ref)
        if w:
            w["card"].configure(border_color=tema.SUCCESSO)
            w["lbl_stato"].configure(
                text=f"Salvata come: {res['path'].name}",
                text_color=tema.SUCCESSO,
            )
            self._aggiorna_thumbnail(w, res["path"])
        self._aggiorna_conferma()

    def _applica_associazione(self, nome_ref: str,
                              path_sorgente: Path,
                              salva: bool = True):
        if salva:
            res = associa_immagine(
                self.root_progetto, self.slug, self.cap,
                nome_ref, path_sorgente,
            )
            if not res["ok"]:
                messagebox.showerror(
                    "Errore associazione",
                    res["errore"] or "Errore sconosciuto.",
                    parent=self,
                )
                return
            self.associazioni[nome_ref] = Path(path_sorgente)
        else:
            self.associazioni[nome_ref] = Path(path_sorgente)

        w = self._widgets.get(nome_ref)
        if w:
            w["card"].configure(border_color=tema.SUCCESSO)
            w["lbl_stato"].configure(
                text=f"Associata a: {Path(path_sorgente).name}",
                text_color=tema.SUCCESSO,
            )
            self._aggiorna_thumbnail(w, path_sorgente)

        self._aggiorna_conferma()

    def _aggiorna_thumbnail(self, w: dict, path: Path):
        if not _HAS_PIL:
            w["lbl_thumb"].configure(text=Path(path).name)
            return
        try:
            img = Image.open(str(path))
            img.thumbnail((120, 85), Image.LANCZOS)
            ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img,
                size=(img.width, img.height),
            )
            w["lbl_thumb"].configure(image=ctk_img, text="")
            w["lbl_thumb"].image = ctk_img
        except Exception:
            w["lbl_thumb"].configure(text="(anteprima n/d)")

    def _aggiorna_conferma(self):
        tutte = all(
            ref["nome"] in self.associazioni for ref in self.mancanti
        )
        if not self.mancanti:
            tutte = True

        self.btn_conferma.configure(
            state="normal" if tutte else "disabled"
        )

        n_ok = sum(
            1 for ref in self.mancanti
            if ref["nome"] in self.associazioni
        )
        n_tot = len(self.mancanti)

        if n_tot == 0:
            self.lbl_stato.configure(
                text="Tutte le immagini sono presenti.",
                text_color=tema.SUCCESSO,
            )
        elif n_ok == n_tot:
            self.lbl_stato.configure(
                text=f"Tutte le {n_tot} immagini sono associate. "
                     f"Puoi confermare.",
                text_color=tema.SUCCESSO,
            )
        else:
            self.lbl_stato.configure(
                text=f"{n_ok} / {n_tot} immagini associate. "
                     f"Completa per confermare.",
                text_color=tema.AVVISO,
            )

    def _conferma(self):
        tutte = all(
            ref["nome"] in self.associazioni for ref in self.mancanti
        )
        if self.mancanti and not tutte:
            mancanti = [
                ref["nome"] for ref in self.mancanti
                if ref["nome"] not in self.associazioni
            ]
            messagebox.showwarning(
                "Associazione incompleta",
                "Mancano le associazioni per:\n\n  - "
                + "\n  - ".join(mancanti),
                parent=self,
            )
            return

        self.risultato = True
        cb = self.on_completato
        self.destroy()
        if cb is not None:
            try:
                cb()
            except Exception:
                pass

    def _annulla(self):
        self.risultato = False
        self.destroy()

    def _cartella_immagini_libro(self) -> Path:
        return (Path(self.root_progetto) / "libri" / self.slug
                / "immagini")

    def _apri_cartella_capitolo(self):
        c = percorso_immagini_capitolo(
            self.root_progetto, self.slug, self.cap
        )
        try:
            c.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        self._apri(c)

    def _apri(self, percorso: Path):
        if not percorso or not percorso.exists():
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(percorso))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(percorso)], check=False)
            else:
                subprocess.run(["xdg-open", str(percorso)], check=False)
        except Exception:
            pass

    def _centra_su_parent(self, parent):
        try:
            self.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass


# ======================================================================
# Dialog: cattura regione da una dispensa (Tk PURO)
# ======================================================================

class DialogCatturaDaDispensa(tk.Toplevel):
    """
    Visualizzatore di slide estratte con selezione rettangolare,
    implementato in Tk puro per garantire il rendering delle immagini
    dentro una finestra modale figlia di una CTkToplevel.

    Layout:
        - in alto: menu a tendina per scegliere la dispensa;
        - al centro: tk.Canvas con la pagina corrente;
        - sotto: pulsanti di navigazione + slider;
        - in basso: pulsanti azzera / annulla / applica.

    Il rettangolo di selezione e' disegnato dal tk.Canvas come
    elemento grafico sopra l'immagine.
    """

    # Colori (coerenti col tema scuro dell'app)
    BG = "#1a1a1a"
    BG_CARD = "#242424"
    BG_INPUT = "#2b2b2b"
    FG = "#e8e8e8"
    FG_TENUE = "#b0b0b0"
    NEUTRO = "#3a3a3a"
    NEUTRO_HOVER = "#4a4a4a"
    PRIMARIO = "#3fa34d"
    PRIMARIO_HOVER = "#2e7d3a"
    ACCENTO = "#00d4ff"

    def __init__(self, parent, root_progetto: Path, slug: str,
                 nome_ref: str, dispense: list[dict],
                 on_conferma):
        super().__init__(parent)

        self.root_progetto = root_progetto
        self.slug = slug
        self.nome_ref = nome_ref
        self.dispense = list(dispense)
        self.on_conferma = on_conferma

        self._idx_dispensa = 0
        self._pagine: list[Path] = []
        self._idx_pagina = 0

        self._img_originale = None       # PIL
        self._photo = None               # PhotoImage Tk
        self._canvas_img_id = None       # id immagine nel canvas
        self._rect_id = None             # id rettangolo di selezione

        self._scala = 1.0
        self._offset_x = 0
        self._offset_y = 0

        self._sel = None                 # (x0,y0,x1,y1) in coord immagine
        self._drag_start = None
        self._slider_busy = False
        self._resize_job = None

        self.title(f"Cattura da dispensa — {nome_ref}")
        self.geometry("1060x820")
        self.minsize(820, 640)
        self.configure(bg=self.BG)

        try:
            self.transient(parent)
        except Exception:
            pass

        self._build_ui()
        self._centra_su_parent(parent)

        try:
            self.grab_set()
        except Exception:
            pass

        self.bind("<Escape>", lambda e: self.destroy())

        self.after(80, self.lift)
        self.after(80, self.focus_force)
        self.after(150, self._carica_dispensa_corrente)

    # ------------------------------------------------------------------
    # UI (Tk puro)
    # ------------------------------------------------------------------

    def _build_ui(self):
        # -------- Header: selezione dispensa --------
        header = tk.Frame(self, bg=self.BG_CARD, padx=12, pady=10)
        header.pack(side="top", fill="x", padx=12, pady=(12, 6))

        tk.Label(
            header, text="Dispensa:",
            bg=self.BG_CARD, fg=self.FG,
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=(0, 8))

        valori = [d["dispensa"] for d in self.dispense]
        self._var_dispensa = tk.StringVar(value=valori[0] if valori else "")
        if valori:
            self._menu_dispensa = tk.OptionMenu(
                header, self._var_dispensa, *valori,
                command=self._on_cambia_dispensa,
            )
            self._menu_dispensa.configure(
                bg=self.BG_INPUT, fg=self.FG,
                activebackground=self.NEUTRO_HOVER,
                activeforeground=self.FG,
                highlightthickness=0, bd=0, padx=10,
                font=("Segoe UI", 11),
            )
            self._menu_dispensa["menu"].configure(
                bg=self.BG_INPUT, fg=self.FG,
                activebackground=self.PRIMARIO,
                activeforeground="white",
                font=("Segoe UI", 11),
            )
            self._menu_dispensa.pack(side="left")

        self.lbl_info = tk.Label(
            header, text="",
            bg=self.BG_CARD, fg=self.FG_TENUE,
            font=("Segoe UI", 10),
        )
        self.lbl_info.pack(side="right")

        # -------- Corpo: canvas --------
        body = tk.Frame(self, bg=self.BG, bd=0)
        body.pack(side="top", fill="both", expand=True,
                  padx=12, pady=(0, 6))

        self.canvas = tk.Canvas(
            body, bg=self.BG, highlightthickness=0, bd=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # -------- Navigazione --------
        nav = tk.Frame(self, bg=self.BG, padx=4, pady=4)
        nav.pack(side="top", fill="x", padx=12, pady=(0, 6))

        self.btn_prev = tk.Button(
            nav, text="<", width=4, height=1,
            bg=self.NEUTRO, fg=self.FG,
            activebackground=self.NEUTRO_HOVER,
            activeforeground=self.FG,
            bd=0, highlightthickness=0,
            font=("Segoe UI", 11),
            command=self._prec,
        )
        self.btn_prev.pack(side="left", padx=(0, 6))

        self.lbl_pagina = tk.Label(
            nav, text="pagina - / -", width=16,
            bg=self.BG, fg=self.FG,
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_pagina.pack(side="left", padx=(0, 8))

        self.slider = tk.Scale(
            nav, from_=1, to=1, orient="horizontal",
            showvalue=False,
            bg=self.BG, fg=self.FG,
            troughcolor=self.BG_INPUT,
            activebackground=self.PRIMARIO,
            highlightthickness=0, bd=0,
            command=self._on_slider,
        )
        self.slider.pack(side="left", fill="x", expand=True, padx=8)

        self.btn_next = tk.Button(
            nav, text=">", width=4, height=1,
            bg=self.NEUTRO, fg=self.FG,
            activebackground=self.NEUTRO_HOVER,
            activeforeground=self.FG,
            bd=0, highlightthickness=0,
            font=("Segoe UI", 11),
            command=self._succ,
        )
        self.btn_next.pack(side="left", padx=(6, 0))

        # -------- Footer --------
        footer = tk.Frame(self, bg=self.BG, padx=4, pady=4)
        footer.pack(side="bottom", fill="x", padx=12, pady=(0, 12))

        self.lbl_sel = tk.Label(
            footer, text="Disegna un rettangolo sulla slide con il "
                         "mouse, poi premi «Applica ritaglio».",
            bg=self.BG, fg=self.FG_TENUE,
            font=("Segoe UI", 10), anchor="w", justify="left",
        )
        self.lbl_sel.pack(side="left")

        tk.Button(
            footer, text="Azzera selezione",
            bg=self.NEUTRO, fg=self.FG,
            activebackground=self.NEUTRO_HOVER,
            activeforeground=self.FG,
            bd=0, highlightthickness=0, padx=12, pady=6,
            font=("Segoe UI", 10),
            command=self._azzera_selezione,
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            footer, text="Annulla",
            bg=self.NEUTRO, fg=self.FG,
            activebackground=self.NEUTRO_HOVER,
            activeforeground=self.FG,
            bd=0, highlightthickness=0, padx=12, pady=6,
            font=("Segoe UI", 10),
            command=self.destroy,
        ).pack(side="right", padx=(6, 0))

        self.btn_applica = tk.Button(
            footer, text="Applica ritaglio",
            bg=self.PRIMARIO, fg="white",
            activebackground=self.PRIMARIO_HOVER,
            activeforeground="white",
            bd=0, highlightthickness=0, padx=14, pady=6,
            font=("Segoe UI", 10, "bold"),
            state="disabled",
            command=self._applica,
        )
        self.btn_applica.pack(side="right", padx=(6, 0))

    # ------------------------------------------------------------------
    # Caricamento
    # ------------------------------------------------------------------

    def _on_cambia_dispensa(self, valore: str):
        for i, d in enumerate(self.dispense):
            if d["dispensa"] == valore:
                self._idx_dispensa = i
                break
        self._carica_dispensa_corrente()

    def _carica_dispensa_corrente(self):
        if not self.dispense:
            return
        try:
            disp = self.dispense[self._idx_dispensa]
            self._pagine = carica_pagine(disp["cartella"])
        except Exception as e:
            print(f"[cattura dispensa] errore caricando dispensa: {e}")
            self._pagine = []

        self._idx_pagina = 0
        self._aggiorna_slider()
        self._carica_pagina()

    def _carica_pagina(self):
        self.canvas.delete("all")
        self._canvas_img_id = None
        self._rect_id = None
        self._sel = None
        self._drag_start = None

        if not self._pagine:
            self._img_originale = None
            self._photo = None
            self._disegna_messaggio("(nessuna pagina in questa dispensa)")
            return

        path = self._pagine[self._idx_pagina]
        try:
            img = Image.open(str(path))
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
        except Exception as e:
            print(f"[cattura dispensa] errore apertura: {e}")
            self._img_originale = None
            self._photo = None
            self._disegna_messaggio(f"Errore apertura: {e}")
            return

        self._img_originale = img
        self._ridisegna()

    def _disegna_messaggio(self, testo: str):
        self.canvas.delete("all")
        try:
            cw = max(1, self.canvas.winfo_width())
            ch = max(1, self.canvas.winfo_height())
        except Exception:
            cw, ch = 800, 400
        self.canvas.create_text(
            cw // 2, ch // 2,
            text=testo,
            fill=self.FG_TENUE,
            font=("Segoe UI", 12),
        )

    def _ridisegna(self):
        if self._img_originale is None:
            return

        try:
            self.update_idletasks()
        except Exception:
            pass

        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 2 or ch <= 2:
            self.after(60, self._ridisegna)
            return

        # Scala l'immagine per entrare nel canvas (con piccolo margine)
        cw_eff = max(1, cw - 8)
        ch_eff = max(1, ch - 8)

        img = self._img_originale
        w0, h0 = img.size
        scala = min(cw_eff / w0, ch_eff / h0, 1.0)
        dim_w = max(1, int(w0 * scala))
        dim_h = max(1, int(h0 * scala))

        mostrata = img.resize((dim_w, dim_h), Image.LANCZOS)

        self._scala = scala
        self._offset_x = (cw - dim_w) // 2
        self._offset_y = (ch - dim_h) // 2

        # Importante: master = self.winfo_toplevel() evita che Tk associ
        # l'immagine a un default root "sbagliato"
        try:
            self._photo = ImageTk.PhotoImage(mostrata, master=self)
        except Exception as e:
            print(f"[cattura dispensa] PhotoImage errore: {e}")
            return

        self.canvas.delete("all")
        self._canvas_img_id = self.canvas.create_image(
            self._offset_x, self._offset_y,
            anchor="nw", image=self._photo,
        )
        # Bordo
        self.canvas.create_rectangle(
            self._offset_x, self._offset_y,
            self._offset_x + dim_w - 1, self._offset_y + dim_h - 1,
            outline="#3a3a3a", width=1,
        )
        try:
            self.canvas.configure(scrollregion=(0, 0, cw, ch))
        except Exception:
            pass

        # Ridisegna l'eventuale rettangolo di selezione
        if self._sel is not None:
            x0, y0, x1, y1 = self._sel
            cx0 = self._offset_x + x0
            cy0 = self._offset_y + y0
            cx1 = self._offset_x + x1
            cy1 = self._offset_y + y1
            self._rect_id = self.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=self.ACCENTO, width=2,
            )

    def _on_canvas_resize(self, event=None):
        if self._img_originale is None:
            return
        if self._resize_job is not None:
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(120, self._ridisegna)

    # ------------------------------------------------------------------
    # Navigazione
    # ------------------------------------------------------------------

    def _aggiorna_slider(self):
        n = len(self._pagine)
        self._slider_busy = True
        try:
            if n <= 1:
                self.slider.configure(from_=1, to=1)
                self.slider.set(1)
            else:
                self.slider.configure(from_=1, to=n)
                self.slider.set(self._idx_pagina + 1)
        finally:
            self.after(0, lambda: setattr(self, "_slider_busy", False))

        if n:
            self.lbl_pagina.configure(
                text=f"pagina {self._idx_pagina + 1} / {n}"
            )
            self.btn_prev.configure(
                state="normal" if self._idx_pagina > 0 else "disabled"
            )
            self.btn_next.configure(
                state="normal" if self._idx_pagina < n - 1
                else "disabled"
            )
        else:
            self.lbl_pagina.configure(text="pagina - / -")
            self.btn_prev.configure(state="disabled")
            self.btn_next.configure(state="disabled")

        self.lbl_info.configure(
            text=f"{len(self.dispense)} dispense · "
                 f"{len(self._pagine)} pagine"
        )

    def _prec(self):
        if self._idx_pagina > 0:
            self._idx_pagina -= 1
            self._aggiorna_slider()
            self._carica_pagina()

    def _succ(self):
        if self._idx_pagina < len(self._pagine) - 1:
            self._idx_pagina += 1
            self._aggiorna_slider()
            self._carica_pagina()

    def _on_slider(self, valore):
        if self._slider_busy:
            return
        try:
            idx = int(round(float(valore))) - 1
        except Exception:
            return
        if not self._pagine:
            return
        idx = max(0, min(idx, len(self._pagine) - 1))
        if idx == self._idx_pagina:
            return
        self._idx_pagina = idx
        self._aggiorna_slider()
        self._carica_pagina()

    # ------------------------------------------------------------------
    # Selezione
    # ------------------------------------------------------------------

    def _limita_immagine(self, cx: float, cy: float):
        """Da coordinate canvas a coordinate immagine (clamp ai bordi)."""
        if self._img_originale is None:
            return 0, 0
        w = int(self._img_originale.width * self._scala)
        h = int(self._img_originale.height * self._scala)
        x = int(cx) - self._offset_x
        y = int(cy) - self._offset_y
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        return x, y

    def _on_press(self, event):
        if self._img_originale is None:
            return
        self._drag_start = self._limita_immagine(event.x, event.y)
        self._sel = None
        if self._rect_id is not None:
            try:
                self.canvas.delete(self._rect_id)
            except Exception:
                pass
            self._rect_id = None
        self._aggiorna_stato_selezione()

    def _on_drag(self, event):
        if self._drag_start is None or self._img_originale is None:
            return
        x0, y0 = self._drag_start
        x1, y1 = self._limita_immagine(event.x, event.y)

        rx0, rx1 = sorted((x0, x1))
        ry0, ry1 = sorted((y0, y1))

        if (rx1 - rx0) < 2 or (ry1 - ry0) < 2:
            return

        self._sel = (rx0, ry0, rx1, ry1)

        # Disegna/aggiorna il rettangolo sul canvas
        cx0 = self._offset_x + rx0
        cy0 = self._offset_y + ry0
        cx1 = self._offset_x + rx1
        cy1 = self._offset_y + ry1

        if self._rect_id is None:
            self._rect_id = self.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=self.ACCENTO, width=2,
            )
        else:
            self.canvas.coords(self._rect_id, cx0, cy0, cx1, cy1)

    def _on_release(self, event):
        if self._drag_start is None or self._img_originale is None:
            return
        self._drag_start = None
        self._aggiorna_stato_selezione()

    def _azzera_selezione(self, silenzioso: bool = False):
        self._sel = None
        self._drag_start = None
        if self._rect_id is not None:
            try:
                self.canvas.delete(self._rect_id)
            except Exception:
                pass
            self._rect_id = None
        self._aggiorna_stato_selezione(silenzioso=silenzioso)

    def _aggiorna_stato_selezione(self, silenzioso: bool = False):
        if self._sel is None:
            self.btn_applica.configure(state="disabled")
            if not silenzioso:
                self.lbl_sel.configure(
                    text="Disegna un rettangolo sulla slide con il "
                         "mouse, poi premi «Applica ritaglio».",
                    fg=self.FG_TENUE,
                )
            return

        x0, y0, x1, y1 = self._sel
        w_img = x1 - x0
        h_img = y1 - y0
        w_orig = int(round(w_img / self._scala)) if self._scala else 0
        h_orig = int(round(h_img / self._scala)) if self._scala else 0

        self.btn_applica.configure(state="normal")
        self.lbl_sel.configure(
            text=f"Selezione: {w_orig} x {h_orig} px",
            fg=self.PRIMARIO,
        )

    # ------------------------------------------------------------------
    # Applica
    # ------------------------------------------------------------------

    def _applica(self):
        if self._sel is None or self._img_originale is None:
            return

        x0, y0, x1, y1 = self._sel
        img = self._img_originale
        w0, h0 = img.size

        ox0 = int(round(x0 / self._scala))
        oy0 = int(round(y0 / self._scala))
        ox1 = int(round(x1 / self._scala))
        oy1 = int(round(y1 / self._scala))

        ox0 = max(0, min(ox0, w0 - 1))
        oy0 = max(0, min(oy0, h0 - 1))
        ox1 = max(ox0 + 1, min(ox1, w0))
        oy1 = max(oy0 + 1, min(oy1, h0))

        try:
            ritaglio = img.crop((ox0, oy0, ox1, oy1))
        except Exception as e:
            messagebox.showerror(
                "Errore ritaglio",
                f"Impossibile ritagliare: {e}",
                parent=self,
            )
            return

        cb = self.on_conferma
        self.destroy()
        if cb is not None:
            try:
                cb(ritaglio)
            except Exception:
                pass

    def _centra_su_parent(self, parent):
        try:
            self.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass


# ======================================================================
# Selettore immagine
# ======================================================================

class SelettoreImmagine(ctk.CTkToplevel):
    """Popup di selezione di un'immagine da una lista predefinita."""

    def __init__(self, parent, immagini: list[Path],
                 titolo: str = "Scegli immagine",
                 on_scelta=None):
        super().__init__(parent)
        self.immagini = list(immagini)
        self.on_scelta = on_scelta
        self._ctk_images: list = []

        self.title(titolo)
        self.geometry("820x600")
        self.minsize(600, 400)
        self.configure(fg_color=tema.BG_APP)

        try:
            self.transient(parent)
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = card(self)
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(0, weight=1)

        self.entry_ricerca = ctk.CTkEntry(
            top, placeholder_text="Filtra per nome file…",
            height=34, fg_color=tema.BG_INPUT,
        )
        self.entry_ricerca.grid(row=0, column=0, sticky="ew",
                                 padx=12, pady=12)
        self.entry_ricerca.bind(
            "<KeyRelease>", lambda e: self._ricarica_griglia()
        )

        self.scroll = ctk.CTkScrollableFrame(
            self, corner_radius=8, fg_color=tema.BG_INPUT,
        )
        self.scroll.grid(row=1, column=0, sticky="nsew",
                          padx=14, pady=(0, 8))
        for i in range(3):
            self.scroll.grid_columnconfigure(i, weight=1)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        footer.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            footer, text="  Annulla",
            width=120, height=34,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).grid(row=0, column=1, sticky="e")

        self._ricarica_griglia()
        self._centra_su_parent(parent)
        self.after(80, self.entry_ricerca.focus_set)

    def _ricarica_griglia(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self._ctk_images.clear()

        filtro = self.entry_ricerca.get().strip().lower()
        lista = [
            p for p in self.immagini
            if not filtro or filtro in p.name.lower()
        ]

        if not lista:
            ctk.CTkLabel(
                self.scroll, text="(nessuna immagine)",
                text_color=tema.TESTO_MOLTO_TENUE,
            ).grid(row=0, column=0, columnspan=3, padx=8, pady=20)
            return

        for i, p in enumerate(lista):
            self._cella(i // 3, i % 3, p)

    def _cella(self, riga: int, col: int, path: Path):
        cella = ctk.CTkFrame(
            self.scroll, corner_radius=8,
            fg_color=tema.BG_CARD,
            border_width=1, border_color=tema.BG_INPUT_HOVER,
        )
        cella.grid(row=riga, column=col, padx=6, pady=6, sticky="nsew")

        if _HAS_PIL:
            try:
                img = Image.open(str(path))
                img.thumbnail((200, 130), Image.LANCZOS)
                ctk_img = ctk.CTkImage(
                    light_image=img, dark_image=img,
                    size=(img.width, img.height),
                )
                self._ctk_images.append(ctk_img)
                lbl = ctk.CTkLabel(cella, image=ctk_img, text="",
                                    cursor="hand2")
                lbl.image = ctk_img
                lbl.pack(padx=8, pady=(8, 4))
                lbl.bind(
                    "<Button-1>",
                    lambda e, pp=path: self._scegli(pp),
                )
            except Exception:
                ctk.CTkLabel(
                    cella, text="(anteprima n/d)",
                    text_color=tema.TESTO_MOLTO_TENUE,
                ).pack(padx=8, pady=8)
        else:
            ctk.CTkLabel(
                cella, text=path.name, text_color=tema.TESTO,
            ).pack(padx=8, pady=8)

        nome_breve = path.name
        if len(nome_breve) > 28:
            nome_breve = nome_breve[:25] + "..."
        ctk.CTkLabel(
            cella, text=nome_breve,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=tema.TESTO, anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 2))

        try:
            rel = path.relative_to(Path(self.master.root_progetto))
            rel_str = str(rel)
        except Exception:
            rel_str = str(path.parent)
        if len(rel_str) > 40:
            rel_str = "…" + rel_str[-37:]
        ctk.CTkLabel(
            cella, text=rel_str,
            font=ctk.CTkFont(size=9),
            text_color=tema.TESTO_MOLTO_TENUE, anchor="w",
        ).pack(fill="x", padx=8, pady=(0, 6))

        ctk.CTkButton(
            cella, text="Scegli", width=80, height=28,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda pp=path: self._scegli(pp),
        ).pack(padx=8, pady=(0, 8))

    def _scegli(self, path: Path):
        cb = self.on_scelta
        self.destroy()
        if cb is not None:
            try:
                cb(path)
            except Exception:
                pass

    def _centra_su_parent(self, parent):
        try:
            self.update_idletasks()
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            w = self.winfo_width()
            h = self.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass