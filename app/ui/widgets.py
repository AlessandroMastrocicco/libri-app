# -*- coding: utf-8 -*-
"""Widget riusabili."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from app.ui import tema


# ----------------------------------------------------------------------
# Contenitori
# ----------------------------------------------------------------------

def card(parent, **kwargs) -> ctk.CTkFrame:
    opts = {"corner_radius": 12, "fg_color": tema.BG_CARD}
    opts.update(kwargs)
    return ctk.CTkFrame(parent, **opts)


def separatore(parent, height: int = 1) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, height=height, fg_color=tema.BG_INPUT)


# ----------------------------------------------------------------------
# Testo
# ----------------------------------------------------------------------

def titolo(parent, testo: str, **kwargs) -> ctk.CTkLabel:
    opts = {
        "text": testo,
        "font": ctk.CTkFont(size=22, weight="bold"),
        "anchor": "w",
        "text_color": tema.TESTO,
    }
    opts.update(kwargs)
    return ctk.CTkLabel(parent, **opts)


def sottotitolo(parent, testo: str, **kwargs) -> ctk.CTkLabel:
    opts = {
        "text": testo,
        "font": ctk.CTkFont(size=13),
        "anchor": "w",
        "justify": "left",
        "text_color": tema.TESTO_TENUE,
        "wraplength": 800,
    }
    opts.update(kwargs)
    return ctk.CTkLabel(parent, **opts)


def etichetta(parent, testo: str, **kwargs) -> ctk.CTkLabel:
    opts = {
        "text": testo,
        "font": ctk.CTkFont(size=13, weight="bold"),
        "anchor": "w",
        "text_color": tema.TESTO,
    }
    opts.update(kwargs)
    return ctk.CTkLabel(parent, **opts)


def messaggio(parent, testo: str = "",
              colore: str = tema.TESTO_TENUE) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=testo,
        font=ctk.CTkFont(size=12),
        anchor="w",
        justify="left",
        wraplength=700,
        text_color=colore,
    )


# ----------------------------------------------------------------------
# Pulsanti
# ----------------------------------------------------------------------

def bottone_primario(parent, testo: str,
                     command: Callable[[], None],
                     **kwargs) -> ctk.CTkButton:
    opts = {
        "text": testo,
        "height": 40,
        "corner_radius": 8,
        "fg_color": tema.PRIMARIO,
        "hover_color": tema.PRIMARIO_HOVER,
        "font": ctk.CTkFont(size=14, weight="bold"),
        "command": command,
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


def bottone_secondario(parent, testo: str,
                       command: Callable[[], None],
                       **kwargs) -> ctk.CTkButton:
    opts = {
        "text": testo,
        "height": 36,
        "corner_radius": 8,
        "fg_color": tema.NEUTRO,
        "hover_color": tema.NEUTRO_HOVER,
        "font": ctk.CTkFont(size=13),
        "command": command,
    }
    opts.update(kwargs)
    return ctk.CTkButton(parent, **opts)


# ----------------------------------------------------------------------
# Campi form
# ----------------------------------------------------------------------

class CampoTesto(ctk.CTkFrame):
    """Etichetta + entry, con placeholder."""

    def __init__(self, parent, etichetta_testo: str,
                 placeholder: str = "", width: int = 320):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)

        etichetta(self, etichetta_testo).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )

        self.entry = ctk.CTkEntry(
            self,
            width=width,
            height=36,
            corner_radius=6,
            fg_color=tema.BG_INPUT,
            border_color=tema.BG_INPUT_HOVER,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=13),
        )
        self.entry.grid(row=1, column=0, sticky="ew")

    def get(self) -> str:
        return self.entry.get()

    def set(self, valore: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, valore)

    def focus(self):
        self.entry.focus_set()