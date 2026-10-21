# -*- coding: utf-8 -*-
"""
crea_libro.py - Wizard di creazione nuovo libro.
"""

from __future__ import annotations

import os
import subprocess
import sys
from tkinter import messagebox

import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import (
    CampoTesto,
    bottone_primario,
    bottone_secondario,
    card,
    etichetta,
    messaggio,
    sottotitolo,
    titolo,
)
from app.core.libro import (
    SOTTOCARTELLE,
    crea_libro,
    libro_esiste,
    percorso_libro,
    slugifica,
    slug_valido,
)
from app.core.pattern_libro import PATTERN_LIBRO, PATTERN_RISORSE_EXTRA


# ======================================================================
# Popup "libro gia' esistente"
# ======================================================================

class DialogLibroEsistente(ctk.CTkToplevel):
    """
    Popup modale che chiede un nome diverso quando lo slug e' gia' in uso.

    Ritorna (via attributo `risultato`) il nuovo slug scelto, oppure None
    se l'utente annulla.
    """

    def __init__(self, parent, root_progetto, slug_attuale: str):
        super().__init__(parent)

        self.root_progetto = root_progetto
        self.slug_attuale = slug_attuale
        self.risultato: str | None = None

        self.title("Libro gia' esistente")
        self.geometry("520x300")
        self.configure(fg_color=tema.BG_APP)
        self.resizable(False, False)

        try:
            self.transient(parent)
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)

        # header
        ctk.CTkLabel(
            self,
            text="Libro gia' esistente",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", text_color=tema.ERRORE,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))

        ctk.CTkLabel(
            self,
            text=f"Esiste gia' una cartella con il nome:\n"
                 f"    libri/{slug_attuale}/\n\n"
                 f"Scegli un nome diverso per il nuovo libro.",
            font=ctk.CTkFont(size=12),
            anchor="w", justify="left",
            text_color=tema.TESTO_TENUE,
            wraplength=480,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 14))

        # campo nuovo nome
        ctk.CTkLabel(
            self, text="Nuovo nome cartella (slug)",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 4))

        self.entry = ctk.CTkEntry(
            self,
            height=36,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=tema.BG_INPUT,
        )
        self.entry.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 6))
        self.entry.insert(0, slug_attuale)
        self.entry.bind("<KeyRelease>", lambda e: self._valida())
        self.entry.bind("<Return>", lambda e: self._conferma())

        self.lbl_errore = ctk.CTkLabel(
            self, text="",
            font=ctk.CTkFont(size=11),
            anchor="w", justify="left",
            text_color=tema.ERRORE,
            wraplength=480,
        )
        self.lbl_errore.grid(row=4, column=0, sticky="ew",
                             padx=20, pady=(0, 8))

        # pulsanti
        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, sticky="e", padx=20, pady=(4, 20))

        ctk.CTkButton(
            btns, text="  Annulla",
            width=110, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._annulla,
        ).pack(side="left", padx=(0, 8))

        self.btn_ok = ctk.CTkButton(
            btns, text="  Prova nome",
            width=140, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._conferma,
        )
        self.btn_ok.pack(side="left")

        # posiziona al centro del parent
        self._centra_su_parent(parent)

        self.after(80, self.entry.focus_set)
        self.after(80, lambda: self.entry.select_range(0, "end"))
        self.after(80, self.lift)
        self.after(80, self.focus_force)

        self._valida()

    # ------------------------------------------------------------------

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

    def _valida(self) -> bool:
        nuovo = self.entry.get().strip()

        if not nuovo:
            self.lbl_errore.configure(text="Il nome e' obbligatorio.")
            self.btn_ok.configure(state="disabled")
            return False

        if nuovo == self.slug_attuale:
            self.lbl_errore.configure(
                text="Questo nome e' ancora in uso. Scegline un altro."
            )
            self.btn_ok.configure(state="disabled")
            return False

        ok, motivo = slug_valido(nuovo)
        if not ok:
            self.lbl_errore.configure(text=motivo)
            self.btn_ok.configure(state="disabled")
            return False

        if libro_esiste(self.root_progetto, nuovo):
            self.lbl_errore.configure(
                text=f"Anche '{nuovo}' esiste gia'. Scegline un altro."
            )
            self.btn_ok.configure(state="disabled")
            return False

        self.lbl_errore.configure(text="")
        self.btn_ok.configure(state="normal")
        return True

    def _conferma(self):
        if not self._valida():
            return
        self.risultato = self.entry.get().strip()
        self.destroy()

    def _annulla(self):
        self.risultato = None
        self.destroy()


