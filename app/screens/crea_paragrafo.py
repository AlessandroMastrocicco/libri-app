# -*- coding: utf-8 -*-
"""
crea_paragrafo.py - Crea o modifica un paragrafo.
"""

from __future__ import annotations

import traceback
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
from app.core.paragrafo import (
    aggiorna_paragrafo,
    crea_paragrafo,
    elenca_paragrafi,
    leggi_paragrafo,
    paragrafo_esiste,
    prossimo_numero,
    titolo_da_sorgente,
    valida_contenuto,
    pulisci_codice_markdown,
)
from app.core.render_paragrafo import invalida_cache_paragrafo
from app.core.pattern_paragrafo import PATTERN_PARAGRAFO
from app.core.pattern_esercizi import PATTERN_ESERCIZI
from app.screens.associa_immagini import PopupAssociaImmagini


class DialogErroreValidazione(ctk.CTkToplevel):
    def __init__(self, parent, val: dict):
        super().__init__(parent)
        self.title("Validazione non superata")
        self.geometry("760x620")
        self.minsize(600, 480)
        self.configure(fg_color=tema.BG_APP)
        try: self.transient(parent)
        except Exception: pass

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        tipo_err = (val.get("tipo_errore") or "errore").lower()
        etichetta_tipo = "Sintassi" if tipo_err == "sintassi" else "Struttura" if tipo_err == "struttura" else "Errore"
        colore = tema.ERRORE

        header = ctk.CTkFrame(self, corner_radius=12, fg_color=tema.BG_CARD)
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 8))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=f"Errore di {etichetta_tipo}", font=ctk.CTkFont(size=18, weight="bold"), anchor="w", text_color=colore).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 4))
        ctk.CTkLabel(header, text=val.get("errore") or "Contenuto non valido.", font=ctk.CTkFont(size=13), anchor="w", justify="left", text_color=tema.TESTO, wraplength=680).grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        body = ctk.CTkScrollableFrame(self, corner_radius=8, fg_color=tema.BG_INPUT)
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 8))
        body.grid_columnconfigure(0, weight=1)

        det = val.get("dettagli") or {}
        riga = 0

        info_riga = []
        if det.get("riga") is not None: info_riga.append(f"Riga: {det['riga']}")
        if det.get("colonna") is not None: info_riga.append(f"Colonna: {det['colonna']}")
        if det.get("tipo"): info_riga.append(f"Tipo: {det['tipo']}")

        if info_riga:
            ctk.CTkLabel(body, text="   ".join(info_riga), font=ctk.CTkFont(size=12, weight="bold"), anchor="w", text_color=tema.TESTO_TENUE).grid(row=riga, column=0, sticky="w", padx=14, pady=(12, 4))
            riga += 1

        if det.get("frammento"):
            ctk.CTkLabel(body, text="Frammento di codice", font=ctk.CTkFont(size=13, weight="bold"), anchor="w", text_color=tema.TESTO).grid(row=riga, column=0, sticky="w", padx=14, pady=(10, 2))
            riga += 1
            testo_frammento = ctk.CTkTextbox(body, height=140, font=ctk.CTkFont(family="Consolas", size=12), wrap="none", corner_radius=6, fg_color=tema.BG_CARD, text_color=tema.TESTO)
            testo_frammento.grid(row=riga, column=0, sticky="ew", padx=14, pady=(0, 8))
            testo_frammento.insert("1.0", det["frammento"])
            testo_frammento.configure(state="disabled")
            riga += 1

        if det.get("suggerimento"):
            ctk.CTkLabel(body, text="Cosa fare", font=ctk.CTkFont(size=13, weight="bold"), anchor="w", text_color=tema.AVVISO).grid(row=riga, column=0, sticky="w", padx=14, pady=(10, 2))
            riga += 1
            ctk.CTkLabel(body, text=det["suggerimento"], font=ctk.CTkFont(size=12), anchor="w", justify="left", text_color=tema.TESTO_TENUE, wraplength=680).grid(row=riga, column=0, sticky="w", padx=14, pady=(0, 8))
            riga += 1

        if det.get("elementi_mancanti"):
            ctk.CTkLabel(body, text="Elementi mancanti", font=ctk.CTkFont(size=13, weight="bold"), anchor="w", text_color=tema.ERRORE).grid(row=riga, column=0, sticky="w", padx=14, pady=(10, 2))
            riga += 1
            for el in det["elementi_mancanti"]:
                ctk.CTkLabel(body, text=f"  -  {el}", font=ctk.CTkFont(size=12), anchor="w", text_color=tema.TESTO_TENUE).grid(row=riga, column=0, sticky="w", padx=20, pady=1)
                riga += 1

        if det.get("elementi_ok"):
            ctk.CTkLabel(body, text="Elementi corretti", font=ctk.CTkFont(size=13, weight="bold"), anchor="w", text_color=tema.SUCCESSO).grid(row=riga, column=0, sticky="w", padx=14, pady=(10, 2))
            riga += 1
            for el in det["elementi_ok"]:
                ctk.CTkLabel(body, text=f"  +  {el}", font=ctk.CTkFont(size=12), anchor="w", text_color=tema.TESTO_TENUE).grid(row=riga, column=0, sticky="w", padx=20, pady=1)
                riga += 1

        if val.get("warning"):
            ctk.CTkLabel(body, text="Avvisi non bloccanti", font=ctk.CTkFont(size=13, weight="bold"), anchor="w", text_color=tema.AVVISO).grid(row=riga, column=0, sticky="w", padx=14, pady=(10, 2))
            riga += 1
            for w in val["warning"]:
                ctk.CTkLabel(body, text=f"  -  {w}", font=ctk.CTkFont(size=12), anchor="w", justify="left", text_color=tema.TESTO_TENUE, wraplength=660).grid(row=riga, column=0, sticky="w", padx=20, pady=1)
                riga += 1

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        ctk.CTkButton(footer, text="  Chiudi", width=140, height=38, fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER, font=ctk.CTkFont(size=13, weight="bold"), command=self.destroy).pack(side="right")

        self._centra_su_parent(parent)
        self.after(80, self.lift)
        self.after(80, self.focus_force)

    def _centra_su_parent(self, parent):
        try:
            self.update_idletasks()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            w, h = self.winfo_width(), self.winfo_height()
            self.geometry(f"+{max(0, px + (pw - w) // 2)}+{max(0, py + (ph - h) // 2)}")
        except Exception: pass


