# -*- coding: utf-8 -*-
"""
popup_rigenera.py - Popup "Rigenera paragrafo" (responsabilita' unica: UI).

L'utente scrive in una casella di testo le istruzioni sui cambiamenti voluti
e preme Invia. La rigenerazione vera (recupero fonti/slide, versione attuale,
linee guida, chiamata AI) e' delegata a `app.core.ai.rigenera`, eseguito in un
thread separato per non bloccare la UI. Il risultato viene consegnato al
callback `on_fine(esito, note)` che decide come mostrarlo/salvarlo.
"""

from __future__ import annotations

import threading
from tkinter import messagebox

import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import bottone_primario, bottone_secondario


class PopupRigeneraParagrafo(ctk.CTkToplevel):
    """Dialogo con textbox istruzioni + pulsante Invia.

    Parametri:
      parent        : widget radice della schermata;
      titolo_par    : titolo del paragrafo (per contestualizzare l'utente);
      on_invia      : callback(istruzioni:str, rifai:callable) -> il popup
                      passa anche una funzione per rilanciare la stessa
                      richiesta (utile dopo un errore quota/rete);
      on_fine       : callback(esito, note:list[str]) chiamato sul thread UI
                      quando la rigenerazione termina.
    """

    def __init__(self, parent, *, titolo_par: str,
                 avvia: callable, on_fine: callable):
        super().__init__(parent)
        self.title("Rigenera paragrafo con AI")
        self.geometry("720x560")
        self.minsize(560, 420)
        self.configure(fg_color=tema.BG_APP)
        try:
            self.transient(parent)
        except Exception:
            pass

        self._avvia = avvia          # avvia(istruzioni, done_cb)
        self._on_fine = on_fine
        self._in_corso = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- header -----------------------------------------------------
        hdr = ctk.CTkFrame(self, corner_radius=12, fg_color=tema.BG_CARD)
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            hdr, text=f"Rigenera «{titolo_par}»",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=tema.TESTO, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(
            hdr,
            text=("Descrivi i cambiamenti voluti. L'AI riparte dalle FONTI "
                  "(le slide coinvolte), dalla VERSIONE ATTUALE del paragrafo "
                  "e dalle LINEE GUIDA del libro, applicando le tue "
                  "indicazioni. Il risultato arriva in bozza: lo rivedi tu."),
            font=ctk.CTkFont(size=12), text_color=tema.TESTO_TENUE,
            anchor="w", wraplength=640, justify="left",
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 14))

        # --- istruzioni --------------------------------------------------
        lbl = ctk.CTkLabel(self, text="Istruzioni per il modello:",
                           font=ctk.CTkFont(size=13, weight="bold"),
                           text_color=tema.TESTO, anchor="w")
        lbl.grid(row=1, column=0, sticky="w", padx=20, pady=(6, 2))

        self.txt_istruzioni = ctk.CTkTextbox(
            self, corner_radius=10, fg_color=tema.BG_CARD,
            border_width=1, border_color=tema.BG_INPUT_HOVER,
            font=ctk.CTkFont(size=13), wrap="word")
        self.txt_istruzioni.grid(row=2, column=0, sticky="nsew",
                                 padx=20, pady=(2, 8))
        self.txt_istruzioni.insert(
            "1.0",
            "Esempi: «Espandi il concetto X con un esempio svolto»; "
            "«Accorcia il terzo sottoparagrafo»; «Cambia il tono: piu' "
            "discorsivo»; «Aggiungi gli errori comuni su Y».\n")

        # --- footer ------------------------------------------------------
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 16))
        foot.grid_columnconfigure(0, weight=1)

        self.lbl_stato = ctk.CTkLabel(foot, text="", anchor="w",
                                      font=ctk.CTkFont(size=12),
                                      text_color=tema.TESTO_TENUE)
        self.lbl_stato.grid(row=0, column=0, sticky="w")

        self.btn_chiudi = bottone_secondario(foot, "  Chiudi",
                                             command=self.destroy, width=120)
        self.btn_chiudi.grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.btn_invia = bottone_primario(foot, "  Invia al modello",
                                          command=self._invia, width=190)
        self.btn_invia.grid(row=0, column=1, sticky="e", padx=(8, 0))

    # ------------------------------------------------------------------

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        try:
            self.lbl_stato.configure(text=testo, text_color=colore)
        except Exception:
            pass

    def _invia(self):
        if self._in_corso:
            self._set_stato("Rigenerazione gia' in corso...", tema.AVVISO)
            return
        istruzioni = self.txt_istruzioni.get("1.0", "end").strip()
        # ignora il testo d'esempio se l'utente non l'ha toccato
        if not istruzioni or istruzioni.startswith("Esempi:"):
            messagebox.showwarning(
                "Istruzioni mancanti",
                "Scrivi almeno un'istruzione: cosa deve cambiare nel "
                "paragrafo?", parent=self)
            return

        self._in_corso = True
        self.btn_invia.configure(state="disabled", text="  Rigenero...")
        self._set_stato("Rigenerazione avviata (puo' richiedere qualche "
                        "minuto; le quote esauste fanno switchare modello "
                        "automaticamente)...", tema.AVVISO)

        def done():
            self._in_corso = False
            self.btn_invia.configure(state="normal",
                                     text="  Invia al modello")

        def worker():
            # il core fa tutto (fonti+versione+guida+istruzioni+AI).
            # Il callback `cb` viene INVOCATO GIA' SUL THREAD UI dal chiamante
            # (pattern usato in crea_paragrafo/lettore); se un core passasse
            # l'esito dal thread di lavoro, `_fine` resta idempotente perche'
            # configurare widget da altro thread non e' sicuro: normalizziamo.
            def cb(esito, note):
                import threading as _th
                if _th.current() is _th.main_thread():
                    self._fine(esito, note)
                else:
                    self.after(0, lambda: self._fine(esito, note))

            try:
                self._avvia(istruzioni, cb)
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                self.after(0, lambda: self._fine(None, [f"Errore: {err}"]))

        threading.Thread(target=worker, daemon=True).start()

    def _fine(self, esito, note):
        self._in_corso = False
        try:
            self.btn_invia.configure(state="normal",
                                     text="  Invia al modello")
        except Exception:
            pass
        if esito is None or not getattr(esito, "ok", False):
            errore = getattr(esito, "errore", None) or "esito assente"
            self._set_stato(f"Rigenerazione non riuscita: {errore}",
                            tema.ERRORE)
        else:
            self._set_stato(
                f"Rigenerato con {esito.modello_finale} "
                f"({esito.token_totali:,} token).", tema.SUCCESSO)
        if callable(self._on_fine):
            self._on_fine(esito, note or [])
