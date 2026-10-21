# -*- coding: utf-8 -*-
"""
libro_dettaglio.py - Vista di un singolo libro.
"""

from __future__ import annotations

import os
import subprocess
import sys
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
    elimina_libro,
    formatta_dimensione,
    informazioni_dashboard,
    informazioni_eliminazione,
    percorso_libro,
    registra_accesso,
)
from app.core.capitolo import (
    elenca_capitoli,
    leggi_titolo_capitolo,
    percorso_capitolo,
)
from app.core.paragrafo import elenca_paragrafi


class SchermataLibro(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        registra_accesso(self.app.root_progetto, self.slug)

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        self._build_header()
        self._build_azioni()
        self._build_dashboard()
        self._build_elenco()

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        titolo(header, self.slug).grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        percorso = percorso_libro(self.app.root_progetto, self.slug)
        sottotitolo(header, str(percorso)).grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 14)
        )

        ctk.CTkButton(
            header,
            text="  Elimina libro",
            width=160, height=34,
            corner_radius=8,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._elimina_libro,
        ).grid(row=0, column=1, rowspan=2, padx=(18, 6), pady=14, sticky="e")

        bottone_secondario(
            header, "  Home", command=self.app.mostra_home,
            width=100, height=34,
        ).grid(row=0, column=2, rowspan=2, padx=(0, 18), pady=14, sticky="e")

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _build_azioni(self):
        azioni = ctk.CTkFrame(self, fg_color="transparent")
        azioni.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        bottone_primario(
            azioni,
            "  Modifica libro",
            command=self._apri_modifica_libro,
            width=170,
        ).pack(side="left")

        bottone_secondario(
            azioni,
            "  Estrattore slide",
            command=self._apri_estrattore_slide,
            width=180,
        ).pack(side="left", padx=(8, 0))

        bottone_secondario(
            azioni,
            "  Gestione immagini",
            command=self._apri_gestione_immagini,
            width=180,
        ).pack(side="left", padx=(8, 0))

        bottone_secondario(
            azioni,
            "  Apri lettore",
            command=lambda: self.app.mostra_lettore(self.slug),
            width=160,
        ).pack(side="left", padx=(8, 0))

        bottone_secondario(
            azioni,
            "  Apri cartella",
            command=self._apri_cartella_libro,
            width=160,
        ).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    def _build_dashboard(self):
        wrap = card(self)
        wrap.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_columnconfigure(1, weight=1)
        wrap.grid_columnconfigure(2, weight=1)
        wrap.grid_columnconfigure(3, weight=1)

        info = informazioni_dashboard(
            self.app.root_progetto, self.slug
        )

        testata = ctk.CTkFrame(wrap, fg_color="transparent")
        testata.grid(row=0, column=0, columnspan=4, sticky="ew",
                     padx=14, pady=(12, 4))
        testata.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            testata, text="Panoramica",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, sticky="w")

        if info.get("titolo_visualizzato") or info.get("autore"):
            sottotitolo(
                testata,
                self._componi_sottotitolo(info),
            ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        self._card_dashboard(
            wrap, col=0, etichetta="Pagine",
            valore=str(info["n_pagine"]),
            colore_valore=tema.PRIMARIO,
            dettaglio=f"{info['n_paragrafi']} paragrafi di teoria",
        )
        self._card_dashboard(
            wrap, col=1, etichetta="Capitoli",
            valore=str(info["n_capitoli"]),
            colore_valore=tema.INFO,
            dettaglio="suddivisioni del libro",
        )
        self._card_dashboard(
            wrap, col=2, etichetta="Ultimo accesso",
            valore=self._formatta_ultimo_accesso(info.get("ultimo_accesso")),
            colore_valore=tema.TESTO,
            dettaglio="data e ora",
            valore_piccolo=True,
        )
        self._card_dashboard(
            wrap, col=3, etichetta="Dimensione",
            valore=info["dimensione_str"],
            colore_valore=tema.TESTO,
            dettaglio=(f"creato il {info['data_creazione']}" if info.get("data_creazione") else ""),
            valore_piccolo=True,
        )

    def _card_dashboard(self, parent, col: int, etichetta: str, valore: str, colore_valore: str, dettaglio: str = "", valore_piccolo: bool = False):
        card_v = ctk.CTkFrame(parent, corner_radius=10, fg_color=tema.BG_INPUT)
        card_v.grid(row=1, column=col, sticky="nsew", padx=(14 if col == 0 else 4, 14 if col == 3 else 4), pady=(4, 14))

        ctk.CTkLabel(card_v, text=etichetta, font=ctk.CTkFont(size=11, weight="bold"), anchor="w", text_color=tema.TESTO_MOLTO_TENUE).pack(anchor="w", padx=14, pady=(12, 2))
        ctk.CTkLabel(card_v, text=valore, font=ctk.CTkFont(size=16 if valore_piccolo else 26, weight="bold"), anchor="w", text_color=colore_valore, justify="left", wraplength=200).pack(anchor="w", padx=14, pady=(0, 2))
        if dettaglio:
            ctk.CTkLabel(card_v, text=dettaglio, font=ctk.CTkFont(size=10), anchor="w", text_color=tema.TESTO_MOLTO_TENUE, justify="left", wraplength=200).pack(anchor="w", padx=14, pady=(0, 12))
        else:
            ctk.CTkFrame(card_v, height=12, fg_color="transparent").pack()

    def _componi_sottotitolo(self, info: dict) -> str:
        pezzi = []
        if info.get("titolo_visualizzato"): pezzi.append(info["titolo_visualizzato"])
        if info.get("autore"): pezzi.append(f"di {info['autore']}")
        return "   -   ".join(pezzi)

    def _formatta_ultimo_accesso(self, dt) -> str:
        if dt is None: return "prima volta"
        from datetime import datetime as _dt
        giorni = (_dt.now() - dt).days
        suffisso = "oggi" if giorni == 0 else "ieri" if giorni == 1 else f"{giorni} giorni fa"
        return f"{dt.strftime('%Y-%m-%d')}\n{dt.strftime('%H:%M')}  ({suffisso})"

    # ------------------------------------------------------------------
    # Elenco capitoli
    # ------------------------------------------------------------------

    def _build_elenco(self):
        wrap = card(self)
        wrap.grid(row=4, column=0, sticky="nsew", padx=24, pady=(0, 24))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        sottotitolo(wrap, "Capitoli del libro").grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 4)
        )

        self.scroll = ctk.CTkScrollableFrame(
            wrap, corner_radius=8, fg_color=tema.BG_INPUT,
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
            ctk.CTkLabel(self.scroll, text="(nessun capitolo: usa «Modifica libro» per crearne)", text_color=tema.TESTO_MOLTO_TENUE, font=ctk.CTkFont(size=13), anchor="w").grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        for i, n in enumerate(numeri):
            self._riga_capitolo(i, n)

    def _riga_capitolo(self, indice: int, n: int):
        riga = ctk.CTkFrame(self.scroll, fg_color="transparent")
        riga.grid(row=indice, column=0, sticky="ew", pady=3)
        riga.grid_columnconfigure(0, weight=1)

        titolo_cap = leggi_titolo_capitolo(self.app.root_progetto, self.slug, n)
        etichetta = f"Capitolo {n:02d} - {titolo_cap}" if titolo_cap else f"Capitolo {n:02d}"

        n_par = len(elenca_paragrafi(self.app.root_progetto, self.slug, n))
        meta = f"{n_par} paragrafi" if n_par else "nessun paragrafo"

        ctk.CTkButton(
            riga, text=f"  {etichetta}", height=38, corner_radius=6,
            fg_color=tema.BG_INPUT_HOVER, hover_color=tema.NEUTRO_HOVER,
            anchor="w", font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda k=n: self.app.mostra_capitolo(self.slug, k),
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))

        ctk.CTkLabel(riga, text=meta, text_color=tema.TESTO_MOLTO_TENUE, font=ctk.CTkFont(size=11), anchor="w").grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))

        bottone_secondario(riga, "Apri cartella", command=lambda k=n: self._apri_cartella_capitolo(k), width=130, height=30).grid(row=0, column=1, rowspan=2, sticky="e", padx=4, pady=4)

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _apri_modifica_libro(self):
        self.app.mostra_modifica_libro(self.slug)

    def _apri_estrattore_slide(self):
        self.app.mostra_estrattore_slide(self.slug)

    def _apri_gestione_immagini(self):
        self.app.mostra_gestione_immagini(self.slug)

    def _apri_cartella_libro(self):
        self._apri(percorso_libro(self.app.root_progetto, self.slug))

    def _apri_cartella_capitolo(self, n: int):
        self._apri(percorso_capitolo(self.app.root_progetto, self.slug, n))

    def _apri(self, percorso):
        if not percorso or not percorso.is_dir(): return
        try:
            if sys.platform.startswith("win"): os.startfile(str(percorso))
            elif sys.platform == "darwin": subprocess.run(["open", str(percorso)], check=False)
            else: subprocess.run(["xdg-open", str(percorso)], check=False)
        except Exception: pass

    def _elimina_libro(self):
        info = informazioni_eliminazione(self.app.root_progetto, self.slug)
        if not info["esiste"]:
            messagebox.showerror("Libro non trovato", f"Il libro '{self.slug}' non esiste piu'.")
            self.app.mostra_home()
            return
        dim = formatta_dimensione(info["dimensione_byte"])
        testo_1 = f"Stai per eliminare DEFINITIVAMENTE il libro:\n\n    {self.slug}\n\nVerranno cancellati:\n    - {info['n_capitoli']} capitoli\n    - {info['n_paragrafi']} paragrafi\n\nDimensione totale: {dim}\n\nQuesta operazione NON e' reversibile. Continuare?"
        if not messagebox.askyesno("Elimina libro - conferma 1 di 2", testo_1, icon="warning", default="no"): return
        if not messagebox.askyesno("Elimina libro - conferma 2 di 2", f"Sei sicuro di voler eliminare '{self.slug}' e tutti i suoi dati?", icon="warning", default="no"): return
        risultato = elimina_libro(self.app.root_progetto, self.slug)
        if not risultato["ok"]:
            messagebox.showerror("Errore durante l'eliminazione", "\n".join(risultato["errori"]))
            return
        messagebox.showinfo("Libro eliminato", f"Il libro '{self.slug}' e' stato eliminato.")
        self.app.mostra_home()