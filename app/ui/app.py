# -*- coding: utf-8 -*-
"""
app.py - Finestra principale e routing tra le schermate.
"""

from __future__ import annotations

import sys
from queue import Empty, Queue
from pathlib import Path
from threading import Thread
from tkinter import TclError

import customtkinter as ctk

from app.ui import tema
from app.ui.breadcrumb import Breadcrumb
from app.ui.tutorial import TutorialWizard
from app.ui.popup_aggiornamento import PopupAggiornamento
from app.core.updater import controlla_aggiornamenti

from app.screens.home import SchermataHome
from app.screens.crea_libro import SchermataCreaLibro
from app.screens.libro_dettaglio import SchermataLibro
from app.screens.modifica_libro import SchermataModificaLibro
from app.screens.crea_capitolo import SchermataCreaCapitolo
from app.screens.capitolo import SchermataCapitolo
from app.screens.crea_paragrafo import SchermataCreaParagrafo
from app.screens.lettore import SchermataLettore
from app.screens.estrattore_slide import SchermataEstrattoreSlide
from app.screens.gestione_immagini import SchermataGestioneImmagini


class App(ctk.CTk):
    """Finestra principale. Si occupa solo di cambiare schermata."""

    def __init__(self, root_progetto: Path):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root_progetto = Path(root_progetto).resolve()

        self.title("LIBRI")
        self.minsize(1000, 640)
        self.configure(fg_color=tema.BG_APP)
        self._imposta_icona()

        self._fullscreen = False
        self._tour_attivo = False
        self._aggiornamento_in_attesa = None
        self._coda_aggiornamenti: Queue[dict | None] = Queue()

        self.topbar = ctk.CTkFrame(
            self, fg_color=tema.BG_APP, height=44,
        )
        self.topbar.pack(side="top", fill="x", padx=0, pady=0)
        self.topbar.pack_propagate(False)

        self.breadcrumb = Breadcrumb(self.topbar)
        self.breadcrumb.pack(fill="x", padx=24, pady=(10, 6))

        ctk.CTkFrame(
            self, fg_color=tema.BG_INPUT, height=1,
        ).pack(side="top", fill="x")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self._schermata = None

        self.bind("<F11>", lambda e: self._toggle_fullscreen())
        self.bind("<Escape>", lambda e: self._esci_fullscreen())

        self.mostra_home()
        self.after(50, self._massimizza)
        
        # Controllo del tutorial (avvio primario)
        self.after(500, self._controlla_primo_avvio)
        
        # Controllo degli aggiornamenti (in background leggero)
        self.after(1500, self._controlla_aggiornamenti)

    def _imposta_icona(self):
        if sys.platform != "win32":
            return
        if getattr(sys, "frozen", False):
            root_risorse = Path(sys._MEIPASS)
        else:
            root_risorse = Path(__file__).resolve().parents[2]
        percorso_icona = root_risorse / "assets" / "libri.ico"
        try:
            self.iconbitmap(default=str(percorso_icona))
        except TclError as e:
            print(f"[app] Impossibile impostare l'icona della finestra: {e}")

    # ------------------------------------------------------------------
    # Gestione Primo Avvio (Tutorial)
    # ------------------------------------------------------------------

    def _controlla_primo_avvio(self):
        flag_path = self.root_progetto / ".tutorial_completato"
        
        if not flag_path.exists():
            self.avvia_tour_guidato(on_finish=self._segna_tutorial_completato)

    def _segna_tutorial_completato(self):
        flag_path = self.root_progetto / ".tutorial_completato"
        try:
            flag_path.touch()
        except OSError as e:
            print(f"[app] Impossibile salvare il completamento del tutorial: {e}")

    def avvia_tour_guidato(self, on_finish=None):
        if self._tour_attivo:
            return

        self._tour_attivo = True

        def al_termine():
            self._tour_attivo = False
            if on_finish:
                on_finish()
            if self._aggiornamento_in_attesa:
                dati = self._aggiornamento_in_attesa
                self._aggiornamento_in_attesa = None
                self.after(0, lambda: self._mostra_aggiornamento(dati))

        try:
            TutorialWizard(self, on_finish=al_termine)
        except Exception:
            self._tour_attivo = False
            raise

    # ------------------------------------------------------------------
    # Controllo Aggiornamenti
    # ------------------------------------------------------------------

    def _controlla_aggiornamenti(self):
        Thread(
            target=self._controlla_aggiornamenti_in_background,
            name="LIBRI-update-check",
            daemon=True,
        ).start()
        self.after(100, self._leggi_risultato_aggiornamenti)

    def _controlla_aggiornamenti_in_background(self):
        try:
            dati = controlla_aggiornamenti(self.root_progetto)
        except Exception as e:
            print(f"[app] Errore controllo aggiornamenti: {e}")
            dati = None
        self._coda_aggiornamenti.put(dati)

    def _leggi_risultato_aggiornamenti(self):
        try:
            dati = self._coda_aggiornamenti.get_nowait()
        except Empty:
            self.after(100, self._leggi_risultato_aggiornamenti)
            return
        if dati:
            self._mostra_aggiornamento(dati)

    def _mostra_aggiornamento(self, dati: dict):
        if self._tour_attivo:
            self._aggiornamento_in_attesa = dati
            return
        PopupAggiornamento(self, dati)

    # ------------------------------------------------------------------
    # Finestra
    # ------------------------------------------------------------------

    def _massimizza(self):
        try:
            self.state("zoomed")
            return
        except Exception:
            pass
        try:
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")
        except Exception:
            pass

    def _entra_fullscreen(self):
        try:
            self.attributes("-fullscreen", True)
            self._fullscreen = True
        except Exception:
            pass

    def _esci_fullscreen(self):
        if not self._fullscreen:
            return
        try:
            self.attributes("-fullscreen", False)
            self._fullscreen = False
        except Exception:
            pass
        self.after(50, self._massimizza)

    def _toggle_fullscreen(self):
        if self._fullscreen:
            self._esci_fullscreen()
        else:
            self._entra_fullscreen()

    # ------------------------------------------------------------------
    # Breadcrumb
    # ------------------------------------------------------------------

    def _aggiorna_breadcrumb(self, voci: list):
        self.breadcrumb.imposta(voci)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _svuota(self):
        for w in self.container.winfo_children():
            w.destroy()

    def mostra_home(self):
        self._svuota()
        self.title("LIBRI - Home")
        self._aggiorna_breadcrumb([("Home", None)])
        self._schermata = SchermataHome(self.container, self)

    def mostra_crea_libro(self):
        self._svuota()
        self.title("LIBRI - Nuovo libro")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            ("Nuovo libro", None),
        ])
        self._schermata = SchermataCreaLibro(self.container, self)

    def mostra_libro(self, slug: str):
        self._svuota()
        self.title(f"LIBRI - {slug}")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, None),
        ])
        self._schermata = SchermataLibro(self.container, self, slug)

    def mostra_modifica_libro(self, slug: str):
        self._svuota()
        self.title(f"LIBRI - {slug} - Modifica libro")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Modifica", None),
        ])
        self._schermata = SchermataModificaLibro(self.container, self, slug)

    def mostra_crea_capitolo(self, slug: str):
        self._svuota()
        self.title(f"LIBRI - {slug} - Nuovo capitolo")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Modifica", lambda s=slug: self.mostra_modifica_libro(s)),
            ("Nuovo capitolo", None),
        ])
        self._schermata = SchermataCreaCapitolo(self.container, self, slug)

    def mostra_capitolo(self, slug: str, cap: int):
        self._svuota()
        self.title(f"LIBRI - {slug} - Capitolo {cap:02d}")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Modifica", lambda s=slug: self.mostra_modifica_libro(s)),
            (f"Capitolo {cap:02d}",
             lambda s=slug, c=cap: self.mostra_capitolo(s, c)),
        ])
        self._schermata = SchermataCapitolo(self.container, self, slug, cap)

    def mostra_crea_paragrafo(self, slug: str, cap: int,
                              par: str | None = None):
        self._svuota()
        if par is None:
            self.title(f"LIBRI - {slug} - Nuovo paragrafo")
            ultima = "Nuovo paragrafo"
        else:
            is_ex = par.endswith("_esercizi")
            tipo = "Eserciziario" if is_ex else "Paragrafo"
            num = par.replace("_esercizi", "")
            self.title(f"LIBRI - {slug} - {tipo} {cap}.{num}")
            ultima = f"{tipo} {cap}.{num}"
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Modifica", lambda s=slug: self.mostra_modifica_libro(s)),
            (f"Capitolo {cap:02d}",
             lambda s=slug, c=cap: self.mostra_capitolo(s, c)),
            (ultima, None),
        ])
        self._schermata = SchermataCreaParagrafo(
            self.container, self, slug, cap, par
        )

    def mostra_lettore(self, slug: str,
                       cap: int | None = None,
                       par: str | None = None):
        self._svuota()
        if cap is not None and par is not None:
            is_ex = par.endswith("_esercizi")
            num = par.replace("_esercizi", "")
            tipo = "Esercizi" if is_ex else "Anteprima"
            self.title(f"LIBRI - {slug} - {tipo} {cap}.{num}")
            ultima = f"{tipo} {cap}.{num}"
        else:
            self.title(f"LIBRI - {slug} - Lettore")
            ultima = "Lettore"
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            (ultima, None),
        ])
        self._schermata = SchermataLettore(
            self.container, self, slug, cap, par
        )

    def mostra_estrattore_slide(self, slug: str):
        self._svuota()
        self.title(f"LIBRI - {slug} - Estrattore slide")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Estrattore slide", None),
        ])
        self._schermata = SchermataEstrattoreSlide(
            self.container, self, slug
        )

    def mostra_gestione_immagini(self, slug: str):
        self._svuota()
        self.title(f"LIBRI - {slug} - Gestione immagini")
        self._aggiorna_breadcrumb([
            ("Home", self.mostra_home),
            (slug, lambda s=slug: self.mostra_libro(s)),
            ("Gestione immagini", None),
        ])
        self._schermata = SchermataGestioneImmagini(
            self.container, self, slug
        )