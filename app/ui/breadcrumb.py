# -*- coding: utf-8 -*-
"""
breadcrumb.py - Barra di navigazione stile filesystem.

Una lista di segmenti, ognuno con una label e una callback opzionale.
L'ultimo segmento e' quello corrente: mostrato in grassetto e non
cliccabile. I segmenti precedenti sono cliccabili.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from app.ui import tema


# Voce = (label: str, callback: Callable | None)
Voce = tuple[str, Callable[[], None] | None]


class Breadcrumb(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent", height=36)
        self._voci: list[Voce] = []
        self._bottoni: list = []

        # pack_propagate disabilitato per mantenere altezza fissa
        self.pack_propagate(False)

    def imposta(self, voci: list[Voce]):
        """Sostituisce la breadcrumb corrente."""
        self._voci = list(voci)
        self._ridisegna()

    def _ridisegna(self):
        for w in self.winfo_children():
            w.destroy()
        self._bottoni.clear()

        if not self._voci:
            return

        for i, (label, callback) in enumerate(self._voci):
            ultimo = (i == len(self._voci) - 1)

            if ultimo:
                # segmento corrente: label semplice, in grassetto
                lbl = ctk.CTkLabel(
                    self,
                    text=label,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=tema.TESTO,
                    anchor="w",
                )
                lbl.pack(side="left", padx=(0, 4))
                self._bottoni.append(lbl)
            else:
                # segmento navigabile: pulsante piatto
                btn = ctk.CTkButton(
                    self,
                    text=label,
                    height=26,
                    fg_color="transparent",
                    hover_color=tema.BG_INPUT_HOVER,
                    text_color=tema.TESTO_TENUE,
                    font=ctk.CTkFont(size=13),
                    anchor="w",
                    command=(callback or (lambda: None)),
                )
                btn.pack(side="left", padx=(0, 2))
                self._bottoni.append(btn)

            # separatore "/" tra le voci
            if not ultimo:
                ctk.CTkLabel(
                    self,
                    text="/",
                    font=ctk.CTkFont(size=13),
                    text_color=tema.TESTO_MOLTO_TENUE,
                    anchor="w",
                ).pack(side="left", padx=(2, 4))