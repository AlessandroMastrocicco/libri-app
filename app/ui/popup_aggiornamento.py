# -*- coding: utf-8 -*-
"""
popup_aggiornamento.py - Popup per notificare la disponibilità di una nuova versione.
"""

from __future__ import annotations

import webbrowser
import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import bottone_primario, bottone_secondario, card
from app.version import __version__


class PopupAggiornamento(ctk.CTkToplevel):
    def __init__(self, parent, dati_aggiornamento: dict):
        super().__init__(parent)

        self.dati = dati_aggiornamento
        self.url_download = self.dati.get("url", "")

        self.title("Aggiornamento disponibile")
        self.geometry("600x450")
        self.resizable(False, False)
        self.configure(fg_color=tema.BG_APP)

        try:
            self.transient(parent)
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        box = card(self)
        box.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(2, weight=1)

        # Header
        ctk.CTkLabel(
            box, text="🎉 Nuova versione disponibile!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=tema.PRIMARIO, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Info versione
        v_remota = self.dati.get("version", "?")
        ctk.CTkLabel(
            box,
            text=f"Stai usando la versione {__version__}. L'ultima versione è la {v_remota}.",
            font=ctk.CTkFont(size=13),
            text_color=tema.TESTO_TENUE, anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        # Changelog
        ctk.CTkLabel(
            box, text="Novità di questa versione:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=tema.TESTO, anchor="w",
        ).grid(row=2, column=0, sticky="nw", padx=20, pady=(10, 4))

        self.txt_changelog = ctk.CTkTextbox(
            box,
            font=ctk.CTkFont(size=13),
            wrap="word",
            fg_color=tema.BG_INPUT,
            text_color=tema.TESTO,
        )
        self.txt_changelog.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.txt_changelog.insert("1.0", self.dati.get("changelog", ""))
        self.txt_changelog.configure(state="disabled")

        # Footer
        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=20, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        bottone_secondario(
            footer, "  Più tardi", command=self.destroy, width=120, height=38,
        ).grid(row=0, column=1, sticky="e", padx=(0, 10))

        bottone_primario(
            footer, "  Scarica aggiornamento", command=self._scarica,
            width=220, height=38,
        ).grid(row=0, column=2, sticky="e")

        self._centra_su_parent(parent)
        self.after(80, self.lift)
        self.after(80, self.focus_force)

    def _scarica(self):
        if self.url_download:
            webbrowser.open(self.url_download)
        self.destroy()

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