# -*- coding: utf-8 -*-
"""
lettore.py - Lettore PDF di paragrafi.

Responsabilita' uniche: navigazione capitolo/paragrafo, rendering e
visualizzazione PDF. La rigenerazione AI del testo'e' delegata a
`popup_rigenera` (UI del popup) e `core.ai.rigenera` (logica): qui solo
orchestrazione threading e reload dell'anteprima a successo avvenuto.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import customtkinter as ctk

from app.ui import tema
from app.ui.widgets import (
    bottone_primario,
    bottone_secondario,
    card,
)
from app.ui.pdf_viewer import PdfViewer
from app.core.libro import percorso_libro
from app.core.capitolo import (
    elenca_capitoli,
    leggi_titolo_capitolo,
)
from app.core.paragrafo import (
    elenca_paragrafi,
    leggi_paragrafo,
    leggi_teoria_origine,
)
from app.core.render_paragrafo import (
    cache_valida,
    percorso_cache_pdf,
    renderizza_paragrafo,
)
from app.core.pattern_paragrafo import PATTERN_PARAGRAFO
from app.core.pattern_esercizi import PATTERN_ESERCIZI


class SchermataLettore(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str,
                 cap: int | None = None,
                 par: str | None = None):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        self._cap_sel = cap
        self._par_sel = par
        self._pdf_corrente: Path | None = None
        self._render_in_corso = False

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()

        if self._cap_sel is None or self._par_sel is None:
            self._seleziona_primo_disponibile()

        self._carica_paragrafo_corrente()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=290, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(1, weight=1)
        side.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(side, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(14, 6))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            top, text="  Home", height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.app.mostra_home,
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            top, text="  Torna al libro", height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self.app.mostra_libro(self.slug),
        ).grid(row=1, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(
            top, text=f"Libro: {self.slug}",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", wraplength=250,
        ).grid(row=2, column=0, sticky="ew", pady=(4, 0))

        self.scroll_elenco = ctk.CTkScrollableFrame(
            side, width=260, fg_color=tema.BG_INPUT,
        )
        self.scroll_elenco.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.scroll_elenco.grid_columnconfigure(0, weight=1)

        self._ricarica_sidebar()

    def _ricarica_sidebar(self):
        for w in self.scroll_elenco.winfo_children():
            w.destroy()

        numeri = elenca_capitoli(self.app.root_progetto, self.slug)
        if not numeri:
            ctk.CTkLabel(
                self.scroll_elenco, text="(nessun capitolo)", 
                text_color=tema.TESTO_MOLTO_TENUE, font=ctk.CTkFont(size=12), anchor="w"
            ).pack(fill="x", padx=8, pady=8)
            return

        for cap in numeri:
            titolo_cap = leggi_titolo_capitolo(self.app.root_progetto, self.slug, cap)
            intestazione = f"Capitolo {cap:02d} — {titolo_cap}" if titolo_cap else f"Capitolo {cap:02d}"

            ctk.CTkLabel(
                self.scroll_elenco, text=intestazione, 
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w", wraplength=240
            ).pack(fill="x", padx=6, pady=(10, 2))

            par_ids = elenca_paragrafi(self.app.root_progetto, self.slug, cap)
            if not par_ids:
                ctk.CTkLabel(
                    self.scroll_elenco, text="  (nessun paragrafo)", 
                    text_color=tema.TESTO_MOLTO_TENUE, font=ctk.CTkFont(size=11), anchor="w"
                ).pack(fill="x", padx=16, pady=2)
                continue

            for par_id in par_ids:
                self._bottone_paragrafo(cap, par_id)

    def _bottone_paragrafo(self, cap: int, par_id: str):
        attivo = (cap == self._cap_sel and par_id == self._par_sel)
        colore = tema.PRIMARIO if attivo else tema.NEUTRO
        hover = tema.PRIMARIO_HOVER if attivo else tema.NEUTRO_HOVER
        
        is_ex = par_id.endswith("_esercizi")
        num_str = par_id.replace("_esercizi", "")
        
        if is_ex:
            # Controlla se l'eserciziario è collegato a una teoria diversa
            p = leggi_paragrafo(self.app.root_progetto, self.slug, cap, par_id)
            orig = leggi_teoria_origine(p or "", fallback=num_str)
            
            if orig != num_str:
                testo = f"  ↳ Ex (per {orig})"
            else:
                testo = f"  ↳ Ex"
        else:
            testo = f"  {cap}.{num_str}"

        ctk.CTkButton(
            self.scroll_elenco, text=testo, height=30, corner_radius=6,
            fg_color=colore, hover_color=hover, anchor="w", font=ctk.CTkFont(size=12),
            command=lambda c=cap, p=par_id: self._seleziona(c, p),
        ).pack(fill="x", padx=10, pady=2)

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        toolbar = card(main)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        toolbar.grid_columnconfigure(4, weight=1)

        self.btn_render = bottone_primario(
            toolbar, "  Rigenera anteprima",
            command=self._rigenera,
            width=200,
        )
        self.btn_render.grid(row=0, column=0, padx=(12, 4), pady=10)

        bottone_secondario(
            toolbar, "  Apri cartella libro",
            command=self._apri_cartella_libro,
            width=180,
        ).grid(row=0, column=1, padx=4, pady=10)

        bottone_secondario(
            toolbar, "  Apri nel sistema",
            command=self._apri_col_sistema,
            width=170,
        ).grid(row=0, column=2, padx=4, pady=10)

        # Rigenerazione AI del testo del paragrafo (non del PDF).
        self.btn_rig_ai = bottone_secondario(
            toolbar, "  Rigenera paragrafo",
            command=self._apri_rigenera_ai,
            width=190,
        )
        self.btn_rig_ai.grid(row=0, column=3, padx=4, pady=10)

        self.lbl_stato = ctk.CTkLabel(
            toolbar, text="",
            text_color=tema.TESTO_TENUE,
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self.lbl_stato.grid(row=0, column=4, sticky="w", padx=12)

        self.viewer = PdfViewer(main)
        self.viewer.grid(row=1, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Selezione
    # ------------------------------------------------------------------

    def _seleziona_primo_disponibile(self):
        for cap in elenca_capitoli(self.app.root_progetto, self.slug):
            par_ids = elenca_paragrafi(self.app.root_progetto, self.slug, cap)
            if par_ids:
                self._cap_sel = cap
                self._par_sel = par_ids[0]
                return
        self._cap_sel = None
        self._par_sel = None

    def _seleziona(self, cap: int, par_id: str):
        if self._cap_sel == cap and self._par_sel == par_id:
            return
        self._cap_sel = cap
        self._par_sel = par_id
        self._ricarica_sidebar()
        self._carica_paragrafo_corrente()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _carica_paragrafo_corrente(self):
        if self._cap_sel is None or self._par_sel is None:
            self._set_stato("Seleziona un paragrafo.")
            self.viewer.svuota()
            return

        pdf = percorso_cache_pdf(
            self.app.root_progetto, self.slug,
            self._cap_sel, self._par_sel,
        )
        if cache_valida(
            self.app.root_progetto, self.slug,
            self._cap_sel, self._par_sel,
        ) and pdf.is_file():
            self._pdf_corrente = pdf
            self.viewer.carica(pdf)
            
            is_ex = self._par_sel.endswith("_esercizi")
            tipo = "esercizi" if is_ex else "teoria"
            
            self._set_stato(
                f"Anteprima {self._cap_sel}.{self._par_sel} "
                f"({self.viewer.n_pagine()} pagine, {tipo}, da cache)"
            )
        else:
            self._set_stato(
                f"Anteprima {self._cap_sel}.{self._par_sel} assente. "
                f"Rigenero…"
            )
            self._renderizza(asincrono=True)

    def _rigenera(self):
        if self._cap_sel is None or self._par_sel is None:
            self._set_stato("Nessun paragrafo selezionato.")
            return
        self._renderizza(asincrono=True, forza=True)

    def _renderizza(self, asincrono: bool = True, forza: bool = False):
        if self._render_in_corso:
            return
        if self._cap_sel is None or self._par_sel is None:
            return

        cap, par_id = self._cap_sel, self._par_sel

        if not asincrono:
            self._post_render(
                renderizza_paragrafo(
                    self.app.root_progetto, self.slug, cap, par_id,
                    forza=forza,
                ),
                cap, par_id,
            )
            return

        self._render_in_corso = True
        self.btn_render.configure(state="disabled",
                                  text="  Rendering…")
        self._set_stato(f"Rendering {cap}.{par_id}…")

        def worker():
            try:
                ris = renderizza_paragrafo(
                    self.app.root_progetto, self.slug, cap, par_id,
                    forza=forza,
                )
            except Exception as e:
                ris = {
                    "ok": False, "pdf": None, "da_cache": False,
                    "durata_sec": 0.0, "errore": str(e),
                }
            self.after(0, lambda: self._post_render(ris, cap, par_id))

        threading.Thread(target=worker, daemon=True).start()

    def _post_render(self, ris: dict, cap: int, par_id: str):
        self._render_in_corso = False
        self.btn_render.configure(state="normal",
                                  text="  Rigenera anteprima")

        if not ris.get("ok") or not ris.get("pdf"):
            self._set_stato(
                f"Errore: {ris.get('errore', 'sconosciuto')}",
                colore=tema.ERRORE,
            )
            return

        # solo se e' ancora il paragrafo selezionato
        if cap == self._cap_sel and par_id == self._par_sel:
            self._pdf_corrente = Path(ris["pdf"])
            self.viewer.carica(self._pdf_corrente)

        da_cache = " (da cache)" if ris.get("da_cache") else ""
        self._set_stato(
            f"Anteprima {cap}.{par_id} pronta in "
            f"{ris['durata_sec']:.2f}s{da_cache}",
            colore=tema.SUCCESSO,
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Rigenerazione AI del paragrafo (popup istruzioni -> core.ai.rigenera)
    # ------------------------------------------------------------------

    def _apri_rigenera_ai(self):
        """Bottone 'Rigenera paragrafo': apre il popup con la casella delle
        istruzioni. Il modello ricevera' fonti (slide coinvolte), versione
        attuale, linee guida e indicazioni dell'utente (vedi core.ai.rigenera).
        """
        if self._cap_sel is None or self._par_sel is None:
            self._set_stato("Seleziona prima un paragrafo.", colore=tema.ERRORE)
            return
        contenuto = leggi_paragrafo(
            self.app.root_progetto, self.slug, self._cap_sel, self._par_sel)
        if not contenuto or not contenuto.strip():
            self._set_stato("Il paragrafo non ha codice: niente da rigenerare.",
                            colore=tema.ERRORE)
            return
        from app.core.paragrafo import titolo_da_sorgente
        titolo_par = titolo_da_sorgente(contenuto,
                                         fallback=f"{self._cap_sel}.{self._par_sel}")
        cap, par_id = self._cap_sel, self._par_sel

        from app.screens.popup_rigenera import PopupRigeneraParagrafo
        PopupRigeneraParagrafo(
            self, titolo_par=titolo_par,
            avvia=lambda istr, cb: self._avvia_rigenera_ai(
                cap, par_id, istr, contenuto, cb),
            on_fine=lambda esito, note: self._fine_rigenera_ai(
                cap, par_id, esito, note))

    def _avvia_rigenera_ai(self, cap: int, par_id: str, istruzioni: str,
                           contenuto: str, cb):
        """Esegue core.ai.rigenera nel thread gia' avviato dal popup."""
        from app.core.ai.impostazioni import LeggiChiavi
        from app.core.ai.providers import costruisci_fornitore
        from app.core.ai.rigenera import rigenera_paragrafo
        from app.core.ai.router import Router as _Router
        from app.core.paragrafo import aggiorna_paragrafo, valida_contenuto
        from app.core.render_paragrafo import invalida_cache_paragrafo

        radice = self.app.root_progetto
        letture = LeggiChiavi(radice)
        if not letture.consenso_cloud():
            cb(None, ["Servono chiavi API nel file .env e il consenso cloud "
                      "in libri/_ai_config.json (privacy.consenso_cloud=true), "
                      "oppure Ollama locale."])
            return
        esercizi = par_id.endswith("_esercizi")
        pattern = PATTERN_ESERCIZI.format(teoria_origine="—") if esercizi \
            else PATTERN_PARAGRAFO
        router = _Router(path_stato=radice / "libri" / "_ai_quota.json")
        fornitore = costruisci_fornitore(radice)
        esito, note = rigenera_paragrafo(
            router=router, provider=fornitore.chiama, root=radice,
            slug=self.slug, cap=cap, par_id=par_id,
            contenuto=contenuto, istruzioni_utente=istruzioni,
            pattern_completo=pattern,
            valida_fn=lambda c: valida_contenuto(
                c, root=radice, slug=self.slug, cap=cap))
        cb(esito, note)

    def _fine_rigenera_ai(self, cap: int, par_id: str, esito, note):
        """Su successo: backup dell'originale (.bak.txt), salvataggio della
        bozza (.bozza.txt), APPLICAZIONE al paragrafo (aggiorna_paragrafo che
        ne fa gia' un backup interno), cache PDF invalidata e nuova anteprima.
        Un pulsante 'Annulla' ripristina l'originale con la stessa procedura."""
        for n in note or []:
            print(f"[rigenera-lettore] {n}")
        if esito is None or not getattr(esito, "ok", False):
            msg = (note[0] if (note and esito is None)
                   else getattr(esito, "errore", "esito assente"))
            self._set_stato(f"Rigenerazione fallita: {msg}", colore=tema.ERRORE)
            return
        # se nel frattempo l'utente ha cambiato paragrafo, non applicare qui
        if (cap, par_id) != (self._cap_sel, self._par_sel):
            self._set_stato("Paragrafo cambiato: bozza non applicata.",
                            colore=tema.AVVISO)
            return

        from app.core.paragrafo import percorso_paragrafo
        p_file = percorso_paragrafo(self.app.root_progetto, self.slug,
                                    cap, par_id)
        originale = leggi_paragrafo(self.app.root_progetto, self.slug,
                                    cap, par_id) or ""
        # 1) backup espliciti (atomici tmp+replace, come da io_sicuro)
        cart = p_file.parent
        for nome, testo in ((f"{par_id}.bak.txt", originale),
                            (f"{par_id}.bozza.txt", esito.contenuto or "")):
            tmp = cart / (nome + ".tmp")
            tmp.write_text(testo, encoding="utf-8")
            tmp.replace(cart / nome)
        # 2) applica la bozza al paragrafo reale
        risultato = aggiorna_paragrafo(self.app.root_progetto, self.slug,
                                       cap, par_id, esito.contenuto or "")
        if not risultato.get("ok"):
            err = " | ".join(risultato.get("errori") or ["errore sconosciuto"])
            self._set_stato(f"Bozza salva ma non applicata: {err} "
                            f"(vedi {par_id}.bozza.txt)", colore=tema.ERRORE)
            return
        invalida_cache_paragrafo(self.app.root_progetto, self.slug,
                                 cap, par_id)
        # 3) messaggio con annullamento a portata di click
        self._testo_annulla = ("  Annulla rigenerazione" if originale.strip()
                               else None)
        self._backup_prima = cart / f"{par_id}.bak.txt"
        self._set_stato(
            f"Paragrafo rigenerato ({esito.modello_finale}, "
            f"{esito.token_totali:,} token). "
            + ("Premi 'Annulla rigenerazione' per ripristinare."
               if self._testo_annulla else ""),
            colore=tema.SUCCESSO)
        self.btn_render.configure(text=self._testo_annulla or
                                  "  Rigenera anteprima",
                                  command=(self._annulla_rigenera
                                           if self._testo_annulla else
                                           self._rigenera))
        # 4) nuova anteprima del paragrafo rigenerato
        self._renderizza(asincrono=True, forza=True)

    def _annulla_rigenera(self):
        """Ripristina il paragrafo dal backup pre-rigenerazione."""
        bak = getattr(self, "_backup_prima", None)
        cap, par_id = self._cap_sel, self._par_sel
        if not bak or not bak.is_file() or cap is None or par_id is None:
            self.btn_render.configure(text="  Rigenera anteprima",
                                      command=self._rigenera)
            return
        from app.core.paragrafo import percorso_paragrafo
        testo = bak.read_text(encoding="utf-8")
        risultato = aggiorna_paragrafo(self.app.root_progetto, self.slug,
                                       cap, par_id, testo)
        if risultato.get("ok"):
            invalida_cache_paragrafo(self.app.root_progetto, self.slug,
                                     cap, par_id)
            self._set_stato("Ripristinata la versione precedente.",
                            colore=tema.AVVISO)
            self.btn_render.configure(text="  Rigenera anteprima",
                                      command=self._rigenera)
            self._renderizza(asincrono=True, forza=True)
        else:
            self._set_stato("Ripristino fallito: "
                            + " | ".join(risultato.get("errori") or []),
                            colore=tema.ERRORE)

    def _set_stato(self, testo: str, colore: str = tema.TESTO_TENUE):
        try:
            self.lbl_stato.configure(text=testo, text_color=colore)
        except Exception:
            pass

    def _apri_cartella_libro(self):
        p = percorso_libro(self.app.root_progetto, self.slug)
        self._apri(p)

    def _apri_col_sistema(self):
        if self._pdf_corrente and self._pdf_corrente.exists():
            self._apri(self._pdf_corrente)

    def _apri(self, percorso):
        if not percorso or not percorso.exists():
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