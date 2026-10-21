# -*- coding: utf-8 -*-
"""
capitolo.py - Vista di un capitolo.
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
from app.core.capitolo import (
    informazioni_eliminazione_capitolo,
    elimina_capitolo,
    leggi_titolo_capitolo,
    percorso_capitolo,
)
from app.core.libro import formatta_dimensione
from app.core.paragrafo import (
    elenca_paragrafi,
    informazioni_eliminazione_paragrafo,
    elimina_paragrafo,
    riepilogo_paragrafo,
)


class SchermataCapitolo(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str, cap: int):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug
        self.cap = cap

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

        titolo_cap = leggi_titolo_capitolo(
            self.app.root_progetto, self.slug, self.cap
        )
        intestazione = (f"Capitolo {self.cap:02d} — {titolo_cap}"
                        if titolo_cap else f"Capitolo {self.cap:02d}")

        titolo(header, intestazione).grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        sottotitolo(header, f"libro: {self.slug}").grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 14)
        )

        ctk.CTkButton(
            header,
            text="  Elimina capitolo",
            width=180, height=34,
            corner_radius=8,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._elimina_capitolo,
        ).grid(row=0, column=1, rowspan=2, padx=(18, 6), pady=14, sticky="e")

        bottone_secondario(
            header, "  Torna al libro",
            command=lambda: self.app.mostra_modifica_libro(self.slug),
            width=170, height=34,
        ).grid(row=0, column=2, rowspan=2, padx=(0, 18), pady=14, sticky="e")

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _build_azioni(self):
        azioni = ctk.CTkFrame(self, fg_color="transparent")
        azioni.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 8))

        bottone_primario(
            azioni, "  Nuovo paragrafo",
            command=self._apri_crea_paragrafo,
            width=180,
        ).pack(side="left")

        bottone_secondario(
            azioni, "  Apri cartella capitolo",
            command=self._apri_cartella_capitolo,
            width=200,
        ).pack(side="left", padx=(8, 0))

        bottone_secondario(
            azioni, "  Ricarica elenco",
            command=self._ricarica_elenco,
            width=160,
        ).pack(side="left", padx=(8, 0))

    # ------------------------------------------------------------------
    # Elenco paragrafi
    # ------------------------------------------------------------------

    def _build_elenco(self):
        wrap = card(self)
        wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 24))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            wrap, text="Paragrafi ed Esercizi del capitolo",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

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

        par_ids = elenca_paragrafi(
            self.app.root_progetto, self.slug, self.cap
        )
        if not par_ids:
            ctk.CTkLabel(
                self.scroll,
                text="(nessun paragrafo in questo capitolo)\n"
                     "Usa «Nuovo paragrafo» per crearne uno.",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=13),
                anchor="w", justify="left",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=12)
            return

        for i, par_id in enumerate(par_ids):
            self._riga_paragrafo(i, par_id)

    def _riga_paragrafo(self, indice: int, par_id: str):
        riep = riepilogo_paragrafo(
            self.app.root_progetto, self.slug, self.cap, par_id
        )
        titolo_par = (riep["titolo"] if riep else f"{self.cap}.{par_id}")

        is_ex = par_id.endswith("_esercizi")
        num_str = par_id.replace("_esercizi", "")
        
        if is_ex:
            etichetta_badge = "EX"
            colore_badge = tema.INFO
        else:
            etichetta_badge = f"{self.cap}.{num_str}"
            colore_badge = tema.PRIMARIO

        riga = ctk.CTkFrame(
            self.scroll, fg_color=tema.BG_CARD,
            corner_radius=8, border_width=1, border_color=tema.BG_INPUT_HOVER,
        )
        riga.grid(row=indice, column=0, sticky="ew", pady=3)
        riga.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            riga, text=f"  {etichetta_badge}  ",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=colore_badge, corner_radius=6,
            text_color="white", width=60,
        ).grid(row=0, column=1, rowspan=2, sticky="w", padx=(10, 8), pady=10)

        titolo_breve = titolo_par
        if len(titolo_breve) > 70:
            titolo_breve = titolo_breve[:67] + "..."
        
        ctk.CTkLabel(
            riga, text=titolo_breve, font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w", justify="left", text_color=tema.TESTO, wraplength=440,
        ).grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=(10, 2))

        # Sottotitolo con informazioni (righe, origine teoria)
        info_extra = []
        if riep: info_extra.append(f"{riep['righe']} righe")
        
        if is_ex and riep and riep.get("teoria_origine") and riep["teoria_origine"] != num_str:
            info_extra.append(f"Rif. Teoria: {self.cap}.{riep['teoria_origine']}")

        ctk.CTkLabel(
            riga, text=" · ".join(info_extra), font=ctk.CTkFont(size=11),
            anchor="w", justify="left", text_color=tema.TESTO_MOLTO_TENUE, wraplength=650,
        ).grid(row=1, column=2, sticky="ew", padx=(0, 8), pady=(0, 10))

        bottone_secondario(
            riga, "Modifica",
            command=lambda k=par_id: self._apri_paragrafo(k),
            width=100, height=32,
        ).grid(row=0, column=3, rowspan=2, sticky="e", padx=(4, 4), pady=8)

        ctk.CTkButton(
            riga, text="Anteprima",
            width=110, height=32,
            corner_radius=8,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=12),
            command=lambda k=par_id: self._apri_anteprima(k),
        ).grid(row=0, column=4, rowspan=2,
               sticky="e", padx=(0, 4), pady=8)

        ctk.CTkButton(
            riga, text="Elimina",
            width=100, height=32,
            corner_radius=8,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda k=par_id: self._elimina_paragrafo(k),
        ).grid(row=0, column=5, rowspan=2,
               sticky="e", padx=(0, 10), pady=8)

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _apri_crea_paragrafo(self):
        self.app.mostra_crea_paragrafo(self.slug, self.cap)

    def _apri_paragrafo(self, par_id: str):
        self.app.mostra_crea_paragrafo(self.slug, self.cap, par_id)

    def _apri_anteprima(self, par_id: str):
        self.app.mostra_lettore(self.slug, self.cap, par_id)

    def _apri_cartella_capitolo(self):
        p = percorso_capitolo(self.app.root_progetto, self.slug, self.cap)
        self._apri(p)

    def _apri(self, percorso):
        if not percorso or not percorso.is_dir(): return
        try:
            if sys.platform.startswith("win"): os.startfile(str(percorso))
            elif sys.platform == "darwin": subprocess.run(["open", str(percorso)], check=False)
            else: subprocess.run(["xdg-open", str(percorso)], check=False)
        except Exception: pass

    # ------------------------------------------------------------------
    # Eliminazione paragrafo
    # ------------------------------------------------------------------

    def _elimina_paragrafo(self, par_id: str):
        info = informazioni_eliminazione_paragrafo(
            self.app.root_progetto, self.slug, self.cap, par_id
        )
        if not info["esiste"]:
            messagebox.showerror("Paragrafo non trovato", f"Il paragrafo {self.cap}.{par_id} non esiste piu'.")
            self._ricarica_elenco()
            return
        nome = f"{self.cap}.{par_id} — {info['titolo']}"
        dim = formatta_dimensione(info["dimensione_byte"])
        testo_1 = f"Stai per eliminare DEFINITIVAMENTE il paragrafo:\n\n    {nome}\n\nDimensione: {dim}\n\nQuesta operazione NON e' reversibile.\n\nContinuare?"
        if not messagebox.askyesno("Elimina paragrafo - conferma 1 di 2", testo_1, icon="warning", default="no"): return
        testo_2 = f"Conferma finale.\n\nSei assolutamente sicuro di voler eliminare\nil paragrafo {self.cap}.{par_id}?"
        if not messagebox.askyesno("Elimina paragrafo - conferma 2 di 2", testo_2, icon="warning", default="no"): return
        
        risultato = elimina_paragrafo(self.app.root_progetto, self.slug, self.cap, par_id)
        if not risultato["ok"]:
            messagebox.showerror("Errore durante l'eliminazione", "\n".join(risultato["errori"]) or "Errore sconosciuto.")
            return
        try:
            from app.core.render_paragrafo import invalida_cache_paragrafo
            invalida_cache_paragrafo(self.app.root_progetto, self.slug, self.cap, par_id)
        except Exception: pass
        messagebox.showinfo("Paragrafo eliminato", f"Il paragrafo {self.cap}.{par_id} e' stato eliminato.")
        self._ricarica_elenco()

    # ------------------------------------------------------------------
    # Eliminazione capitolo
    # ------------------------------------------------------------------

    def _elimina_capitolo(self):
        info = informazioni_eliminazione_capitolo(self.app.root_progetto, self.slug, self.cap)
        if not info["esiste"]:
            messagebox.showerror("Capitolo non trovato", f"Il capitolo {self.cap:02d} non esiste piu'.")
            self.app.mostra_modifica_libro(self.slug)
            return
        titolo_cap = leggi_titolo_capitolo(self.app.root_progetto, self.slug, self.cap)
        nome_esteso = f"Capitolo {self.cap:02d} - {titolo_cap}" if titolo_cap else f"Capitolo {self.cap:02d}"
        dim = formatta_dimensione(info["dimensione_byte"])
        testo_1 = f"Stai per eliminare DEFINITIVAMENTE il capitolo:\n\n    {nome_esteso}\n\nCartella:\n    {info['path']}\n\nVerranno cancellati:\n    - {info['n_paragrafi']} paragrafi\n    - la cache interna del capitolo\n\nDimensione totale: {dim}\n\nQuesta operazione NON e' reversibile.\n\nContinuare?"
        if not messagebox.askyesno("Elimina capitolo - conferma 1 di 2", testo_1, icon="warning", default="no"): return
        if not messagebox.askyesno("Elimina capitolo - conferma 2 di 2", f"Sei assolutamente sicuro di voler eliminare\nil {nome_esteso}?", icon="warning", default="no"): return
        
        risultato = elimina_capitolo(self.app.root_progetto, self.slug, self.cap)
        if not risultato["ok"]:
            messagebox.showerror("Errore durante l'eliminazione", "\n".join(risultato["errori"]) or "Errore sconosciuto.")
            return
        messagebox.showinfo("Capitolo eliminato", f"Il {nome_esteso} e' stato eliminato.")
        self.app.mostra_modifica_libro(self.slug)