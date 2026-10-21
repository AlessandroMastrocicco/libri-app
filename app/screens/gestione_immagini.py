# -*- coding: utf-8 -*-
"""
gestione_immagini.py - Schermata di gestione e cattura delle immagini
delle slide.

Due modalità (segmented button in alto):
- "Immagini salvate" (default): galleria a 4 colonne di tutte le
  immagini della dispensa corrente, con azioni Copia / Apri / Rinomina
  / Elimina per ogni cella.
- "Cattura slide": visore della slide corrente con slider di
  navigazione e bottone "Cattura immagine".

Sidebar sinistra: elenco dispense estratte del libro.

Il PNG viene salvato in libri/<slug>/immagini/<dispensa>/.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from app.ui import tema
from app.ui.widgets import (
    bottone_primario,
    bottone_secondario,
    card,
)
from app.core.slide_extract import (
    carica_pagine,
    cartella_catture,
    copia_immagine_negli_appunti,
    elenca_catture,
    elenca_estratti,
    estrai_numero_lezione,
    salva_cattura_con_nome,
)
from app.core.screenshot import cattura_rettangolo, pil_disponibile


# Numero di colonne della griglia immagini nella vista galleria
N_COLONNE_GALLERIA = 4


def _slug_nome(s: str) -> str:
    """Stessa logica di slide_extract._slug, replicata per la rinomina."""
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    return s or "immagine"


# ======================================================================
# Popup "salva cattura"
# ======================================================================

class PopupSalvaCattura(ctk.CTkToplevel):
    """
    Popup modale con anteprima della cattura e campo per il nome.
    Chiama `on_salva(image_pil, nome)` alla conferma.
    Opzionale: `on_riprova()` per ripetere la cattura.
    """

    def __init__(self, parent, image_pil,
                 nome_default: str,
                 on_salva,
                 on_riprova=None):
        super().__init__(parent)
        self.image_pil = image_pil
        self.on_salva = on_salva
        self.on_riprova = on_riprova

        self.title("Salva cattura")
        self.configure(fg_color=tema.BG_APP)
        self.resizable(False, False)

        try:
            self.transient(parent)
        except Exception:
            pass

        preview = image_pil.copy()
        max_w, max_h = 640, 420
        w, h = preview.size
        if w > max_w or h > max_h:
            preview.thumbnail((max_w, max_h), Image.LANCZOS)

        ctk_img = ctk.CTkImage(
            light_image=preview, dark_image=preview,
            size=(preview.width, preview.height),
        )

        win_w = max(460, preview.width + 60)
        win_h = min(760, preview.height + 250)
        self.geometry(f"{win_w}x{win_h}")

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text=f"Immagine: {image_pil.width} x {image_pil.height} px",
            text_color=tema.TESTO_TENUE,
            font=ctk.CTkFont(size=11), anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        lbl = ctk.CTkLabel(self, image=ctk_img, text="")
        lbl.image = ctk_img
        lbl.grid(row=1, column=0, padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self, text="Nome cattura",
            font=ctk.CTkFont(size=12, weight="bold"), anchor="w",
            text_color=tema.TESTO,
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 4))

        self.entry = ctk.CTkEntry(
            self,
            height=36,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=tema.BG_INPUT,
        )
        self.entry.grid(row=3, column=0, sticky="ew",
                         padx=20, pady=(0, 6))
        self.entry.insert(0, nome_default)
        self.entry.bind("<KeyRelease>", lambda e: self._aggiorna_label())
        self.entry.bind("<Return>", lambda e: self._salva())

        self.lbl_file = ctk.CTkLabel(
            self, text=f"File: {nome_default}.png",
            text_color=tema.TESTO_MOLTO_TENUE,
            font=ctk.CTkFont(size=11), anchor="w",
        )
        self.lbl_file.grid(row=4, column=0, sticky="w",
                            padx=20, pady=(0, 12))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 20))
        btns.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btns, text="  Riprova", width=120, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._riprova,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            btns, text="  Annulla", width=120, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).grid(row=0, column=1, sticky="e", padx=(0, 8))

        ctk.CTkButton(
            btns, text="  Salva", width=140, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._salva,
        ).grid(row=0, column=2, sticky="e")

        self._centra_su_parent(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        try:
            self.grab_set()
        except Exception:
            pass

        self.after(120, self.entry.focus_set)
        self.after(120, lambda: self.entry.select_range(0, "end"))
        self.after(120, self.lift)
        self.after(120, self.focus_force)

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

    def _aggiorna_label(self):
        nome = self.entry.get().strip() or "(vuoto)"
        self.lbl_file.configure(text=f"File: {nome}.png")

    def _salva(self):
        nome = self.entry.get().strip()
        if not nome:
            return
        try:
            self.on_salva(self.image_pil, nome)
        finally:
            self.destroy()

    def _riprova(self):
        parent = self.master
        callback = self.on_riprova
        self.destroy()
        if callback is not None and parent is not None:
            try:
                parent.after(120, callback)
            except Exception:
                pass


# ======================================================================
# Popup "rinomina immagine"
# ======================================================================

class PopupRinominaImmagine(ctk.CTkToplevel):
    """
    Popup modale per rinominare un file immagine.
    Chiama `on_rinominata(nuovo_path)` dopo una rinomina riuscita.
    """

    def __init__(self, parent, path_img: Path, on_rinominata):
        super().__init__(parent)
        self.path_img = path_img
        self.on_rinominata = on_rinominata

        self.title("Rinomina immagine")
        self.configure(fg_color=tema.BG_APP)
        self.resizable(False, False)

        try:
            self.transient(parent)
        except Exception:
            pass

        self.geometry("460x230")
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self, text="Rinomina immagine",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))

        ctk.CTkLabel(
            self, text=f"File attuale: {path_img.name}",
            font=ctk.CTkFont(size=11),
            anchor="w", text_color=tema.TESTO_MOLTO_TENUE,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self, text="Nuovo nome",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 4))

        self.entry = ctk.CTkEntry(
            self, height=36,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=tema.BG_INPUT,
        )
        self.entry.grid(row=3, column=0, sticky="ew",
                         padx=20, pady=(0, 6))
        self.entry.insert(0, path_img.stem)
        self.entry.bind("<Return>", lambda e: self._rinomina())
        self.entry.bind("<KeyRelease>", lambda e: self._aggiorna_label())

        self.lbl_anteprima = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11),
            anchor="w", text_color=tema.TESTO_MOLTO_TENUE,
        )
        self.lbl_anteprima.grid(row=4, column=0, sticky="w",
                                 padx=20, pady=(0, 12))
        self._aggiorna_label()

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 20))
        btns.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btns, text="  Annulla", width=120, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            btns, text="  Rinomina", width=140, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._rinomina,
        ).grid(row=0, column=1, sticky="e")

        self._centra_su_parent(parent)
        self.bind("<Escape>", lambda e: self.destroy())

        try:
            self.grab_set()
        except Exception:
            pass

        self.after(120, self.entry.focus_set)
        self.after(120, lambda: self.entry.select_range(0, "end"))
        self.after(120, self.lift)
        self.after(120, self.focus_force)

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

    def _aggiorna_label(self):
        nome = self.entry.get().strip() or "(vuoto)"
        slug = _slug_nome(nome)
        self.lbl_anteprima.configure(text=f"File: {slug}.png")

    def _rinomina(self):
        nome = self.entry.get().strip()
        if not nome:
            return
        slug = _slug_nome(nome)

        if slug == self.path_img.stem:
            self.destroy()
            return

        cartella = self.path_img.parent
        nuovo_path = cartella / f"{slug}.png"
        n = 2
        while nuovo_path.exists():
            nuovo_path = cartella / f"{slug}_{n}.png"
            n += 1

        try:
            self.path_img.rename(nuovo_path)
        except Exception as e:
            messagebox.showerror(
                "Errore",
                f"Impossibile rinominare:\n{e}",
                parent=self,
            )
            return

        try:
            self.on_rinominata(nuovo_path)
        except Exception:
            pass
        self.destroy()


# ======================================================================
# Popup anteprima immagine
# ======================================================================

class PopupAnteprimaCattura(ctk.CTkToplevel):
    def __init__(self, parent, path_img: Path,
                 on_eliminata=None,
                 on_rinominata=None):
        super().__init__(parent)
        self.path_img = path_img
        self.on_eliminata = on_eliminata
        self.on_rinominata = on_rinominata

        self.title(f"Anteprima — {path_img.name}")
        self.configure(fg_color=tema.BG_APP)

        try:
            self.transient(parent)
        except Exception:
            pass

        img = Image.open(str(path_img))
        max_w, max_h = 900, 600
        w, h = img.size
        if w > max_w or h > max_h:
            img.thumbnail((max_w, max_h), Image.LANCZOS)

        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img,
            size=(img.width, img.height),
        )
        self.geometry(f"{img.width + 40}x{img.height + 140}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        lbl = ctk.CTkLabel(self, image=ctk_img, text="")
        lbl.image = ctk_img
        lbl.grid(row=0, column=0, padx=20, pady=(20, 8))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=1, column=0, pady=(0, 16))

        ctk.CTkButton(
            btns, text="  Copia",
            width=110, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._copia,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Rinomina",
            width=130, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._rinomina,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Apri",
            width=110, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self._apri(path_img),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Elimina",
            width=110, height=36,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            command=self._elimina,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Chiudi",
            width=100, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).pack(side="left", padx=4)

        self.after(80, self.lift)
        self.after(80, self.focus_force)

    def _copia(self):
        ok, msg = copia_immagine_negli_appunti(self.path_img)
        if ok:
            messagebox.showinfo("Fatto", msg, parent=self)
        else:
            messagebox.showerror("Errore", msg, parent=self)

    def _rinomina(self):
        parent = self.master
        on_rin = self.on_rinominata
        path = self.path_img
        self.destroy()
        if parent is not None:
            try:
                PopupRinominaImmagine(
                    parent, path,
                    on_rinominata=lambda _np: (
                        on_rin() if on_rin else None
                    ),
                )
            except Exception:
                pass

    def _apri(self, p: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=False)
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
        except Exception:
            pass

    def _elimina(self):
        if not messagebox.askyesno(
            "Elimina immagine",
            f"Eliminare {self.path_img.name}?\n\n"
            f"Questa operazione non e' reversibile.",
            parent=self,
        ):
            return
        try:
            self.path_img.unlink()
        except Exception as e:
            messagebox.showerror(
                "Errore",
                f"Impossibile eliminare: {e}",
                parent=self,
            )
            return
        if self.on_eliminata:
            try:
                self.on_eliminata()
            except Exception:
                pass
        self.destroy()


# ======================================================================
# Schermata principale
# ======================================================================

class SchermataGestioneImmagini(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        self._dispense: list[dict] = []
        self._dispensa_corrente: dict | None = None
        self._pagine: list[Path] = []
        self._idx_pagina: int = 0
        self._immagini: list[Path] = []
        self._slider_in_aggiornamento: bool = False

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_center()

        self._ricarica_sidebar()

    # ------------------------------------------------------------------
    # Sidebar sinistra
    # ------------------------------------------------------------------

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=260, corner_radius=0,
                            fg_color=tema.BG_CARD)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(2, weight=1)
        side.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(side, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(14, 6))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            top, text="  Torna al libro",
            height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self.app.mostra_libro(self.slug),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            top, text="  Aggiorna elenco",
            height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._ricarica_sidebar,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(
            top, text=f"Libro: {self.slug}",
            font=ctk.CTkFont(size=11),
            anchor="w", text_color=tema.TESTO_TENUE,
            wraplength=220,
        ).grid(row=2, column=0, sticky="ew", pady=(6, 0))

        ctk.CTkLabel(
            side, text="Dispense estratte",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 4))

        self.scroll_dispense = ctk.CTkScrollableFrame(
            side, width=230, fg_color=tema.BG_INPUT,
        )
        self.scroll_dispense.grid(row=2, column=0, sticky="nsew",
                                   padx=8, pady=(0, 8))
        self.scroll_dispense.grid_columnconfigure(0, weight=1)

    def _ricarica_sidebar(self):
        for w in self.scroll_dispense.winfo_children():
            w.destroy()

        self._dispense = elenca_estratti(
            self.app.root_progetto, self.slug
        )

        if not self._dispense:
            ctk.CTkLabel(
                self.scroll_dispense,
                text="(nessuna dispensa estratta)\n\n"
                     "Vai in «Estrattore slide» dal libro per "
                     "estrarre un PDF.",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=11),
                anchor="w", justify="left",
            ).pack(fill="x", padx=8, pady=8)
            self._dispensa_corrente = None
            self._pagine = []
            self._immagini = []
            self._aggiorna_viewer()
            self._aggiorna_slider()
            self._ricarica_galleria()
            return

        for e in self._dispense:
            attiva = (
                self._dispensa_corrente is not None
                and self._dispensa_corrente["dispensa"] == e["dispensa"]
            )
            colore = tema.PRIMARIO if attiva else tema.BG_INPUT_HOVER
            hover = tema.PRIMARIO_HOVER if attiva else tema.NEUTRO_HOVER
            ctk.CTkButton(
                self.scroll_dispense,
                text=f"  {e['dispensa']}  ({e['n_pagine']})",
                height=30, corner_radius=6,
                fg_color=colore, hover_color=hover,
                anchor="w",
                font=ctk.CTkFont(size=11),
                command=lambda d=e: self._seleziona_dispensa(d),
            ).pack(fill="x", padx=4, pady=1)

        if self._dispensa_corrente is None:
            self._seleziona_dispensa(self._dispense[0])

    # ------------------------------------------------------------------
    # Area centrale (segmented + stack di 2 viste)
    # ------------------------------------------------------------------

    def _build_center(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(1, weight=1)

        # Toolbar superiore con segmented button
        toolbar = card(center)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        self.seg_modo = ctk.CTkSegmentedButton(
            toolbar,
            values=["  Immagini salvate  ", "  Cattura slide  "],
            command=self._on_modo_change,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
        )
        self.seg_modo.grid(row=0, column=0, sticky="w",
                            padx=12, pady=8)
        self.seg_modo.set("  Immagini salvate  ")

        self.lbl_stato = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(size=12),
            text_color=tema.TESTO_TENUE,
            anchor="e",
        )
        self.lbl_stato.grid(row=0, column=1, sticky="e", padx=(6, 12))

        # Stack: entrambe le viste occupano la stessa cella
        self.stack = ctk.CTkFrame(center, fg_color="transparent")
        self.stack.grid(row=1, column=0, sticky="nsew")
        self.stack.grid_columnconfigure(0, weight=1)
        self.stack.grid_rowconfigure(0, weight=1)

        self.frame_galleria = ctk.CTkFrame(
            self.stack, fg_color="transparent",
        )
        self.frame_galleria.grid(row=0, column=0, sticky="nsew")
        self.frame_galleria.grid_columnconfigure(0, weight=1)
        self.frame_galleria.grid_rowconfigure(1, weight=1)

        self.frame_cattura = ctk.CTkFrame(
            self.stack, fg_color="transparent",
        )
        self.frame_cattura.grid(row=0, column=0, sticky="nsew")
        self.frame_cattura.grid_columnconfigure(0, weight=1)
        self.frame_cattura.grid_rowconfigure(1, weight=1)

        self._build_galleria(self.frame_galleria)
        self._build_cattura(self.frame_cattura)

        # Default: galleria
        self.frame_galleria.tkraise()

    def _on_modo_change(self, valore: str):
        v = valore.strip()
        if v == "Cattura slide":
            self.frame_cattura.tkraise()
            self._aggiorna_viewer()
            self._aggiorna_slider()
        else:
            self.frame_galleria.tkraise()
            self._ricarica_galleria()

    def _vai_a_galleria(self):
        try:
            self.seg_modo.set("  Immagini salvate  ")
        except Exception:
            pass
        self.frame_galleria.tkraise()
        self._ricarica_galleria()

    # ------------------------------------------------------------------
    # Vista "Immagini salvate"
    # ------------------------------------------------------------------

    def _build_galleria(self, parent):
        toolbar = card(parent)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.grid_columnconfigure(2, weight=1)

        self.lbl_titolo_galleria = ctk.CTkLabel(
            toolbar, text="Immagini",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        )
        self.lbl_titolo_galleria.grid(row=0, column=0,
                                        sticky="w", padx=(12, 12), pady=10)

        bottone_secondario(
            toolbar, "  Aggiorna",
            command=self._ricarica_galleria,
            width=120,
        ).grid(row=0, column=1, padx=6, pady=10)

        bottone_secondario(
            toolbar, "  Apri cartella",
            command=self._apri_cartella_immagini,
            width=150,
        ).grid(row=0, column=2, sticky="w", padx=6, pady=10)

        bottone_primario(
            toolbar, "  Cattura nuova immagine",
            command=self._vai_a_cattura,
            width=200,
        ).grid(row=0, column=3, sticky="e",
                padx=(6, 12), pady=10)

        self.scroll_galleria = ctk.CTkScrollableFrame(
            parent, fg_color=tema.BG_INPUT,
        )
        self.scroll_galleria.grid(row=1, column=0, sticky="nsew")
        for i in range(N_COLONNE_GALLERIA):
            self.scroll_galleria.grid_columnconfigure(i, weight=1)

    def _vai_a_cattura(self):
        try:
            self.seg_modo.set("  Cattura slide  ")
        except Exception:
            pass
        self._on_modo_change("Cattura slide")

    def _ricarica_galleria(self):
        for w in self.scroll_galleria.winfo_children():
            w.destroy()

        if self._dispensa_corrente is None:
            self.lbl_titolo_galleria.configure(text="Immagini")
            ctk.CTkLabel(
                self.scroll_galleria,
                text="(nessuna dispensa selezionata)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, columnspan=N_COLONNE_GALLERIA,
                   padx=8, pady=20, sticky="w")
            return

        dispensa = self._dispensa_corrente["dispensa"]
        self._immagini = elenca_catture(
            self.app.root_progetto, self.slug, dispensa
        )
        self.lbl_titolo_galleria.configure(
            text=f"Immagini in {dispensa}  ({len(self._immagini)})"
        )

        if not self._immagini:
            ctk.CTkLabel(
                self.scroll_galleria,
                text="(nessuna immagine salvata)\n\n"
                     "Passa a «Cattura slide» per selezionare una "
                     "regione della slide corrente e salvarla.",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=12),
                anchor="w", justify="left",
            ).grid(row=0, column=0, columnspan=N_COLONNE_GALLERIA,
                   padx=8, pady=20, sticky="w")
            return

        if not _HAS_PIL:
            ctk.CTkLabel(
                self.scroll_galleria,
                text="Pillow non installato: pip install pillow",
                text_color=tema.ERRORE,
                font=ctk.CTkFont(size=12),
            ).grid(row=0, column=0, columnspan=N_COLONNE_GALLERIA,
                   padx=8, pady=20, sticky="w")
            return

        for i, p in enumerate(self._immagini):
            riga = i // N_COLONNE_GALLERIA
            col = i % N_COLONNE_GALLERIA
            self._cella_galleria(riga, col, p)

    def _cella_galleria(self, riga: int, col: int, path_img: Path):
        cella = ctk.CTkFrame(
            self.scroll_galleria, corner_radius=10,
            fg_color=tema.BG_CARD, border_width=1,
            border_color=tema.BG_INPUT_HOVER,
        )
        cella.grid(row=riga, column=col, padx=8, pady=8, sticky="nsew")

        try:
            img = Image.open(str(path_img))
            thumb = img.copy()
            thumb.thumbnail((220, 160), Image.LANCZOS)
            ctk_img = ctk.CTkImage(
                light_image=thumb, dark_image=thumb,
                size=(thumb.width, thumb.height),
            )
            w_orig, h_orig = img.size
        except Exception:
            ctk_img = None
            w_orig, h_orig = 0, 0

        if ctk_img is not None:
            lbl = ctk.CTkLabel(
                cella, image=ctk_img, text="", cursor="hand2",
            )
            lbl.image = ctk_img
            lbl.pack(padx=10, pady=(10, 6))
            lbl.bind(
                "<Button-1>",
                lambda e, p=path_img: self._apri_preview(p),
            )
        else:
            ctk.CTkLabel(
                cella, text="(anteprima non disponibile)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=11),
            ).pack(padx=10, pady=20)

        ctk.CTkLabel(
            cella, text=path_img.stem,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=tema.TESTO, anchor="w",
        ).pack(fill="x", padx=10)

        if w_orig and h_orig:
            ctk.CTkLabel(
                cella, text=f"{w_orig} x {h_orig} px",
                font=ctk.CTkFont(size=10),
                text_color=tema.TESTO_MOLTO_TENUE,
                anchor="w",
            ).pack(fill="x", padx=10, pady=(0, 4))

        btns = ctk.CTkFrame(cella, fg_color="transparent")
        btns.pack(fill="x", padx=6, pady=(2, 8))

        ctk.CTkButton(
            btns, text="Copia", width=70, height=26,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda p=path_img: self._copia_immagine(p),
        ).pack(side="left", padx=(4, 2))

        ctk.CTkButton(
            btns, text="Apri", width=60, height=26,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda p=path_img: self._apri_preview(p),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btns, text="Rin.", width=60, height=26,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda p=path_img: self._rinomina_immagine(p),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btns, text="X", width=34, height=26,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda p=path_img: self._elimina_immagine(p),
        ).pack(side="right", padx=(2, 4))

    # ------------------------------------------------------------------
    # Vista "Cattura slide"
    # ------------------------------------------------------------------

    def _build_cattura(self, parent):
        toolbar = card(parent)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        self.btn_cattura = bottone_primario(
            toolbar, "  Cattura immagine",
            command=self._cattura,
            width=200,
        )
        self.btn_cattura.grid(row=0, column=0, padx=(12, 6), pady=10)

        self.lbl_pagina = ctk.CTkLabel(
            toolbar, text="pagina - / -",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=tema.TESTO,
            anchor="e",
        )
        self.lbl_pagina.grid(row=0, column=2, sticky="e", padx=(6, 12))

        viewer_wrap = card(parent)
        viewer_wrap.grid(row=1, column=0, sticky="nsew")
        viewer_wrap.grid_columnconfigure(0, weight=1)
        viewer_wrap.grid_rowconfigure(0, weight=1)

        self.lbl_slide = ctk.CTkLabel(
            viewer_wrap, text="",
            fg_color=tema.BG_INPUT,
            corner_radius=8,
        )
        self.lbl_slide.grid(row=0, column=0, sticky="nsew",
                             padx=8, pady=8)

        bar = ctk.CTkFrame(parent, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        bar.grid_columnconfigure(1, weight=1)

        self.btn_prev = bottone_secondario(
            bar, "  <", command=self._pagina_prec, width=60,
        )
        self.btn_prev.grid(row=0, column=0, padx=(0, 6))

        self.slider = ctk.CTkSlider(
            bar, from_=1, to=1, number_of_steps=1,
            command=self._on_slider,
        )
        self.slider.grid(row=0, column=1, sticky="ew")
        self.slider.set(1)

        self.btn_next = bottone_secondario(
            bar, ">  ", command=self._pagina_succ, width=60,
        )
        self.btn_next.grid(row=0, column=2, padx=(6, 0))

    # ------------------------------------------------------------------
    # Cambio dispensa
    # ------------------------------------------------------------------

    def _seleziona_dispensa(self, dispensa: dict):
        self._dispensa_corrente = dispensa
        cartella = dispensa["cartella"]
        self._pagine = carica_pagine(cartella)
        self._idx_pagina = 0
        self._ricarica_sidebar()
        self._aggiorna_slider()
        self._aggiorna_viewer()
        self._ricarica_galleria()

    # ------------------------------------------------------------------
    # Slider / viewer
    # ------------------------------------------------------------------

    def _aggiorna_slider(self):
        n = len(self._pagine)
        self._slider_in_aggiornamento = True
        try:
            if n <= 1:
                self.slider.configure(from_=1, to=1,
                                       number_of_steps=1)
                self.slider.set(1)
            else:
                self.slider.configure(from_=1, to=n,
                                       number_of_steps=n - 1)
                self.slider.set(self._idx_pagina + 1)
        finally:
            self._slider_in_aggiornamento = False

        self.lbl_pagina.configure(
            text=f"pagina {self._idx_pagina + 1} / {n}"
            if n else "pagina - / -"
        )

        if n == 0:
            self.btn_cattura.configure(state="disabled")
        else:
            self.btn_cattura.configure(state="normal")

    def _on_slider(self, valore):
        if self._slider_in_aggiornamento:
            return
        try:
            idx = int(round(float(valore))) - 1
        except Exception:
            return
        idx = max(0, min(idx, len(self._pagine) - 1))
        if idx == self._idx_pagina:
            return
        self._idx_pagina = idx
        self._aggiorna_viewer()
        self._aggiorna_slider()

    def _pagina_prec(self):
        if self._idx_pagina > 0:
            self._idx_pagina -= 1
            self._aggiorna_viewer()
            self._aggiorna_slider()

    def _pagina_succ(self):
        if self._idx_pagina < len(self._pagine) - 1:
            self._idx_pagina += 1
            self._aggiorna_viewer()
            self._aggiorna_slider()

    def _aggiorna_viewer(self):
        if not _HAS_PIL:
            self.lbl_slide.configure(
                image=None,
                text="Pillow non installato:  pip install pillow",
            )
            return

        if not self._pagine:
            self.lbl_slide.configure(image=None, text="(nessuna pagina)")
            return

        path = self._pagine[self._idx_pagina]
        try:
            img = Image.open(str(path))
        except Exception as e:
            self.lbl_slide.configure(image=None,
                                      text=f"Errore apertura: {e}")
            return

        max_w, max_h = 1100, 700
        w, h = img.size
        if w > max_w or h > max_h:
            img.thumbnail((max_w, max_h), Image.LANCZOS)

        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img,
            size=(img.width, img.height),
        )
        self.lbl_slide.configure(image=ctk_img, text="")
        self.lbl_slide.image = ctk_img

    # ------------------------------------------------------------------
    # Azioni su singola immagine (usate dalla galleria)
    # ------------------------------------------------------------------

    def _apri_preview(self, path_img: Path):
        PopupAnteprimaCattura(
            self, path_img,
            on_eliminata=self._ricarica_galleria,
            on_rinominata=self._ricarica_galleria,
        )

    def _rinomina_immagine(self, path_img: Path):
        PopupRinominaImmagine(
            self, path_img,
            on_rinominata=lambda _np: self._ricarica_galleria(),
        )

    def _copia_immagine(self, path_img: Path):
        ok, msg = copia_immagine_negli_appunti(path_img)
        if ok:
            self._set_stato(f"Copiato: {path_img.name}",
                            colore=tema.SUCCESSO)
            return
        messagebox.showerror("Copia non disponibile", msg)

    def _elimina_immagine(self, path_img: Path):
        if not messagebox.askyesno(
            "Elimina immagine",
            f"Eliminare {path_img.name}?\n\n"
            f"Questa operazione non e' reversibile.",
            parent=self,
        ):
            return
        try:
            path_img.unlink()
        except Exception as e:
            messagebox.showerror(
                "Errore", f"Impossibile eliminare: {e}", parent=self,
            )
            return
        self._set_stato(f"Eliminato: {path_img.name}",
                        colore=tema.SUCCESSO)
        self._ricarica_galleria()

    # ------------------------------------------------------------------
    # Nome di default: L<numero_lezione>S<numero_slide>
    # ------------------------------------------------------------------

    def _nome_default_cattura(self) -> str:
        if self._dispensa_corrente is None:
            return "cattura"

        dispensa = self._dispensa_corrente["dispensa"]

        fallback = 1
        try:
            ordinate = [d["dispensa"] for d in self._dispense]
            fallback = ordinate.index(dispensa) + 1
        except ValueError:
            pass

        lezione = estrai_numero_lezione(dispensa, fallback=fallback)
        slide = self._idx_pagina + 1
        return f"L{lezione}S{slide}"

    # ------------------------------------------------------------------
    # Cattura
    # ------------------------------------------------------------------

    def _cattura(self):
        if not pil_disponibile():
            messagebox.showerror(
                "Cattura non disponibile",
                "Pillow non installato. Esegui: pip install pillow",
            )
            return

        if self._dispensa_corrente is None:
            messagebox.showwarning(
                "Nessuna dispensa",
                "Seleziona prima una dispensa o creane una.",
            )
            return

        self.btn_cattura.configure(state="disabled")
        self._set_stato("Seleziona l'area da catturare…")

        try:
            img = cattura_rettangolo(self)
        except Exception as e:
            img = None
            self._set_stato(f"Errore cattura: {e}", colore=tema.ERRORE)
        finally:
            self.btn_cattura.configure(state="normal")

        if img is None:
            self._set_stato("Cattura annullata.")
            return

        nome_default = self._nome_default_cattura()
        self._set_stato(f"Cattura pronta: {nome_default}.png")
        PopupSalvaCattura(
            self,
            image_pil=img,
            nome_default=nome_default,
            on_salva=self._salva_cattura,
            on_riprova=self._cattura,
        )

    def _salva_cattura(self, image_pil, nome: str):
        if self._dispensa_corrente is None:
            return
        dispensa = self._dispensa_corrente["dispensa"]
        try:
            path = salva_cattura_con_nome(
                self.app.root_progetto, self.slug, dispensa,
                image_pil, nome,
            )
        except Exception as e:
            self._set_stato(f"Errore salvataggio: {e}",
                            colore=tema.ERRORE)
            return
        self._set_stato(f"Salvato: {path.name}", colore=tema.SUCCESSO)
        # Dopo il salvataggio vai alla galleria
        self._vai_a_galleria()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        try:
            self.lbl_stato.configure(text=testo, text_color=colore)
        except Exception:
            pass

    def _apri_cartella_immagini(self):
        if self._dispensa_corrente is None:
            return
        dispensa = self._dispensa_corrente["dispensa"]
        c = cartella_catture(self.app.root_progetto, self.slug, dispensa)
        c.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(c))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(c)], check=False)
            else:
                subprocess.run(["xdg-open", str(c)], check=False)
        except Exception:
            pass