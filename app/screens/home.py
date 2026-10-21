# -*- coding: utf-8 -*-
"""
home.py - Schermata principale: elenco libri + azioni globali.

Ogni riga della lista mostra:
- nome del libro (cliccabile -> apre la vista libro)
- pulsante Rinomina
- pulsante Elimina
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import (
    bottone_primario,
    bottone_secondario,
    card,
    sottotitolo,
    titolo,
)
from app.core.libro import (
    elenca_libri,
    elimina_libro,
    formatta_dimensione,
    informazioni_eliminazione,
    percorso_libro,
    rinomina_libro,
    slug_valido,
)


# ======================================================================
# Dialog di rinomina
# ======================================================================

class DialogRinomina(ctk.CTkToplevel):
    """Piccola finestra per rinominare un libro."""

    def __init__(self, parent, root_progetto, slug_old: str,
                 on_success):
        super().__init__(parent)
        self.root_progetto = root_progetto
        self.slug_old = slug_old
        self.on_success = on_success

        self.title("Rinomina libro")
        self.geometry("480x260")
        self.configure(fg_color=tema.BG_APP)
        self.resizable(False, False)

        try:
            self.transient(parent)
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)

        # header
        ctk.CTkLabel(
            self, text="Rinomina libro",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))

        ctk.CTkLabel(
            self,
            text=f"Nuovo nome cartella per '{slug_old}'.\n"
                 f"Lettere, numeri e underscore; deve iniziare con una "
                 f"lettera.",
            font=ctk.CTkFont(size=12),
            anchor="w", justify="left",
            text_color=tema.TESTO_TENUE,
            wraplength=440,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 12))

        # campo
        self.entry = ctk.CTkEntry(
            self,
            height=36,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=tema.BG_INPUT,
        )
        self.entry.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        self.entry.insert(0, slug_old)
        self.entry.bind("<KeyRelease>", lambda e: self._valida())
        self.entry.bind("<Return>", lambda e: self._conferma())

        self.lbl_errore = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11),
            anchor="w", justify="left",
            text_color=tema.ERRORE,
            wraplength=440,
        )
        self.lbl_errore.grid(row=3, column=0, sticky="ew",
                             padx=20, pady=(0, 8))

        # pulsanti
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="e", padx=20, pady=(4, 20))

        ctk.CTkButton(
            btns, text="  Annulla",
            width=110, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).pack(side="left", padx=(0, 8))

        self.btn_ok = ctk.CTkButton(
            btns, text="  Rinomina",
            width=130, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._conferma,
        )
        self.btn_ok.pack(side="left")

        self.after(80, self.entry.focus_set)
        self.after(80, self.lift)
        self.after(80, self.focus_force)

        self._valida()

    def _valida(self) -> bool:
        nuovo = self.entry.get().strip()

        if not nuovo:
            self.lbl_errore.configure(text="Il nome e' obbligatorio.")
            self.btn_ok.configure(state="disabled")
            return False

        if nuovo == self.slug_old:
            self.lbl_errore.configure(
                text="Il nuovo nome e' identico a quello attuale."
            )
            self.btn_ok.configure(state="disabled")
            return False

        ok, motivo = slug_valido(nuovo)
        if not ok:
            self.lbl_errore.configure(text=motivo)
            self.btn_ok.configure(state="disabled")
            return False

        try:
            destinazione = percorso_libro(self.root_progetto, nuovo)
            if destinazione.exists():
                self.lbl_errore.configure(
                    text=f"Esiste gia' un libro chiamato '{nuovo}'."
                )
                self.btn_ok.configure(state="disabled")
                return False
        except Exception:
            pass

        self.lbl_errore.configure(text="")
        self.btn_ok.configure(state="normal")
        return True

    def _conferma(self):
        if not self._valida():
            return

        nuovo = self.entry.get().strip()
        risultato = rinomina_libro(
            self.root_progetto, self.slug_old, nuovo
        )

        if not risultato["ok"]:
            self.lbl_errore.configure(
                text=" | ".join(risultato["errori"]) or "Errore."
            )
            return

        try:
            self.on_success(nuovo)
        except Exception:
            pass
        self.destroy()


# ======================================================================
# Schermata Home
# ======================================================================

class SchermataHome(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_azioni()
        self._build_elenco()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        titolo(header, "LIBRI").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        sottotitolo(
            header,
            "Elenco dei libri. Clicca un libro per aprirlo e gestire "
            "capitoli e paragrafi. L'estrattore slide e' disponibile "
            "dentro ogni libro.",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

    def _build_azioni(self):
        azioni = ctk.CTkFrame(self, fg_color="transparent")
        azioni.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        azioni.grid_columnconfigure(4, weight=1)

        bottone_primario(
            azioni,
            "  Crea nuovo libro",
            command=self.app.mostra_crea_libro,
            width=210,
        ).grid(row=0, column=0, sticky="w")

        bottone_secondario(
            azioni,
            "  Ricarica elenco",
            command=self._ricarica_elenco,
            width=170,
        ).grid(row=0, column=2, sticky="w", padx=(8, 0))

    def _build_elenco(self):
        wrap = card(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        sottotitolo(wrap, "Libri presenti in libri/").grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4)
        )

        self.scroll = ctk.CTkScrollableFrame(
            wrap, corner_radius=8, fg_color=tema.BG_INPUT
        )
        self.scroll.grid(row=1, column=0, sticky="nsew",
                         padx=14, pady=(0, 14))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._ricarica_elenco()

    # ------------------------------------------------------------------
    # Logica
    # ------------------------------------------------------------------

    def _ricarica_elenco(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        libri = elenca_libri(self.app.root_progetto)

        if not libri:
            ctk.CTkLabel(
                self.scroll,
                text="(nessun libro presente)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=13),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        for i, slug in enumerate(libri):
            self._riga_libro(i, slug)

    def _riga_libro(self, indice: int, slug: str):
        riga = ctk.CTkFrame(self.scroll, fg_color="transparent")
        riga.grid(row=indice, column=0, sticky="ew", pady=3)
        riga.grid_columnconfigure(0, weight=1)

        # nome del libro (cliccabile -> apre il libro)
        ctk.CTkButton(
            riga,
            text=slug,
            height=36,
            corner_radius=6,
            fg_color=tema.BG_INPUT_HOVER,
            hover_color=tema.NEUTRO_HOVER,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda s=slug: self.app.mostra_libro(s),
        ).grid(row=0, column=0, sticky="ew", padx=(4, 4), pady=4)

        ctk.CTkButton(
            riga,
            text="  Rinomina",
            width=120, height=36,
            corner_radius=8,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=12),
            command=lambda s=slug: self._rinomina(s),
        ).grid(row=0, column=1, sticky="e", padx=(0, 4), pady=4)

        ctk.CTkButton(
            riga,
            text="  Elimina",
            width=110, height=36,
            corner_radius=8,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda s=slug: self._elimina(s),
        ).grid(row=0, column=2, sticky="e", padx=(0, 4), pady=4)

    # ------------------------------------------------------------------
    # Rinomina
    # ------------------------------------------------------------------

    def _rinomina(self, slug: str):
        DialogRinomina(
            self,
            self.app.root_progetto,
            slug,
            on_success=self._dopo_rinomina,
        )

    def _dopo_rinomina(self, nuovo_slug: str):
        self._ricarica_elenco()
        messagebox.showinfo(
            "Libro rinominato",
            f"Il libro e' stato rinominato in:\n\n    {nuovo_slug}",
        )

    # ------------------------------------------------------------------
    # Eliminazione
    # ------------------------------------------------------------------

    def _elimina(self, slug: str):
        info = informazioni_eliminazione(self.app.root_progetto, slug)
        if not info["esiste"]:
            messagebox.showerror(
                "Libro non trovato",
                f"Il libro '{slug}' non esiste piu'.",
            )
            self._ricarica_elenco()
            return

        dim = formatta_dimensione(info["dimensione_byte"])
        testo_1 = (
            f"Stai per eliminare DEFINITIVAMENTE il libro:\n\n"
            f"    {slug}\n\n"
            f"Verranno cancellati:\n"
            f"    - {info['n_capitoli']} capitoli\n"
            f"    - {info['n_paragrafi']} paragrafi\n"
            f"    - tutti i file di tracciamento\n"
            f"    - tutta la cache\n\n"
            f"Dimensione totale: {dim}\n\n"
            f"Questa operazione NON e' reversibile. Continuare?"
        )
        if not messagebox.askyesno(
            "Elimina libro - conferma 1 di 2",
            testo_1, icon="warning", default="no",
        ):
            return

        if not messagebox.askyesno(
            "Elimina libro - conferma 2 di 2",
            f"Sei sicuro di voler eliminare '{slug}' e tutti i suoi dati?",
            icon="warning", default="no",
        ):
            return

        risultato = elimina_libro(self.app.root_progetto, slug)
        if not risultato["ok"]:
            messagebox.showerror(
                "Errore durante l'eliminazione",
                "\n".join(risultato["errori"]),
            )
            return

        messagebox.showinfo(
            "Libro eliminato",
            f"Il libro '{slug}' e' stato eliminato.",
        )
        self._ricarica_elenco()