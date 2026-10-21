# -*- coding: utf-8 -*-
"""
tutorial.py - Finestra modale che spiega il flusso di lavoro al primo avvio.
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import bottone_primario, bottone_secondario, card


class TutorialWizard(ctk.CTkToplevel):
    def __init__(self, parent, on_finish=None):
        super().__init__(parent)
        
        self.on_finish = on_finish
        self.step = 0
        
        self.title("Benvenuto in LIBRI - Tutorial")
        self.geometry("700x500")
        self.resizable(False, False)
        self.configure(fg_color=tema.BG_APP)
        
        try:
            self.transient(parent)
        except Exception:
            pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Dati dei passaggi
        self.steps = [
            {
                "titolo": "Benvenuto in LIBRI!",
                "testo": "Questa applicazione ti permette di creare e impaginare libri tecnici in formato PDF, "
                         "utilizzando l'intelligenza artificiale (DeepSeek) per generare il contenuto e le immagini.\n\n"
                         "Vediamo insieme come funziona il flusso di lavoro in 4 semplici passaggi."
            },
            {
                "titolo": "1. Crea un Libro",
                "testo": "Dalla schermata Home, clicca su «Crea nuovo libro».\n\n"
                         "Compila i campi per generare la struttura di cartelle. L'app creerà automaticamente "
                         "tutto lo scheletro del libro (capitoli, immagini, grafici, ecc.).\n\n"
                         "Qui troverai anche i pulsanti per copiare i «Prompt di Inaugurazione» da dare a DeepSeek."
            },
            {
                "titolo": "2. Estrai le Slide",
                "testo": "Entra nel libro appena creato e clicca su «Estrattore slide».\n\n"
                         "Carica il PDF delle slide del corso. L'app convertirà il PDF in immagini PNG "
                         "che userai per generare le immagini all'interno del libro.\n\n"
                         "Puoi anche usare lo strumento «Gestione immagini» per catturare porzioni di schermo."
            },
            {
                "titolo": "3. Crea Capitoli e Paragrafi",
                "testo": "Vai in «Modifica libro» per creare un nuovo capitolo, e poi crea i paragrafi.\n\n"
                         "Per ogni paragrafo, l'app ti fornirà un pulsante «Copia regole per DeepSeek».\n"
                         "Incolla le regole nella chat di DeepSeek (insieme alle slide caricate).\n\n"
                         "DeepSeek genererà il codice Python. Copialo e incollalo nell'editor dell'app: "
                         "il sistema validerà il codice e ti permetterà di salvare il paragrafo."
            },
            {
                "titolo": "4. Leggi e Genera il PDF",
                "testo": "Clicca su «Apri lettore» per visualizzare l'anteprima PDF di ogni paragrafo.\n\n"
                         "Se il paragrafo contiene immagini, l'app ti chiederà di associarle alle figure estratte "
                         "dalle slide.\n\n"
                         "Puoi sempre rigenerare l'anteprima con il pulsante «Rigenera anteprima». "
                         "Buon lavoro!"
            }
        ]

        self._build_ui()
        self._aggiorna_step()
        self._centra_su_parent(parent)
        
        self.protocol("WM_DELETE_WINDOW", self._chiudi)
        
        self.after(80, self.lift)
        self.after(80, self.focus_force)

    def _build_ui(self):
        # Contenitore centrale
        self.box = card(self)
        self.box.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)
        self.box.grid_columnconfigure(0, weight=1)
        self.box.grid_rowconfigure(1, weight=1)

        # Titolo
        self.lbl_titolo = ctk.CTkLabel(
            self.box, text="",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=tema.PRIMARIO, anchor="w",
        )
        self.lbl_titolo.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))

        # Testo
        self.txt_spiegazione = ctk.CTkTextbox(
            self.box,
            font=ctk.CTkFont(size=14),
            wrap="word",
            fg_color="transparent",
            text_color=tema.TESTO,
        )
        self.txt_spiegazione.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.txt_spiegazione.configure(state="disabled")

        # Footer con pulsanti
        footer = ctk.CTkFrame(self.box, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        footer.grid_columnconfigure(1, weight=1)

        self.btn_salta = bottone_secondario(
            footer, "Salta tutorial", command=self._chiudi, width=120, height=38
        )
        self.btn_salta.grid(row=0, column=0, sticky="w")

        # Indicatore passi (pallini)
        self.frame_dots = ctk.CTkFrame(footer, fg_color="transparent")
        self.frame_dots.grid(row=0, column=1, sticky="w", padx=20)

        self.btn_prev = bottone_secondario(
            footer, "< Indietro", command=self._prev, width=100, height=38
        )
        self.btn_prev.grid(row=0, column=2, sticky="e", padx=(0, 8))

        self.btn_next = bottone_primario(
            footer, "Avanti >", command=self._next, width=120, height=38
        )
        self.btn_next.grid(row=0, column=3, sticky="e")

    def _aggiorna_step(self):
        step_data = self.steps[self.step]
        
        self.lbl_titolo.configure(text=step_data["titolo"])
        
        self.txt_spiegazione.configure(state="normal")
        self.txt_spiegazione.delete("1.0", "end")
        self.txt_spiegazione.insert("1.0", step_data["testo"])
        self.txt_spiegazione.configure(state="disabled")

        # Aggiorna stato pulsanti
        if self.step == 0:
            self.btn_prev.configure(state="disabled")
        else:
            self.btn_prev.configure(state="normal")

        if self.step == len(self.steps) - 1:
            self.btn_next.configure(text="Inizia a usare l'app", width=160, fg_color=tema.SUCCESSO, hover_color="#2e7d3a")
        else:
            self.btn_next.configure(text="Avanti >", width=120, fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER)

        # Aggiorna i pallini indicatori
        for w in self.frame_dots.winfo_children():
            w.destroy()
            
        for i in range(len(self.steps)):
            colore = tema.PRIMARIO if i == self.step else tema.BG_INPUT
            dot = ctk.CTkFrame(self.frame_dots, width=10, height=10, corner_radius=5, fg_color=colore)
            dot.pack(side="left", padx=4)

    def _next(self):
        if self.step < len(self.steps) - 1:
            self.step += 1
            self._aggiorna_step()
        else:
            self._chiudi()

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._aggiorna_step()

    def _chiudi(self):
        if self.on_finish:
            try:
                self.on_finish()
            except Exception:
                pass
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