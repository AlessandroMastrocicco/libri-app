# -*- coding: utf-8 -*-
"""Tour guidato delle schermate dell'applicazione."""

from __future__ import annotations

import tempfile
from pathlib import Path

import customtkinter as ctk

from app.core.capitolo import crea_capitolo
from app.core.libro import crea_libro
from app.ui import tema
from app.ui.widgets import bottone_primario, bottone_secondario, card


def coordinate_centro_schermo(larghezza: int, altezza: int,
                              larghezza_schermo: int,
                              altezza_schermo: int) -> tuple[int, int]:
    return (
        max(0, (larghezza_schermo - larghezza) // 2),
        max(0, (altezza_schermo - altezza) // 2),
    )


class TutorialWizard(ctk.CTkToplevel):
    def __init__(self, parent, on_finish=None):
        super().__init__(parent)

        self.app = parent
        self.on_finish = on_finish
        self.step = 0
        self._chiuso = False
        self._root_originale = self.app.root_progetto
        self._directory_demo = tempfile.TemporaryDirectory(
            prefix="LIBRI_tour_guidato_"
        )
        self._root_demo = Path(self._directory_demo.name)
        self._slug_demo = "LibroTourGuidato"

        try:
            self._prepara_dati_demo()
            self.app.root_progetto = self._root_demo
            self.title("Tour guidato di LIBRI")
            self.geometry("570x310")
            self.resizable(False, False)
            self.configure(fg_color=tema.BG_APP)
            self.transient(parent)
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self._build_ui()
            self._mostra_step()
            self._posiziona_al_centro_schermo()
            self.protocol("WM_DELETE_WINDOW", self._chiudi)
            self.after(80, self.lift)
            self.after(80, self.focus_force)
        except Exception:
            self.app.root_progetto = self._root_originale
            self._directory_demo.cleanup()
            self.destroy()
            raise

    def _prepara_dati_demo(self):
        risultato_libro = crea_libro(
            self._root_demo,
            {
                "slug": self._slug_demo,
                "titolo": "Libro dimostrativo",
                "soggetto": "Tour guidato",
                "dominio": "Dimostrazione",
                "autore": "",
            },
        )
        if not risultato_libro["ok"]:
            raise RuntimeError(
                "Impossibile preparare il libro dimostrativo: "
                + " | ".join(risultato_libro["errori"])
            )

        risultato_capitolo = crea_capitolo(
            self._root_demo,
            self._slug_demo,
            1,
            titolo="Capitolo dimostrativo",
        )
        if not risultato_capitolo["ok"]:
            raise RuntimeError(
                "Impossibile preparare il capitolo dimostrativo: "
                + " | ".join(risultato_capitolo["errori"])
            )

    def _build_ui(self):
        box = card(self)
        box.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(2, weight=1)

        self.lbl_titolo = ctk.CTkLabel(
            box,
            text="",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=tema.PRIMARIO,
            anchor="w",
        )
        self.lbl_titolo.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 2))

        self.lbl_progresso = ctk.CTkLabel(
            box,
            text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=tema.TESTO_MOLTO_TENUE,
            anchor="w",
        )
        self.lbl_progresso.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))

        self.txt_spiegazione = ctk.CTkTextbox(
            box,
            height=100,
            font=ctk.CTkFont(size=13),
            wrap="word",
            fg_color="transparent",
            text_color=tema.TESTO,
        )
        self.txt_spiegazione.grid(
            row=2, column=0, sticky="nsew", padx=18, pady=(0, 8)
        )
        self.txt_spiegazione.configure(state="disabled")

        footer = ctk.CTkFrame(box, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        footer.grid_columnconfigure(1, weight=1)

        bottone_secondario(
            footer, "Termina tour", command=self._chiudi, width=120, height=36
        ).grid(row=0, column=0, sticky="w")
        self.lbl_schermata = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
        )
        self.lbl_schermata.grid(row=0, column=1, sticky="ew", padx=8)
        self.btn_prev = bottone_secondario(
            footer, "Indietro", command=self._prev, width=95, height=36
        )
        self.btn_prev.grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.btn_next = bottone_primario(
            footer, "Avanti", command=self._next, width=110, height=36
        )
        self.btn_next.grid(row=0, column=3, sticky="e")

        self.steps = [
            {
                "titolo": "Benvenuto nel tour di LIBRI",
                "testo": (
                    "Vedrai le schermate principali e il flusso per creare "
                    "un libro. Premi Avanti per proseguire: il tour naviga "
                    "nell'app e usa un libro dimostrativo temporaneo, senza "
                    "modificare i tuoi libri."
                ),
                "schermata": "home",
            },
            {
                "titolo": "Home",
                "testo": (
                    "Qui trovi i tuoi libri e il comando per crearne uno. "
                    "Selezionando un libro accedi a capitoli, paragrafi, "
                    "lettore, slide e immagini."
                ),
                "schermata": "home",
            },
            {
                "titolo": "Creazione di un libro",
                "testo": (
                    "La schermata prepara un nuovo libro: compila nome e "
                    "metadati e conferma per creare la struttura di cartelle. "
                    "I prompt iniziali aiutano a impostare il lavoro con l'AI."
                ),
                "schermata": "crea_libro",
            },
            {
                "titolo": "Scheda del libro",
                "testo": (
                    "La scheda riassume capitoli e paragrafi e dà accesso alle "
                    "azioni del libro. Per questo tour è stato creato "
                    "«LibroTourGuidato» in una cartella temporanea."
                ),
                "schermata": "libro",
            },
            {
                "titolo": "Gestione dei capitoli",
                "testo": (
                    "Da Modifica libro puoi creare capitoli e aprirli per "
                    "gestire i paragrafi. Il capitolo mostrato è un esempio "
                    "temporaneo, predisposto per il tour."
                ),
                "schermata": "modifica_libro",
            },
            {
                "titolo": "Creazione di un capitolo",
                "testo": (
                    "Inserisci titolo e numero del capitolo. Il capitolo "
                    "organizza i paragrafi e può essere modificato "
                    "separatamente."
                ),
                "schermata": "crea_capitolo",
            },
            {
                "titolo": "Paragrafi",
                "testo": (
                    "Apri un capitolo per consultare i paragrafi o crearne "
                    "uno. Il codice generato dall'AI si incolla nell'editor, "
                    "dove puoi validarlo e salvarlo."
                ),
                "schermata": "capitolo",
            },
            {
                "titolo": "Scrittura e fonti",
                "testo": (
                    "Qui trovi le regole di scrittura: privilegia la prosa "
                    "discorsiva e usa definizioni, esempi, avvertenze e altri "
                    "riquadri quando aiutano davvero la spiegazione. Puoi "
                    "allegare slide e pagine di risorse extra."
                ),
                "schermata": "crea_paragrafo",
            },
            {
                "titolo": "Slide e immagini",
                "testo": (
                    "L'estrattore converte le pagine di un PDF in immagini; "
                    "seleziona le pagine da estrarre e associale poi ai "
                    "paragrafi che le richiedono."
                ),
                "schermata": "estrattore_slide",
            },
            {
                "titolo": "Gestione immagini",
                "testo": (
                    "Organizza le figure e gli altri materiali grafici del "
                    "libro. Questa schermata consente di ispezionarli e "
                    "prepararli per l'associazione ai paragrafi."
                ),
                "schermata": "gestione_immagini",
            },
            {
                "titolo": "Lettura e anteprima",
                "testo": (
                    "Il lettore mostra l'anteprima PDF. Dopo aver salvato i "
                    "paragrafi puoi rigenerare il PDF e consultare il libro "
                    "impaginato. Il tour termina qui."
                ),
                "schermata": "lettore",
            },
        ]

    def _mostra_schermata(self, nome: str):
        metodi = {
            "home": self.app.mostra_home,
            "crea_libro": self.app.mostra_crea_libro,
            "libro": lambda: self.app.mostra_libro(self._slug_demo),
            "modifica_libro": lambda: self.app.mostra_modifica_libro(
                self._slug_demo
            ),
            "crea_capitolo": lambda: self.app.mostra_crea_capitolo(
                self._slug_demo
            ),
            "capitolo": lambda: self.app.mostra_capitolo(self._slug_demo, 1),
            "crea_paragrafo": lambda: self.app.mostra_crea_paragrafo(
                self._slug_demo, 1
            ),
            "estrattore_slide": lambda: self.app.mostra_estrattore_slide(
                self._slug_demo
            ),
            "gestione_immagini": lambda: self.app.mostra_gestione_immagini(
                self._slug_demo
            ),
            "lettore": lambda: self.app.mostra_lettore(self._slug_demo),
        }
        metodi[nome]()

    def _mostra_step(self):
        dati = self.steps[self.step]
        self._mostra_schermata(dati["schermata"])
        self.lbl_titolo.configure(text=dati["titolo"])
        self.lbl_progresso.configure(
            text=f"Passaggio {self.step + 1} di {len(self.steps)}"
        )
        self.txt_spiegazione.configure(state="normal")
        self.txt_spiegazione.delete("1.0", "end")
        self.txt_spiegazione.insert("1.0", dati["testo"])
        self.txt_spiegazione.configure(state="disabled")
        self.lbl_schermata.configure(text="La schermata dell'app è dietro questo riquadro.")
        self.btn_prev.configure(
            state="normal" if self.step else "disabled"
        )
        self.btn_next.configure(
            text="Termina" if self.step == len(self.steps) - 1 else "Avanti"
        )
        self.lift()

    def _next(self):
        if self.step < len(self.steps) - 1:
            self.step += 1
            self._mostra_step()
        else:
            self._chiudi()

    def _prev(self):
        if self.step > 0:
            self.step -= 1
            self._mostra_step()

    def _chiudi(self):
        if self._chiuso:
            return
        self._chiuso = True
        try:
            self.app.root_progetto = self._root_originale
            self.app.mostra_home()
            if self.on_finish:
                self.on_finish()
        finally:
            self._directory_demo.cleanup()
            self.destroy()

    def _posiziona_al_centro_schermo(self):
        self.update_idletasks()
        larghezza = self.winfo_width()
        altezza = self.winfo_height()
        x, y = coordinate_centro_schermo(
            larghezza, altezza,
            self.winfo_screenwidth(), self.winfo_screenheight(),
        )
        self.geometry(f"+{x}+{y}")