class SchermataCreaParagrafo(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str, cap: int, par: str | None = None):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug
        self.cap = cap
        self.par_esistente = par
        self._modifica = par is not None
        self._contenuto_validato: str | None = None

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self._build_footer()

        self._inizializza()

    def _build_header(self):
        header = card(self)
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 8))
        header.grid_columnconfigure(0, weight=1)

        azione = "Modifica" if self._modifica else "Nuovo"
        self._titolo_header = titolo(header, f"{azione} paragrafo")
        self._titolo_header.grid(row=0, column=0, sticky="w", padx=18, pady=(14, 2))
        sottotitolo(header, f"{self.slug} - capitolo {self.cap:02d}").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))

        bottone_secondario(header, "  Torna al capitolo", command=lambda: self.app.mostra_capitolo(self.slug, self.cap), width=190, height=34).grid(row=0, column=1, rowspan=2, padx=18, pady=14, sticky="e")

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 8))
        body.grid_columnconfigure(0, weight=0, minsize=340)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._build_form(body)
        self._build_editor(body)

    def _build_form(self, parent):
        form = card(parent)
        form.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        form.grid_columnconfigure(0, weight=1)

        r = 0
        self.campo_numero = CampoTesto(form, "Numero paragrafo", placeholder="es. 4")
        self.campo_numero.grid(row=r, column=0, sticky="ew", padx=16, pady=(16, 10))
        self.campo_numero.entry.bind("<KeyRelease>", lambda e: self._aggiorna_anteprima())
        r += 1

        self._var_esercizi = ctk.BooleanVar(value=False)
        self.chk_esercizi = ctk.CTkCheckBox(form, text="Questo è un eserciziario", variable=self._var_esercizi, font=ctk.CTkFont(size=12), command=self._on_change_esercizi)
        self.chk_esercizi.grid(row=r, column=0, sticky="w", padx=16, pady=(0, 10))
        r += 1

        self.frame_teoria_origine = ctk.CTkFrame(form, fg_color="transparent")
        self.frame_teoria_origine.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.frame_teoria_origine.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self.frame_teoria_origine, text="Collegato al paragrafo teorico:", font=ctk.CTkFont(size=11, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w")
        self.opt_teoria_origine = ctk.CTkOptionMenu(self.frame_teoria_origine, values=[""], font=ctk.CTkFont(size=12))
        self.opt_teoria_origine.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.frame_teoria_origine.grid_remove()
        r += 1

        self.campo_titolo = CampoTesto(form, "Titolo (opzionale)", placeholder="es. Dentro il Sistema Operativo")
        self.campo_titolo.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 10))
        r += 1

        self.lbl_id = ctk.CTkLabel(form, text=f"id: {self.cap}.?", font=ctk.CTkFont(family="Consolas", size=12), text_color=tema.TESTO_TENUE, anchor="w")
        self.lbl_id.grid(row=r, column=0, sticky="w", padx=16, pady=(0, 12))
        r += 1

        etichetta(form, "Istruzioni per DeepSeek").grid(row=r, column=0, sticky="w", padx=16, pady=(4, 4))
        r += 1

        self.lbl_istruzioni = ctk.CTkLabel(
            form,
            text="1. Carica le slide in formato PNG nella chat.\n"
                 "2. Copia le regole.\n"
                 "3. Incolla le regole in chat. DeepSeek genererà il codice.\n"
                 "4. Copia il codice e incollalo nell'editor a fianco.",
            font=ctk.CTkFont(size=11), text_color=tema.TESTO_MOLTO_TENUE,
            wraplength=280, justify="left", anchor="w",
        )
        self.lbl_istruzioni.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 10))
        r += 1

        self.btn_copia = bottone_primario(
            form, "  Copia regole paragrafo", command=self._copia_pattern, width=260,
        )
        self.btn_copia.grid(row=r, column=0, sticky="ew", padx=16, pady=(0, 14))
        r += 1

        form.grid_rowconfigure(r, weight=1)

    def _build_editor(self, parent):
        wrap = card(parent)
        wrap.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(wrap, text="Codice del paragrafo", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        self.txt_codice = ctk.CTkTextbox(wrap, font=ctk.CTkFont(family="Consolas", size=12), wrap="none", corner_radius=8)
        self.txt_codice.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.txt_codice.bind("<KeyRelease>", lambda e: self._on_contenuto_cambia())

    def _build_footer(self):
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 24))
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_stato = messaggio(footer, "")
        self.lbl_stato.grid(row=0, column=0, sticky="w")

        self.btn_valida = bottone_secondario(footer, "  Valida codice", command=self._valida, width=150)
        self.btn_valida.grid(row=0, column=1, sticky="e", padx=(8, 0))

        bottone_secondario(footer, "  Incolla dagli appunti", command=self._incolla, width=210).grid(row=0, column=2, sticky="e", padx=(8, 0))

        self.btn_anteprima = bottone_secondario(footer, "  Salva e anteprima", command=self._salva_e_anteprima, width=200, state="disabled")
        self.btn_anteprima.grid(row=0, column=3, sticky="e", padx=(8, 0))

        self.btn_salva = bottone_primario(footer, "  Salva paragrafo", command=self._salva, width=200, state="disabled")
        self.btn_salva.grid(row=0, column=4, sticky="e", padx=(8, 0))

    def _inizializza(self):
        par_ids = elenca_paragrafi(self.app.root_progetto, self.slug, self.cap)
        teoria_ids = [p for p in par_ids if not p.endswith("_esercizi")]
        if teoria_ids:
            self.opt_teoria_origine.configure(values=teoria_ids)
            self.opt_teoria_origine.set(teoria_ids[0])
        else:
            self.opt_teoria_origine.configure(values=["Nessuno"])
            self.opt_teoria_origine.set("Nessuno")

        if self._modifica:
            if self.par_esistente and self.par_esistente.endswith("_esercizi"):
                self._var_esercizi.set(True)
                self.chk_esercizi.configure(state="disabled")
                num_str = self.par_esistente.replace("_esercizi", "")
                self.campo_numero.set(str(int(num_str)))
                
                contenuto = leggi_paragrafo(self.app.root_progetto, self.slug, self.cap, self.par_esistente)
                from app.core.paragrafo import leggi_teoria_origine
                orig = leggi_teoria_origine(contenuto or "", fallback=num_str)
                if orig in teoria_ids:
                    self.opt_teoria_origine.set(orig)

                self.frame_teoria_origine.grid()
                self._titolo_header.configure(text="Modifica eserciziario")
                self.lbl_istruzioni.configure(text="Stai modificando un eserciziario. Copia le regole e incollale in chat per rigenerare.")
                self.btn_copia.configure(text="  Copia regole eserciziario")
            else:
                self.campo_numero.set(str(int(self.par_esistente)))
                self.campo_numero.entry.configure(state="disabled")
                self._titolo_header.configure(text="Modifica paragrafo")

            contenuto = leggi_paragrafo(self.app.root_progetto, self.slug, self.cap, self.par_esistente)
            if contenuto:
                self.txt_codice.insert("1.0", contenuto)
                titolo_par = titolo_da_sorgente(contenuto, fallback="")
                if titolo_par: self.campo_titolo.set(titolo_par)
            self._aggiorna_anteprima()
        else:
            n = prossimo_numero(self.app.root_progetto, self.slug, self.cap)
            self.campo_numero.set(str(n))
            self._aggiorna_anteprima()

        self._contenuto_validato = None
        self._aggiorna_stato_pulsanti_salva()

    def _on_change_esercizi(self):
        is_ex = self._var_esercizi.get()
        if is_ex:
            self.frame_teoria_origine.grid()
            self._titolo_header.configure(text="Nuovo eserciziario")
            self.lbl_istruzioni.configure(text="Stai creando un eserciziario. Copia le regole e incollale in chat per generare domande ed esercizi.")
            self.btn_copia.configure(text="  Copia regole eserciziario")
        else:
            self.frame_teoria_origine.grid_remove()
            self._titolo_header.configure(text="Nuovo paragrafo")
            self.lbl_istruzioni.configure(text="1. Carica le slide in formato PNG nella chat.\n2. Copia le regole.\n3. Incolla le regole in chat. DeepSeek genererà il codice.\n4. Copia il codice e incollalo nell'editor a fianco.")
            self.btn_copia.configure(text="  Copia regole paragrafo")
        self._aggiorna_anteprima()

    def _numero_corrente(self) -> int | None:
        try: return int(self.campo_numero.get().strip())
        except ValueError: return None

    def _par_id(self) -> str | None:
        n = self._numero_corrente()
        if n is None: return None
        is_ex = self._var_esercizi.get()
        return f"{n:02d}_esercizi" if is_ex else f"{n:02d}"

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        self.lbl_stato.configure(text=testo, text_color=colore)

    def _aggiorna_anteprima(self):
        par_id = self._par_id()
        if par_id is None:
            self.lbl_id.configure(text="id: -")
        else:
            self.lbl_id.configure(text=f"id: {self.cap}.{par_id}")

    def _copia_pattern(self):
        if self._var_esercizi.get():
            teoria = self.opt_teoria_origine.get()
            pat = PATTERN_ESERCIZI.format(teoria_origine=teoria)
        else:
            pat = PATTERN_PARAGRAFO
            
        try:
            self.clipboard_clear()
            self.clipboard_append(pat)
            self.update()
        except Exception as e:
            self._set_stato(f"Errore copia: {e}", colore=tema.ERRORE)
            return
        self._set_stato("Regole copiate. Incollale in chat.", colore=tema.SUCCESSO)

    def _incolla(self):
        try: testo = self.clipboard_get()
        except Exception:
            self._set_stato("Appunti vuoti.", colore=tema.ERRORE)
            return
        
        testo = pulisci_codice_markdown(testo)
        
        self.txt_codice.delete("1.0", "end")
        self.txt_codice.insert("1.0", testo)
        self._contenuto_validato = None
        self._aggiorna_stato_pulsanti_salva()
        self._set_stato("Contenuto incollato. Premi «Valida codice».", colore=tema.AVVISO)

    def _on_contenuto_cambia(self):
        self._contenuto_validato = None
        self._aggiorna_stato_pulsanti_salva()

    def _aggiorna_stato_pulsanti_salva(self):
        contenuto = self.txt_codice.get("1.0", "end").strip()
        valido = (self._contenuto_validato is not None and self._contenuto_validato == contenuto and contenuto != "")
        stato = "normal" if valido else "disabled"
        try:
            self.btn_salva.configure(state=stato)
            self.btn_anteprima.configure(state=stato)
        except Exception: pass

    def _valida(self) -> dict | None:
        contenuto = self.txt_codice.get("1.0", "end").strip()
        if not contenuto:
            self._contenuto_validato = None
            self._aggiorna_stato_pulsanti_salva()
            self._set_stato("Incolla il codice prima di validare.", colore=tema.ERRORE)
            return None

        contenuto_pulito = pulisci_codice_markdown(contenuto)
        
        if contenuto_pulito != contenuto:
            self.txt_codice.delete("1.0", "end")
            self.txt_codice.insert("1.0", contenuto_pulito)
            self._set_stato("Rimossi i blocchi markdown. Validazione...", colore=tema.AVVISO)
            contenuto = contenuto_pulito

        val = valida_contenuto(contenuto, root=self.app.root_progetto, slug=self.slug, cap=self.cap)

        if not val["ok"]:
            tipo = (val.get("tipo_errore") or "errore").lower()
            if tipo == "immagine":
                self._contenuto_validato = None
                self._aggiorna_stato_pulsanti_salva()
                self._apri_associazione_immagini(contenuto)
                return val

            self._contenuto_validato = None
            self._aggiorna_stato_pulsanti_salva()
            etichetta = ("Sintassi" if tipo == "sintassi" else "Struttura" if tipo == "struttura" else "Errore")
            self._set_stato(f"{etichetta}: {val['errore']}", colore=tema.ERRORE)
            return val

        self._contenuto_validato = contenuto
        self._aggiorna_stato_pulsanti_salva()
        if val["warning"]:
            self._set_stato(f"Valido con {len(val['warning'])} avvisi. Puoi salvare.", colore=tema.AVVISO)
        else:
            self._set_stato("Validazione superata: puoi salvare.", colore=tema.SUCCESSO)
        return val

    def _apri_associazione_immagini(self, contenuto: str):
        self._set_stato("Immagini mancanti: completa l'associazione nel popup.", colore=tema.AVVISO)
        def on_completato():
            self.after(120, self._valida)
        try:
            popup = PopupAssociaImmagini(self, self.app.root_progetto, self.slug, self.cap, contenuto, on_completato=on_completato)
        except Exception as e:
            print(traceback.format_exc())
            self._set_stato(f"Errore apertura popup: {e}", colore=tema.ERRORE)
            return
        self.wait_window(popup)

    def _mostra_dialogo_errore(self, val: dict):
        dialog = DialogErroreValidazione(self, val)
        self.wait_window(dialog)

    def _salva(self, apri_anteprima: bool = False) -> str | None:
        contenuto = self.txt_codice.get("1.0", "end").strip()
        if not contenuto:
            self._set_stato("Incolla il codice prima di salvare.", colore=tema.ERRORE)
            return None

        par_id = self._par_id()
        if par_id is None:
            self._set_stato("Numero paragrafo non valido.", colore=tema.ERRORE)
            return None

        if (self._contenuto_validato is None or self._contenuto_validato != contenuto):
            val = valida_contenuto(contenuto, root=self.app.root_progetto, slug=self.slug, cap=self.cap)
            if not val["ok"]:
                tipo = (val.get("tipo_errore") or "errore").lower()
                if tipo == "immagine":
                    self._apri_associazione_immagini(contenuto)
                    return None
                etichetta = ("Sintassi" if tipo == "sintassi" else "Struttura" if tipo == "struttura" else "Errore")
                self._set_stato(f"Salvataggio bloccato - {etichetta}: {val['errore']}", colore=tema.ERRORE)
                self._mostra_dialogo_errore(val)
                return None
            self._contenuto_validato = contenuto
            self._aggiorna_stato_pulsanti_salva()

        if self._modifica:
            par_salvato = self.par_esistente
            risultato = aggiorna_paragrafo(self.app.root_progetto, self.slug, self.cap, par_salvato, contenuto)
            if risultato["ok"]:
                invalida_cache_paragrafo(self.app.root_progetto, self.slug, self.cap, par_salvato)
        else:
            if paragrafo_esiste(self.app.root_progetto, self.slug, self.cap, par_id):
                self._set_stato(f"Il paragrafo {self.cap}.{par_id} esiste gia'.", colore=tema.ERRORE)
                return None
            par_salvato = par_id
            risultato = crea_paragrafo(self.app.root_progetto, self.slug, self.cap, par_id, contenuto)

        if not risultato["ok"]:
            self._set_stato("Errore: " + " | ".join(risultato["errori"]), colore=tema.ERRORE)
            return None

        avvisi = risultato.get("warning") or []
        msg = f"Salvato in {risultato['path'].name}"
        colore = tema.AVVISO if avvisi else tema.SUCCESSO
        if avvisi: msg += f"  -  {len(avvisi)} avvisi"
        self._set_stato(msg, colore=colore)

        if not apri_anteprima:
            self.after(800, lambda: self.app.mostra_capitolo(self.slug, self.cap))
        return par_salvato

    def _salva_e_anteprima(self):
        par_id = self._salva(apri_anteprima=True)
        if par_id is None: return
        self.after(400, lambda: self.app.mostra_lettore(self.slug, self.cap, par_id))