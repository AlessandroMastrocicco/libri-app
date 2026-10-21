# -*- coding: utf-8 -*-
"""
crea_capitolo.py - Wizard di creazione nuovo capitolo.
"""

from __future__ import annotations

import os
import subprocess
import sys

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
from app.core.capitolo import (
    crea_capitolo,
    elenca_capitoli,
    percorso_capitolo,
    prossimo_numero,
    trova_capitolo_con_titolo,
)


# ======================================================================
# Popup "titolo gia' usato"
# ======================================================================

class DialogTitoloDuplicato(ctk.CTkToplevel):
    """
    Popup modale che chiede un titolo diverso quando un capitolo con
    lo stesso titolo esiste gia'.

    Risultato in self.risultato: nuovo titolo (str) o None se annullato.
    """

    def __init__(self, parent, root_progetto, slug: str,
                 titolo_attuale: str, numero_conflitto: int):
        super().__init__(parent)

        self.root_progetto = root_progetto
        self.slug = slug
        self.titolo_attuale = titolo_attuale
        self.numero_conflitto = numero_conflitto
        self.risultato: str | None = None

        self.title("Titolo gia' esistente")
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
            text="Titolo gia' usato",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w", text_color=tema.ERRORE,
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(20, 4))

        ctk.CTkLabel(
            self,
            text=f"Esiste gia' il capitolo {numero_conflitto:02d} "
                 f"con questo titolo:\n"
                 f"    \"{titolo_attuale}\"\n\n"
                 f"Scegli un titolo diverso per il nuovo capitolo.",
            font=ctk.CTkFont(size=12),
            anchor="w", justify="left",
            text_color=tema.TESTO_TENUE,
            wraplength=480,
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 14))

        ctk.CTkLabel(
            self, text="Nuovo titolo del capitolo",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 4))

        self.entry = ctk.CTkEntry(
            self,
            height=36,
            font=ctk.CTkFont(size=13),
            fg_color=tema.BG_INPUT,
        )
        self.entry.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 6))
        self.entry.insert(0, titolo_attuale)
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

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, sticky="e", padx=20, pady=(4, 20))

        ctk.CTkButton(
            btns, text="  Annulla",
            width=110, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._annulla,
        ).pack(side="left", padx=(0, 8))

        self.btn_ok = ctk.CTkButton(
            btns, text="  Prova titolo",
            width=150, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._conferma,
        )
        self.btn_ok.pack(side="left")

        self._centra_su_parent(parent)

        self.after(80, self.entry.focus_set)
        self.after(80, lambda: self.entry.select_range(0, "end"))
        self.after(80, self.lift)
        self.after(80, self.focus_force)

        self._valida()

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
            self.lbl_errore.configure(text="Il titolo e' obbligatorio.")
            self.btn_ok.configure(state="disabled")
            return False

        if nuovo.lower() == self.titolo_attuale.strip().lower():
            self.lbl_errore.configure(
                text="Questo titolo e' ancora in uso. Scegline un altro."
            )
            self.btn_ok.configure(state="disabled")
            return False

        # esiste un altro capitolo con questo titolo?
        conflitto = trova_capitolo_con_titolo(
            self.root_progetto, self.slug, nuovo
        )
        if conflitto is not None:
            self.lbl_errore.configure(
                text=f"Anche questo titolo e' gia' usato dal capitolo "
                     f"{conflitto:02d}."
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
# Schermata crea capitolo
# ======================================================================

class SchermataCreaCapitolo(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._numero_corrente: int = 1
        self._capitolo_creato: int | None = None

        self._build_header()
        self._build_body()
        self._build_footer()

        self._inizializza()
        self.after(80, self.campo_nome.focus)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        titolo(header, "Crea nuovo capitolo").grid(
            row=0, column=0, sticky="w", padx=18, pady=(14, 2)
        )
        sottotitolo(
            header,
            f"Libro: {self.slug}. Scrivi il nome del capitolo: il "
            f"numero viene assegnato automaticamente.",
        ).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        bottone_secondario(
            header, "  Torna al libro",
            command=lambda: self.app.mostra_libro(self.slug),
            width=160, height=34,
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
        form = card(parent)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form.grid_columnconfigure(0, weight=1)

        self.campo_nome = CampoTesto(
            form,
            "Nome del capitolo",
            placeholder="es. Introduzione ai Sistemi Operativi",
        )
        self.campo_nome.grid(row=0, column=0, sticky="ew",
                              padx=16, pady=(16, 10))
        self.campo_nome.entry.bind(
            "<KeyRelease>", lambda e: self._on_nome_change()
        )

        riga_num = ctk.CTkFrame(form, fg_color="transparent")
        riga_num.grid(row=1, column=0, sticky="ew",
                      padx=16, pady=(0, 10))
        riga_num.grid_columnconfigure(1, weight=1)

        etichetta(riga_num, "Numero assegnato").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.lbl_numero = ctk.CTkLabel(
            riga_num,
            text=str(self._numero_corrente),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=tema.TESTO,
            anchor="w",
        )
        self.lbl_numero.grid(row=1, column=0, sticky="w")

        self.lbl_info_num = ctk.CTkLabel(
            riga_num,
            text="(prossimo libero)",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            anchor="w",
        )
        self.lbl_info_num.grid(row=1, column=1, sticky="w", padx=(8, 0))

        form.grid_rowconfigure(2, weight=1)

    def _build_anteprima(self, parent):
        wrap = card(parent)
        wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(3, weight=1)

        etichetta(wrap, "Anteprima struttura").grid(
            row=0, column=0, sticky="w", padx=16, pady=(16, 4)
        )
        self.lbl_percorso = messaggio(wrap, "", colore=tema.TESTO_TENUE)
        self.lbl_percorso.grid(row=1, column=0, sticky="w",
                                padx=16, pady=(0, 4))
        self.lbl_esistenti = messaggio(wrap, "", colore=tema.TESTO_TENUE)
        self.lbl_esistenti.grid(row=2, column=0, sticky="w",
                                 padx=16, pady=(0, 8))

        self.txt_anteprima = ctk.CTkTextbox(
            wrap,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="none",
            corner_radius=8,
            fg_color=tema.BG_INPUT,
            text_color=tema.TESTO_TENUE,
        )
        self.txt_anteprima.grid(row=3, column=0, sticky="nsew",
                                 padx=16, pady=(0, 16))
        self.txt_anteprima.configure(state="disabled")

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
            footer, "  Crea capitolo",
            command=self._crea,
            width=200,
        )
        self.btn_crea.grid(row=0, column=2, sticky="e", padx=(8, 0))

    # ------------------------------------------------------------------
    # Inizializzazione
    # ------------------------------------------------------------------

    def _inizializza(self):
        self._numero_corrente = prossimo_numero(
            self.app.root_progetto, self.slug
        )
        self.lbl_numero.configure(text=str(self._numero_corrente))
        self._aggiorna_anteprima()

    # ------------------------------------------------------------------
    # Logica
    # ------------------------------------------------------------------

    def _nome_corrente(self) -> str:
        return self.campo_nome.get().strip()

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        self.lbl_stato.configure(text=testo, text_color=colore)

    def _on_nome_change(self):
        self._aggiorna_anteprima()

    def _aggiorna_anteprima(self):
        n = self._numero_corrente
        nome = self._nome_corrente() or "(senza nome)"

        cap_dir = percorso_capitolo(
            self.app.root_progetto, self.slug, n
        )

        righe = [
            f"libri/{self.slug}/capitoli/capitolo_{n:02d}/",
            "  capitolo.py",
            f"    (titolo: {nome})",
            "  paragrafi/",
            "    __init__.py",
        ]

        self.txt_anteprima.configure(state="normal")
        self.txt_anteprima.delete("1.0", "end")
        self.txt_anteprima.insert("1.0", "\n".join(righe))
        self.txt_anteprima.configure(state="disabled")

        self.lbl_percorso.configure(text=str(cap_dir))

        esistenti = elenca_capitoli(self.app.root_progetto, self.slug)
        if esistenti:
            self.lbl_esistenti.configure(
                text="Capitoli esistenti: "
                     + ", ".join(str(x) for x in esistenti)
            )
        else:
            self.lbl_esistenti.configure(text="Nessun capitolo esistente.")

    def _crea(self):
        nome = self._nome_corrente()
        if not nome:
            self._set_stato(
                "  Scrivi il nome del capitolo.", colore=tema.ERRORE
            )
            return

        n = self._numero_corrente

        # 1) controllo titolo duplicato
        conflitto = trova_capitolo_con_titolo(
            self.app.root_progetto, self.slug, nome
        )
        if conflitto is not None:
            nuovo = self._chiedi_nuovo_titolo(nome, conflitto)
            if nuovo is None:
                self._set_stato(
                    "  Creazione annullata: titolo gia' usato.",
                    colore=tema.AVVISO,
                )
                return
            self.campo_nome.set(nuovo)
            self._aggiorna_anteprima()
            nome = nuovo

        # 2) creazione
        risultato = crea_capitolo(
            self.app.root_progetto, self.slug, n, titolo=nome
        )

        if not risultato["ok"]:
            self._set_stato(
                "  " + " | ".join(risultato["errori"]),
                colore=tema.ERRORE,
            )
            return

        # 3) successo
        self._capitolo_creato = n
        self._set_stato(
            f"  Capitolo {n:02d} creato "
            f"(titolo: {nome}) in "
            f"libri/{self.slug}/capitoli/capitolo_{n:02d}/",
            colore=tema.SUCCESSO,
        )
        self.btn_apri.configure(state="normal")
        self.btn_crea.configure(state="disabled")
        self.campo_nome.entry.configure(state="disabled")

        # 4) transizione automatica alla schermata paragrafo
        self.after(300, lambda: self.app.mostra_crea_paragrafo(
            self.slug, n
        ))

    def _chiedi_nuovo_titolo(self, titolo: str,
                             numero_conflitto: int) -> str | None:
        dialog = DialogTitoloDuplicato(
            self, self.app.root_progetto, self.slug,
            titolo, numero_conflitto,
        )
        self.wait_window(dialog)
        return dialog.risultato

    def _apri_cartella(self):
        if self._capitolo_creato is None:
            return
        percorso = percorso_capitolo(
            self.app.root_progetto, self.slug, self._capitolo_creato
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