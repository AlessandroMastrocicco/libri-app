# -*- coding: utf-8 -*-
"""
estrattore_slide.py - Estrazione di pagine da PDF con anteprima e selezione.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

try:
    from PIL import Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    _HAS_FITZ = False

from app.ui import tema
from app.ui.widgets import (
    bottone_primario,
    bottone_secondario,
    card,
    sottotitolo,
    titolo,
)
from app.core.slide_extract import (
    carica_pagine,
    copia_immagine_negli_appunti,
    elenca_estratti,
    estrai_pdf,
)


# ======================================================================
# Copia file negli appunti (Windows, CF_HDROP)
# ======================================================================

def copia_file_negli_appunti(paths: list[Path]) -> tuple[bool, str]:
    if not sys.platform.startswith("win"):
        return False, "Copia file negli appunti supportata solo su Windows."
    try:
        import win32clipboard  # type: ignore
    except ImportError as e:
        return False, (
            f"Per copiare file negli appunti serve pywin32.\n"
            f"Esegui:  pip install pywin32\n\n({e})"
        )
    try:
        paths_str = [str(Path(p).resolve()) for p in paths]
        files = "\0".join(paths_str) + "\0\0"
        data = files.encode("utf-16-le")
        header = struct.pack("IiiII", 20, 0, 0, 0, 1)
        blob = header + data
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, blob)
        win32clipboard.CloseClipboard()
        return True, f"{len(paths)} file copiati negli appunti."
    except Exception as e:
        return False, f"Errore copia file: {e}"


# ======================================================================
# Popup anteprima
# ======================================================================

class PopupAnteprima(ctk.CTkToplevel):
    def __init__(self, parent, path_img: Path, on_eliminata=None):
        super().__init__(parent)
        self.path_img = path_img
        self.on_eliminata = on_eliminata
        
        self.title(f"Anteprima — {path_img.name}")
        self.configure(fg_color=tema.BG_APP)

        try:
            self.transient(parent)
        except Exception:
            pass

        img = Image.open(str(path_img))
        max_w, max_h = 900, 640
        w, h = img.size
        if w > max_w or h > max_h:
            img.thumbnail((max_w, max_h), Image.LANCZOS)

        ctk_img = ctk.CTkImage(
            light_image=img, dark_image=img,
            size=(img.width, img.height),
        )
        self.geometry(f"{img.width + 40}x{img.height + 130}")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        lbl = ctk.CTkLabel(self, image=ctk_img, text="")
        lbl.image = ctk_img
        lbl.grid(row=0, column=0, padx=20, pady=(20, 8))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=1, column=0, pady=(0, 16))

        ctk.CTkButton(
            btns, text="  Copia immagine",
            width=150, height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._copia_immagine,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Copia file",
            width=130, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._copia_file,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Apri",
            width=110, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self._apri(path_img),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Elimina",
            width=110, height=36,
            fg_color=tema.DISTRUTTIVO, hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._elimina,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btns, text="  Chiudi",
            width=100, height=36,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self.destroy,
        ).pack(side="left", padx=(16, 4))

        self.after(80, self.lift)
        self.after(80, self.focus_force)

    def _copia_immagine(self):
        ok, msg = copia_immagine_negli_appunti(self.path_img)
        if ok:
            messagebox.showinfo("Fatto", msg, parent=self)
        else:
            messagebox.showerror("Errore", msg, parent=self)

    def _copia_file(self):
        ok, msg = copia_file_negli_appunti([self.path_img])
        if ok:
            messagebox.showinfo("Fatto", msg, parent=self)
        else:
            messagebox.showerror("Errore", msg, parent=self)

    def _apri(self, p: Path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], check=False)
            else:
                subprocess.run(["xdg-open", str(p)], check=False)
        except Exception:
            pass

    def _elimina(self):
        if not messagebox.askyesno(
            "Elimina immagine",
            f"Eliminare {self.path_img.name}?\n\nQuesta operazione non e' reversibile.",
            parent=self,
        ):
            return
        try:
            self.path_img.unlink()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile eliminare: {e}", parent=self)
            return
            
        cb = self.on_eliminata
        self.destroy()
        if cb:
            try: cb()
            except Exception: pass


# ======================================================================
# Schermata principale
# ======================================================================

class SchermataEstrattoreSlide(ctk.CTkFrame):
    def __init__(self, parent, app, slug: str):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.slug = slug

        self._pdf_scelto: Path | None = None
        self._cartella_corrente: Path | None = None
        
        # Stati per la modalità: "preview" (mostra le pagine del PDF scelto) o "estratti" (mostra i file estratti)
        self._modo: str = "estratti" 
        
        self._pagine: list[Path] = []            # Solo per modo "estratti"
        self._preview_pdf: list[dict] = []       # Solo per modo "preview"
        
        self._thumbnails: dict[str, ctk.CTkImage] = {}
        self._selezioni: dict[str, ctk.BooleanVar] = {}
        
        self._form_aperto = True
        self._in_corso = False

        self.grid(row=0, column=0, sticky="nsew")
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_main()
        self._ricarica_sidebar()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=280, corner_radius=0)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_rowconfigure(2, weight=1)
        side.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(side, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(14, 6))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            top, text="  Torna al libro",
            height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self.app.mostra_libro(self.slug),
        ).grid(row=0, column=0, sticky="ew", pady=(0, 4))

        self.btn_nuova = ctk.CTkButton(
            top, text="  + Nuova estrazione",
            height=36,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._toggle_form,
        )
        self.btn_nuova.grid(row=1, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkButton(
            top, text="  Aggiorna elenco",
            height=32,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._ricarica_sidebar,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(
            top, text=f"Libro: {self.slug}",
            font=ctk.CTkFont(size=11),
            anchor="w", text_color=tema.TESTO_TENUE,
            wraplength=240,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))

        ctk.CTkLabel(
            side, text="Estrazioni del libro",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 4))

        self.scroll_estratti = ctk.CTkScrollableFrame(
            side, width=250, fg_color=tema.BG_INPUT,
        )
        self.scroll_estratti.grid(row=2, column=0, sticky="nsew",
                                   padx=8, pady=(0, 8))
        self.scroll_estratti.grid_columnconfigure(0, weight=1)

    def _ricarica_sidebar(self):
        for w in self.scroll_estratti.winfo_children():
            w.destroy()

        estratti = elenca_estratti(self.app.root_progetto, self.slug)
        if not estratti:
            ctk.CTkLabel(
                self.scroll_estratti,
                text="(nessuna estrazione)\n\n"
                     "Premi «+ Nuova estrazione» per iniziare.",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=11),
                anchor="w", justify="left",
            ).pack(fill="x", padx=8, pady=8)
            return

        for e in sorted(estratti, key=lambda x: x["dispensa"]):
            attiva = (self._modo == "estratti" and self._cartella_corrente == e["cartella"])
            colore = tema.PRIMARIO if attiva else tema.BG_INPUT_HOVER
            hover = tema.PRIMARIO_HOVER if attiva else tema.NEUTRO_HOVER
            
            # Riga per contenere il bottone e la X per eliminare
            row = ctk.CTkFrame(self.scroll_estratti, fg_color="transparent")
            row.pack(fill="x", padx=4, pady=1)
            row.grid_columnconfigure(0, weight=1)
            
            btn = ctk.CTkButton(
                row,
                text=f"  {e['dispensa']}  ({e['n_pagine']})",
                height=30, corner_radius=6,
                fg_color=colore, hover_color=hover,
                anchor="w",
                font=ctk.CTkFont(size=11),
                command=lambda c=e["cartella"]: self._carica_cartella(c),
            )
            btn.grid(row=0, column=0, sticky="ew")
            
            # Bottone Elimina intera dispensa
            ctk.CTkButton(
                row, text="X", width=28, height=30, corner_radius=6,
                fg_color=tema.DISTRUTTIVO, hover_color=tema.DISTRUTTIVO_HOVER,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda d=e["dispensa"], c=e["cartella"]: self._elimina_estrazione(d, c),
            ).grid(row=0, column=1, padx=(4, 0))

    def _elimina_estrazione(self, dispensa: str, cartella: Path):
        if not messagebox.askyesno(
            "Elimina estrazione",
            f"Vuoi eliminare l'intera estrazione '{dispensa}'?\n\n"
            f"Verranno rimosse tutte le immagini estratte per questa dispensa.\n\n"
            f"Questa operazione non e' reversibile."
        ):
            return
        try:
            shutil.rmtree(cartella)
            if self._cartella_corrente == cartella:
                self._mostra_vuoto()
            self._ricarica_sidebar()
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile eliminare la cartella: {e}")

    # ------------------------------------------------------------------
    # Main
    # ------------------------------------------------------------------

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(0, weight=0)   # form
        main.grid_rowconfigure(1, weight=0)   # toolbar
        main.grid_rowconfigure(2, weight=1, minsize=280)  # griglia

        # card estrazione (comprimibile)
        self.form = self._build_form(main)
        self.form.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # toolbar griglia
        self._build_toolbar(main)

        # griglia thumbnail
        self.scroll_thumbs = ctk.CTkScrollableFrame(
            main, corner_radius=8, fg_color=tema.BG_INPUT,
        )
        self.scroll_thumbs.grid(row=2, column=0, sticky="nsew")

        self._mostra_vuoto()

    def _build_form(self, parent) -> ctk.CTkFrame:
        form = card(parent)
        form.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(
            form, text="Nuova estrazione",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w", text_color=tema.TESTO,
        ).grid(row=0, column=0, columnspan=4, sticky="w",
               padx=16, pady=(12, 4))

        ctk.CTkLabel(
            form,
            text=f"Scegli un PDF: ogni pagina viene salvata come PNG "
                 f"in libri/{self.slug}/slide_estratte/<nome>/.",
            font=ctk.CTkFont(size=12),
            text_color=tema.TESTO_TENUE,
            anchor="w", justify="left", wraplength=800,
        ).grid(row=1, column=0, columnspan=4, sticky="w",
               padx=16, pady=(0, 10))

        ctk.CTkLabel(form, text="Dispensa:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(16, 4), pady=6)
        self.entry_dispensa = ctk.CTkEntry(
            form, width=340, height=32,
            fg_color=tema.BG_INPUT,
            placeholder_text="es. Lezione 03 - Processi",
        )
        self.entry_dispensa.grid(row=2, column=1, columnspan=3,
                                  sticky="w", pady=6, padx=(0, 16))

        ctk.CTkLabel(form, text="Qualita':", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(16, 4), pady=6)
        self.opt_qualita = ctk.CTkOptionMenu(
            form, values=["bassa", "media", "alta", "max"],
            width=120, height=32,
            fg_color=tema.BG_INPUT,
            button_color=tema.NEUTRO,
            button_hover_color=tema.NEUTRO_HOVER,
        )
        self.opt_qualita.set("media")
        self.opt_qualita.grid(row=3, column=1, sticky="w",
                               pady=6, padx=(0, 4))
        ctk.CTkLabel(
            form, text="(96 / 150 / 200 / 300 dpi)",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            anchor="w",
        ).grid(row=3, column=2, columnspan=2, sticky="w",
               pady=6, padx=(0, 16))

        self.lbl_pdf = ctk.CTkLabel(
            form, text="(nessun PDF selezionato)",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            anchor="w", justify="left", wraplength=560,
        )
        self.lbl_pdf.grid(row=4, column=0, columnspan=3,
                           sticky="ew", padx=16, pady=(6, 4))

        bottone_secondario(
            form, "  Scegli PDF...",
            command=self._scegli_pdf,
            width=150,
        ).grid(row=4, column=3, sticky="e", padx=(4, 16), pady=(6, 4))

        azioni = ctk.CTkFrame(form, fg_color="transparent")
        azioni.grid(row=5, column=0, columnspan=4, sticky="ew",
                    padx=16, pady=(4, 12))
        azioni.grid_columnconfigure(1, weight=1)

        self.chk_sovrascrivi = ctk.CTkCheckBox(
            azioni, text="Sovrascrivi se esiste",
            font=ctk.CTkFont(size=12),
        )
        self.chk_sovrascrivi.grid(row=0, column=0, sticky="w")

        self.btn_estrai = bottone_primario(
            azioni, "  Estrai pagine",
            command=self._estrai,
            width=180,
            state="disabled",
        )
        self.btn_estrai.grid(row=0, column=2, sticky="e", padx=(8, 0))

        return form

    def _build_toolbar(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        toolbar.grid_columnconfigure(1, weight=1)

        self.lbl_cartella = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_MOLTO_TENUE,
            anchor="w", justify="left", wraplength=500,
        )
        self.lbl_cartella.grid(row=0, column=0, columnspan=2,
                                sticky="w", padx=(4, 8))

        self.lbl_selezione = ctk.CTkLabel(
            toolbar, text="",
            font=ctk.CTkFont(size=11),
            text_color=tema.TESTO_TENUE,
            anchor="e",
        )
        self.lbl_selezione.grid(row=0, column=2, sticky="e", padx=(0, 8))

        ctk.CTkButton(
            toolbar, text="Seleziona tutto",
            width=130, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self._seleziona_tutte(True),
        ).grid(row=0, column=3, sticky="e", padx=2)

        ctk.CTkButton(
            toolbar, text="Deseleziona",
            width=110, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=lambda: self._seleziona_tutte(False),
        ).grid(row=0, column=4, sticky="e", padx=2)

        self.btn_copia_sel = ctk.CTkButton(
            toolbar, text="Copia selezionate",
            width=170, height=30,
            fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copia_selezionate,
            state="disabled"
        )
        self.btn_copia_sel.grid(row=0, column=5, sticky="e", padx=2)

        self.btn_copia_perc = ctk.CTkButton(
            toolbar, text="Copia percorsi",
            width=140, height=30,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            command=self._copia_percorsi,
            state="disabled"
        )
        self.btn_copia_perc.grid(row=0, column=6, sticky="e", padx=2)

        self.btn_elimina = ctk.CTkButton(
            toolbar, text="Elimina selezionate",
            width=150, height=30,
            fg_color=tema.DISTRUTTIVO,
            hover_color=tema.DISTRUTTIVO_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._elimina_selezionate,
            state="disabled"
        )
        self.btn_elimina.grid(row=0, column=7, sticky="e", padx=(2, 4))

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _toggle_form(self):
        if self._form_aperto:
            self.form.grid_remove()
            self._form_aperto = False
            self.btn_nuova.configure(
                fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER
            )
        else:
            self.form.grid(row=0, column=0, sticky="ew", pady=(0, 8))
            self._form_aperto = True
            self.btn_nuova.configure(
                fg_color=tema.PRIMARIO, hover_color=tema.PRIMARIO_HOVER
            )

    def _scegli_pdf(self):
        percorso = filedialog.askopenfilename(
            title="Scegli la dispensa di slide",
            filetypes=[("PDF", "*.pdf"), ("Tutti i file", "*.*")],
        )
        if not percorso:
            return
        self._pdf_scelto = Path(percorso)
        self.lbl_pdf.configure(text=str(self._pdf_scelto))
        
        self._carica_preview_pdf(self._pdf_scelto)

    def _carica_preview_pdf(self, pdf_path: Path):
        if not _HAS_FITZ:
            messagebox.showerror("Errore", "PyMuPDF non installato. Esegui: pip install pymupdf")
            return
        if not _HAS_PIL:
            messagebox.showerror("Errore", "Pillow non installato. Esegui: pip install pillow")
            return

        self._modo = "preview"
        self._cartella_corrente = None
        self._ricarica_sidebar()
        
        self.lbl_cartella.configure(text=f"Anteprima PDF: {pdf_path.name}")
        
        self.btn_copia_sel.configure(state="disabled")
        self.btn_copia_perc.configure(state="disabled")
        self.btn_elimina.configure(state="disabled")
        
        self.btn_estrai.configure(state="normal")

        self._pagine = []
        self._preview_pdf.clear()
        self._selezioni.clear()
        self._thumbnails.clear()

        for w in self.scroll_thumbs.winfo_children():
            w.destroy()

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile aprire il PDF: {e}")
            return

        cols = 4
        riga_frame = None

        for i, page in enumerate(doc, start=1):
            if i % cols == 1:
                riga_frame = ctk.CTkFrame(self.scroll_thumbs, fg_color="transparent")
                riga_frame.pack(fill="x", padx=4, pady=4)
            
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                thumb = img.copy()
                thumb.thumbnail((200, 200), Image.LANCZOS)
                
                ctk_img = ctk.CTkImage(light_image=thumb, dark_image=thumb, size=(thumb.width, thumb.height))
                
                card_t = ctk.CTkFrame(riga_frame, corner_radius=8, fg_color=tema.BG_CARD, border_width=1, border_color=tema.BG_INPUT_HOVER)
                card_t.pack(side="left", padx=4, pady=2)
                
                lbl_img = ctk.CTkLabel(card_t, image=ctk_img, text="")
                lbl_img.pack(padx=6, pady=(6, 2))
                
                bottom = ctk.CTkFrame(card_t, fg_color="transparent")
                bottom.pack(fill="x", padx=6, pady=(0, 6))
                
                var = ctk.BooleanVar(value=True) # Tutte selezionate in anteprima
                self._selezioni[str(i)] = var
                
                ctk.CTkCheckBox(
                    bottom, text=f"pag. {i}", variable=var,
                    font=ctk.CTkFont(size=11),
                    checkbox_width=18, checkbox_height=18,
                    command=self._aggiorna_contatore
                ).pack(side="left")
                
            except Exception as e:
                print(f"Errore pagina {i}: {e}")
                continue
        
        doc.close()
        self._aggiorna_contatore()

    def _estrai(self):
        if self._in_corso or not self._pdf_scelto:
            return

        dispensa = self.entry_dispensa.get().strip()
        if not dispensa:
            messagebox.showwarning("Dispensa mancante", "Inserisci il nome della dispensa.")
            return

        pagine_sel = []
        for k, var in self._selezioni.items():
            if var.get():
                pagine_sel.append(int(k))

        if not pagine_sel:
            messagebox.showwarning("Nessuna pagina", "Seleziona almeno una pagina da estrarre.")
            return

        if len(pagine_sel) == len(self._selezioni):
            pagine_sel_param = None
        else:
            pagine_sel_param = pagine_sel

        sovrascrivi = bool(self.chk_sovrascrivi.get())
        qualita = self.opt_qualita.get()
        pdf = self._pdf_scelto
        root = self.app.root_progetto
        slug = self.slug

        self._in_corso = True
        self.btn_estrai.configure(state="disabled", text="  Estrazione...")

        def worker():
            try:
                ris = estrai_pdf(
                    root, pdf, slug, dispensa,
                    qualita=qualita, sovrascrivi=sovrascrivi,
                    pagine_selezionate=pagine_sel_param
                )
            except Exception as e:
                ris = {
                    "ok": False, "cartella": None, "pagine": [],
                    "n_pagine": 0, "dpi": 0,
                    "errori": [str(e)], "avvisi": [],
                }
            self.after(0, lambda: self._post_estrazione(ris))

        threading.Thread(target=worker, daemon=True).start()

    def _post_estrazione(self, ris: dict):
        self._in_corso = False
        self.btn_estrai.configure(state="normal", text="  Estrai pagine")

        if not ris.get("ok"):
            messagebox.showerror(
                "Estrazione non riuscita",
                "\n".join(ris.get("errori") or ["Errore sconosciuto."]),
            )
            return

        if ris.get("avvisi"):
            messagebox.showwarning(
                "Estrazione completata con avvisi",
                f"{ris['n_pagine']} pagine a {ris['dpi']} dpi.\n\n"
                + "\n".join(ris["avvisi"][:8]),
            )
        else:
            messagebox.showinfo(
                "Estrazione completata",
                f"{ris['n_pagine']} pagine a {ris['dpi']} dpi\n\n"
                f"Salvate in:\n{ris['cartella']}",
            )

        self._carica_cartella(ris["cartella"])
        self._ricarica_sidebar()

    # ------------------------------------------------------------------
    # Griglia thumbnail (per file estratti)
    # ------------------------------------------------------------------

    def _mostra_vuoto(self):
        self._modo = "estratti"
        for w in self.scroll_thumbs.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.scroll_thumbs,
            text="Seleziona un'estrazione dalla colonna a sinistra,\n"
                 "oppure crea una nuova estrazione.",
            text_color=tema.TESTO_MOLTO_TENUE,
            font=ctk.CTkFont(size=13),
            anchor="center", justify="center",
        ).pack(expand=True, pady=60)
        self.lbl_cartella.configure(text="")
        self.lbl_selezione.configure(text="")
        
        self.btn_copia_sel.configure(state="disabled")
        self.btn_copia_perc.configure(state="disabled")
        self.btn_elimina.configure(state="disabled")
        self.btn_estrai.configure(state="disabled")

    def _carica_cartella(self, cartella: Path):
        self._modo = "estratti"
        self._cartella_corrente = Path(cartella)
        self._pagine = carica_pagine(self._cartella_corrente)
        self.lbl_cartella.configure(
            text=str(self._cartella_corrente),
            text_color=tema.TESTO_MOLTO_TENUE,
        )
        self._ricarica_sidebar()
        
        self.btn_copia_sel.configure(state="normal")
        self.btn_copia_perc.configure(state="normal")
        self.btn_elimina.configure(state="normal")
        self.btn_estrai.configure(state="disabled")
        
        self.after_idle(self._aggiorna_griglia)

    def _aggiorna_griglia(self):
        for w in self.scroll_thumbs.winfo_children():
            w.destroy()
        self._thumbnails.clear()
        self._selezioni.clear()

        if not self._pagine:
            ctk.CTkLabel(
                self.scroll_thumbs,
                text="(nessuna pagina in questa cartella)",
                text_color=tema.TESTO_MOLTO_TENUE,
                font=ctk.CTkFont(size=12),
                anchor="center",
            ).pack(pady=40)
            self._aggiorna_contatore()
            return

        if not _HAS_PIL:
            ctk.CTkLabel(
                self.scroll_thumbs,
                text="Pillow non installato: esegui  pip install pillow",
                text_color=tema.ERRORE,
                anchor="center",
            ).pack(pady=40)
            self._aggiorna_contatore()
            return

        cols = 4
        riga_frame: ctk.CTkFrame | None = None
        for i, p in enumerate(self._pagine):
            if i % cols == 0:
                riga_frame = ctk.CTkFrame(
                    self.scroll_thumbs, fg_color="transparent",
                )
                riga_frame.pack(fill="x", padx=4, pady=4)
            self._crea_thumbnail_in(riga_frame, p)

        self.scroll_thumbs.update_idletasks()
        self._aggiorna_contatore()

    def _crea_thumbnail_in(self, riga_frame: ctk.CTkFrame, path_img: Path):
        try:
            img = Image.open(str(path_img))
        except Exception as e:
            ctk.CTkLabel(
                riga_frame,
                text=f"Err {path_img.stem}: {e}",
                text_color=tema.ERRORE,
                font=ctk.CTkFont(size=10),
                wraplength=200,
            ).pack(side="left", padx=4, pady=4)
            return

        thumb = img.copy()
        thumb.thumbnail((200, 200), Image.LANCZOS)
        ctk_img = ctk.CTkImage(
            light_image=thumb, dark_image=thumb,
            size=(thumb.width, thumb.height),
        )
        self._thumbnails[str(path_img)] = ctk_img

        card_t = ctk.CTkFrame(
            riga_frame, corner_radius=8,
            fg_color=tema.BG_CARD, border_width=1,
            border_color=tema.BG_INPUT_HOVER,
        )
        card_t.pack(side="left", padx=4, pady=2)

        img_lbl = ctk.CTkLabel(
            card_t, image=ctk_img, text="", cursor="hand2",
        )
        img_lbl.pack(padx=6, pady=(6, 2))
        img_lbl.bind(
            "<Button-1>",
            lambda e, p=path_img: self._apri_preview(p),
        )

        bottom = ctk.CTkFrame(card_t, fg_color="transparent")
        bottom.pack(fill="x", padx=6, pady=(0, 6))

        var = ctk.BooleanVar(value=False)
        self._selezioni[str(path_img)] = var

        ctk.CTkCheckBox(
            bottom,
            text=path_img.stem.replace("pagina_", "p."),
            variable=var,
            font=ctk.CTkFont(size=11),
            checkbox_width=18, checkbox_height=18,
            command=self._aggiorna_contatore,
        ).pack(side="left")

        ctk.CTkButton(
            bottom, text="Copia", width=60, height=22,
            fg_color=tema.NEUTRO, hover_color=tema.NEUTRO_HOVER,
            font=ctk.CTkFont(size=10),
            command=lambda p=path_img: self._copia_singola(p),
        ).pack(side="right")

    def _aggiorna_contatore(self):
        n_tot = len(self._selezioni)
        n_sel = sum(1 for v in self._selezioni.values() if v.get())
        
        if n_tot == 0:
            self.lbl_selezione.configure(text="")
        else:
            suffisso = "pagine" if self._modo == "preview" else "selezionate"
            self.lbl_selezione.configure(
                text=f"{n_sel} {suffisso} su {n_tot}"
            )

    # ------------------------------------------------------------------
    # Preview, Copia, Selezione, Eliminazione
    # ------------------------------------------------------------------

    def _apri_preview(self, path_img: Path):
        PopupAnteprima(self, path_img, on_eliminata=self._dopo_eliminazione)

    def _dopo_eliminazione(self):
        if self._cartella_corrente:
            self._carica_cartella(self._cartella_corrente)
        self._ricarica_sidebar()

    def _copia_singola(self, path_img: Path):
        ok, msg = copia_immagine_negli_appunti(path_img)
        if ok:
            self._flash(f"Copiato: {path_img.name}")
            return
        risposta = messagebox.askyesno(
            "Copia non disponibile",
            f"{msg}\n\nVuoi aprire l'immagine nel visualizzatore di "
            f"sistema? Da li' puoi copiarla con Ctrl+C.",
        )
        if risposta:
            self._apri_nel_sistema(path_img)

    def _copia_selezionate(self):
        if self._modo == "preview":
            return
        selezionate = [Path(p) for p, v in self._selezioni.items() if v.get()]
        if not selezionate:
            messagebox.showinfo("Nessuna selezione", "Seleziona almeno una pagina.")
            return
        if len(selezionate) == 1:
            self._copia_singola(selezionate[0])
            return

        scelta = messagebox.askyesnocancel(
            "Copia di piu' pagine",
            f"Hai selezionato {len(selezionate)} pagine.\n\n"
            f"Si: copia i FILE negli appunti\n"
            f"No: copia i PERCORSI come testo\n"
            f"Annulla: non fare nulla",
        )
        if scelta is None:
            return
        if scelta:
            ok, msg = copia_file_negli_appunti(selezionate)
            if ok: self._flash(msg)
            else: messagebox.showerror("Errore", msg)
        else:
            testo = "\n".join(str(p) for p in selezionate)
            try:
                self.clipboard_clear()
                self.clipboard_append(testo)
                self.update()
                self._flash(f"{len(selezionate)} percorsi copiati negli appunti.")
            except Exception as e:
                messagebox.showerror("Errore", f"Impossibile copiare i percorsi: {e}")

    def _copia_percorsi(self):
        if self._modo == "preview":
            return
        selezionate = [Path(p) for p, v in self._selezioni.items() if v.get()]
        if not selezionate:
            selezionate = list(self._pagine)
        if not selezionate:
            return
        testo = "\n".join(str(p) for p in selezionate)
        try:
            self.clipboard_clear()
            self.clipboard_append(testo)
            self.update()
            self._flash(f"{len(selezionate)} percorsi copiati.")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile copiare: {e}")

    def _seleziona_tutte(self, valore: bool):
        for var in self._selezioni.values():
            var.set(valore)
        self._aggiorna_contatore()

    def _elimina_selezionate(self):
        if self._modo == "preview":
            return
        selezionate = [Path(p) for p, v in self._selezioni.items() if v.get()]
        if not selezionate:
            messagebox.showinfo("Nessuna selezione", "Seleziona almeno una pagina da eliminare.")
            return
        if not messagebox.askyesno(
            "Elimina pagine", 
            f"Eliminare {len(selezionate)} pagine?\n\nQuesta operazione non e' reversibile."
        ):
            return
        errori = []
        for p in selezionate:
            try: p.unlink()
            except Exception as e: errori.append(f"{p.name}: {e}")
        
        if errori:
            messagebox.showerror("Errori durante l'eliminazione", "\n".join(errori))
        if self._cartella_corrente:
            self._carica_cartella(self._cartella_corrente)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _flash(self, testo: str):
        if not self._cartella_corrente:
            return
        try:
            self.lbl_cartella.configure(
                text=f"{testo}   ·   {self._cartella_corrente}",
                text_color=tema.SUCCESSO,
            )
            self.after(
                2500,
                lambda: self.lbl_cartella.configure(
                    text=str(self._cartella_corrente),
                    text_color=tema.TESTO_MOLTO_TENUE,
                ),
            )
        except Exception:
            pass

    def _apri_nel_sistema(self, percorso: Path):
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