# ======================================================================
# Schermata Crea Libro
# ======================================================================

class SchermataCreaLibro(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._libro_creato: str | None = None

        self._build_header()
        self._build_body()
        self._build_footer()

        self.after(80, self.campo_slug.focus)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        titolo(header, "Crea nuovo libro").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        sottotitolo(
            header,
            "Compila i campi. Le sottocartelle e i file di "
            "configurazione saranno generati automaticamente.",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        bottone_secondario(
            header, "  Home", command=self.app.mostra_home,
            width=110, height=34,
        ).grid(row=0, column=1, rowspan=2, padx=18, pady=14, sticky="e")

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        body.grid_columnconfigure(0, weight=0, minsize=420)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body)
        self._build_anteprima(body)

    def _build_form(self, parent):
        # Uso uno scrollable frame per evitare che i campi in basso vengano tagliati
        form_scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent", corner_radius=0
        )
        form_scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form_scroll.grid_columnconfigure(0, weight=1)

        form = card(form_scroll)
        form.grid(row=0, column=0, sticky="nsew")
        form.grid_columnconfigure(0, weight=1)

        self.campo_slug = CampoTesto(
            form, "Nome cartella (slug)",
            placeholder="es. SistemiOperativi1",
        )
        self.campo_slug.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        self.campo_slug.entry.bind("<KeyRelease>", lambda e: self._on_slug_change())

        self.campo_titolo = CampoTesto(
            form, "Titolo visualizzato",
            placeholder="es. Sistemi Operativi - Corso base",
        )
        self.campo_titolo.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.campo_soggetto = CampoTesto(
            form, "Soggetto",
            placeholder="es. Informatica",
        )
        self.campo_soggetto.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.campo_dominio = CampoTesto(
            form, "Dominio",
            placeholder="es. SistemiOperativi1",
        )
        self.campo_dominio.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 10))

        self.campo_autore = CampoTesto(
            form, "Autore",
            placeholder="es. Mario Rossi",
        )
        self.campo_autore.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 16))

        # --- SEZIONE INAUGURAZIONE DEEPSEEK ---
        etichetta(form, "1. Regole Base (Inaugurazione)").grid(
            row=5, column=0, sticky="w", padx=16, pady=(4, 4)
        )
        bottone_secondario(
            form,
            "  Copia regole generali libro",
            command=self._copia_pattern_libro,
            width=260,
        ).grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Incolla queste regole in chat all'inizio della sessione "
                 "con DeepSeek. Serviranno a stabilire le regole di base "
                 "del libro (attesa delle slide, generazione immagini, ecc.).",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            wraplength=280, justify="left", anchor="w",
        ).grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 14))

        # Secondo prompt per risorse extra
        etichetta(form, "2. Risorse Extra").grid(
            row=8, column=0, sticky="w", padx=16, pady=(4, 4)
        )
        bottone_secondario(
            form,
            "  Copia prompt risorse extra",
            command=self._copia_pattern_risorse,
            width=260,
        ).grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            form,
            text="Se hai libri o dispense, incolla questo secondo prompt in chat. "
                 "DeepSeek ti chiederà gli indici di tali risorse per usarli "
                 "durante la scrittura dei paragrafi.",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            wraplength=280, justify="left", anchor="w",
        ).grid(row=10, column=0, sticky="ew", padx=16, pady=(0, 14))

        # Non c'è bisogno di grid_rowconfigure perché lo scrollable frame gestisce l'altezza

    def _build_anteprima(self, parent):
        wrap = card(parent)
        wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(2, weight=1)

        etichetta(wrap, "Anteprima struttura").grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4)
        )
        self.lbl_percorso = messaggio(wrap, "", colore=tema.TESTO_TENUE)
        self.lbl_percorso.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        self.txt_anteprima = ctk.CTkTextbox(
            wrap,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none", corner_radius=8, fg_color=tema.BG_INPUT,
            text_color=tema.TESTO_TENUE,
        )
        self.txt_anteprima.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))
        self.txt_anteprima.configure(state="disabled")

        self._aggiorna_anteprima()

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_stato = messaggio(footer, "")
        self.lbl_stato.grid(row=0, column=0, sticky="w")

        self.btn_apri = bottone_secondario(
            footer, "  Apri cartella",
            command=self._apri_cartella,
            width=170,
            state="disabled",
        )
        self.btn_apri.grid(row=0, column=1, sticky="e", padx=(8, 0))

        self.btn_crea = bottone_primario(
            footer, "  Crea libro",
            command=self._crea,
            width=180,
        )
        self.btn_crea.grid(row=0, column=2, sticky="e", padx=(8, 0))

    # ------------------------------------------------------------------
    # Logica
    # ------------------------------------------------------------------

    def _on_slug_change(self):
        self._aggiorna_anteprima()

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        self.lbl_stato.configure(text=testo, text_color=colore)

    def _slug_corrente(self) -> str:
        return self.campo_slug.get().strip()

    def _aggiorna_anteprima(self):
        slug_raw = self._slug_corrente()
        slug = slug_raw or "NOME_LIBRO"

        righe = [f"libri/{slug}/"]
        righe.append("  _config.py")
        righe.append("  config.py")
        for s in SOTTOCARTELLE:
            righe.append(f"  {s}/")

        self.txt_anteprima.configure(state="normal")
        self.txt_anteprima.delete("1.0", "end")
        self.txt_anteprima.insert("1.0", "\n".join(righe))
        self.txt_anteprima.configure(state="disabled")

        percorso = percorso_libro(self.app.root_progetto, slug)
        self.lbl_percorso.configure(text=str(percorso))

    def _copia_pattern_libro(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(PATTERN_LIBRO)
            self.update()
        except Exception as e:
            self._set_stato(f"Errore copia: {e}", colore=tema.ERRORE)
            return
        self._set_stato(
            "Regole generali copiate. Incollale in chat all'inizio "
            "della sessione con DeepSeek.",
            colore=tema.SUCCESSO,
        )

    def _copia_pattern_risorse(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(PATTERN_RISORSE_EXTRA)
            self.update()
        except Exception as e:
            self._set_stato(f"Errore copia: {e}", colore=tema.ERRORE)
            return
        self._set_stato(
            "Prompt risorse extra copiato. Incollalo in chat (dopo il primo).",
            colore=tema.SUCCESSO,
        )

    def _crea(self):
        slug_raw = self._slug_corrente()
        slug = slug_raw if slug_valido(slug_raw)[0] else slugifica(slug_raw)

        ok, motivo = slug_valido(slug)
        if not ok:
            self._set_stato("  " + motivo, colore=tema.ERRORE)
            return

        if libro_esiste(self.app.root_progetto, slug):
            nuovo = self._chiedi_nuovo_nome(slug)
            if nuovo is None:
                self._set_stato(
                    "  Creazione annullata: nome gia' in uso.",
                    colore=tema.AVVISO,
                )
                return
            self.campo_slug.set(nuovo)
            self._aggiorna_anteprima()
            slug = nuovo

        dati = {
            "slug": slug,
            "titolo": self.campo_titolo.get().strip(),
            "soggetto": self.campo_soggetto.get().strip(),
            "dominio": self.campo_dominio.get().strip(),
            "autore": self.campo_autore.get().strip(),
        }

        risultato = crea_libro(self.app.root_progetto, dati)

        if not risultato["ok"]:
            self._set_stato(
                "  " + " | ".join(risultato["errori"]),
                colore=tema.ERRORE,
            )
            return

        self._libro_creato = slug
        self._set_stato(
            f"  Libro creato in libri/{slug}/ "
            f"({len(risultato['creati'])} elementi)",
            colore=tema.SUCCESSO,
        )
        self.btn_apri.configure(state="normal")
        self.btn_crea.configure(state="disabled")
        self._aggiorna_anteprima()

        messagebox.showinfo(
            "Libro creato",
            f"Il libro '{slug}' e' stato creato correttamente.\n\n"
            f"Verrà aperta la vista del libro.",
        )
        self.app.mostra_libro(slug)

    def _chiedi_nuovo_nome(self, slug: str) -> str | None:
        dialog = DialogLibroEsistente(
            self, self.app.root_progetto, slug
        )
        self.wait_window(dialog)
        return dialog.risultato

    def _apri_cartella(self):
        if not self._libro_creato:
            return
        percorso = percorso_libro(
            self.app.root_progetto, self._libro_creato
        )
        if not percorso.is_dir():
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