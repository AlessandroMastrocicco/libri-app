# -*- coding: utf-8 -*-
"""
modifica_libro.py - Hub di modifica del contenuto di un libro.

Punto d'ingresso per:
- creare un nuovo capitolo
- aprire un capitolo esistente per modificarne i paragrafi
- eliminare un capitolo
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
from app.core.capitolo import (
    elenca_capitoli,
    elimina_capitolo,
    informazioni_eliminazione_capitolo,
    leggi_titolo_capitolo,
)
from app.core.libro import (
    formatta_dimensione,
    percorso_libro,
)
from app.core.paragrafo import elenca_paragrafi


class SchermataModificaLibro(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_azioni()
        self._build_elenco()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        titolo(header, f"Modifica libro — {self.slug}").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        sottotitolo(
            header,
            "Crea nuovi capitoli oppure apri un capitolo esistente "
            "per gestirne i paragrafi.",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=2, padx=18, pady=14, sticky="e")

        bottone_secondario(
            btns, "  Torna al libro",
            command=lambda: self.app.mostra_libro(self.slug),
            width=170, height=34,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _build_azioni(self):
        azioni = ctk.CTkFrame(self, fg_color="transparent")
        azioni.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))
        azioni.grid_columnconfigure(2, weight=1)

        bottone_primario(
            azioni,
            "  Nuovo capitolo",
            command=self._apri_nuovo_capitolo,
            width=180,
        ).grid(row=0, column=0, sticky="w")

        bottone_secondario(
            azioni,
            "  Modifica capitolo (seleziona sotto)",
            command=self._suggerisci_modifica,
            width=290,
        ).grid(row=0, column=1, sticky="w", padx=(8, 0))

        bottone_secondario(
            azioni,
            "  Ricarica elenco",
            command=self._ricarica_elenco,
            width=160,
        ).grid(row=0, column=2, sticky="w", padx=(8, 0))

    # ------------------------------------------------------------------
    # Elenco capitoli
    # ------------------------------------------------------------------

    def _build_elenco(self):
        wrap = card(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        sottotitolo(wrap, "Capitoli esistenti").grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4)
        )

        self.scroll = ctk.CTkScrollableFrame(
            wrap, corner_radius=8, fg_color=tema.BG_INPUT
        )
        self.scroll.grid(row=1, column=0, sticky="nsew",
                         padx=14, pady=(0, 14))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._ricarica_elenco()

    def _ricarica_elenco(self):
        for w in self.scroll.winfo_children():
            w.destroy()

        numeri = elenca_capitoli(self.app.root_progetto, self.slug)

        if not numeri:
            ctk.CTkLabel(
                self.scroll,
                text="(nessun capitolo: usa «Nuovo capitolo» per iniziare)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=13),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        for i, n in enumerate(numeri):
            self._riga_capitolo(i, n)

    def _riga_capitolo(self, indice: int, n: int):
        riga = ctk.CTkFrame(self.scroll, fg_color="transparent")
        riga.grid(row=indice, column=0, sticky="ew", pady=3)
        riga.grid_columnconfigure(0, weight=1)

        titolo_cap = leggi_titolo_capitolo(
            self.app.root_progetto, self.slug, n
        )
        if titolo_cap:
            etichetta = f"Capitolo {n:02d} — {titolo_cap}"
        else:
            etichetta = f"Capitolo {n:02d}"

        n_par = len(elenca_paragrafi(
            self.app.root_progetto, self.slug, n
        ))
        meta = f"{n_par} paragrafi" if n_par else "nessun paragrafo"

        ctk.CTkButton(
            riga,
            text=f"  {etichetta}",
            height=40,
            corner_radius=6,
            fg_color=tema.BG_INPUT_HOVER,
            hover_color=tema.NEUTRO_HOVER,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda k=n: self.app.mostra_capitolo(self.slug, k),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        ctk.CTkLabel(
            riga, text=meta,
            text_color=tema.TESTO_MOLTO_TENUE,
            font=ctk.CTkFont(size=11),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))

        bottone_secondario(
            riga,
            "Modifica",
            command=lambda k=n: self.app.mostra_capitolo(self.slug, k),
            width=110, height=32,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(4, 2), pady=4)

        self.btn_elimina_cap = ctk.CTkButton(
            riga,
            text="Elimina",
            width=100, height=32,
            corner_radius=8,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda k=n: self._elimina_capitolo(k),
        )
        self.btn_elimina_cap.grid(row=0, column=2, rowspan=2, sticky="e",
                                  padx=(2, 4), pady=4)

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _apri_nuovo_capitolo(self):
        self.app.mostra_crea_capitolo(self.slug)

    def _suggerisci_modifica(self):
        if not elenca_capitoli(self.app.root_progetto, self.slug):
            messagebox.showinfo(
                "Nessun capitolo",
                "Non ci sono capitoli da modificare.\n"
                "Crea prima un nuovo capitolo.",
            )
            return
        messagebox.showinfo(
            "Modifica capitolo",
            "Seleziona un capitolo dalla lista qui sotto, "
            "oppure clicca «Modifica» accanto a quello desiderato.",
        )

    def _elimina_capitolo(self, n: int):
        info = informazioni_eliminazione_capitolo(
            self.app.root_progetto, self.slug, n
        )
        if not info["esiste"]:
            messagebox.showerror(
                "Capitolo non trovato",
                f"Il capitolo {n:02d} non esiste piu'.",
            )
            self._ricarica_elenco()
            return

        titolo_cap = leggi_titolo_capitolo(
            self.app.root_progetto, self.slug, n
        )
        nome_esteso = (f"Capitolo {n:02d} - {titolo_cap}"
                       if titolo_cap else f"Capitolo {n:02d}")
        dim = formatta_dimensione(info["dimensione_byte"])

        testo_1 = (
            f"Stai per eliminare DEFINITIVAMENTE il capitolo:\n\n"
            f"    {nome_esteso}\n\n"
            f"Cartella:\n"
            f"    {info['path']}\n\n"
            f"Verranno cancellati:\n"
            f"    - {info['n_paragrafi']} paragrafi\n"
            f"    - {info['n_tracking']} file di tracciamento\n"
            f"    - la cache interna del capitolo\n\n"
            f"Dimensione totale: {dim}\n\n"
            f"Questa operazione NON e' reversibile.\n\n"
            f"Continuare?"
        )

        if not messagebox.askyesno(
            "Elimina capitolo - conferma 1 di 2",
            testo_1,
            icon="warning",
            default="no",
        ):
            return

        testo_2 = (
            f"Conferma finale.\n\n"
            f"Sei assolutamente sicuro di voler eliminare\n"
            f"il {nome_esteso}?"
        )
        if not messagebox.askyesno(
            "Elimina capitolo - conferma 2 di 2",
            testo_2,
            icon="warning",
            default="no",
        ):
            return

        risultato = elimina_capitolo(
            self.app.root_progetto, self.slug, n
        )

        if not risultato["ok"]:
            messagebox.showerror(
                "Errore durante l'eliminazione",
                "\n".join(risultato["errori"]) or "Errore sconosciuto.",
            )
            return

        messagebox.showinfo(
            "Capitolo eliminato",
            f"Il {nome_esteso} e' stato eliminato.",
        )
        self._ricarica_elenco()