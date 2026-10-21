# -*- coding: utf-8 -*-
"""
screenshot.py - Strumento di cattura rettangolare dallo schermo.

Apre un overlay a schermo intero senza decorazioni, semi-trasparente,
che mostra lo schermo corrente (snapshot), lascia all'utente disegnare
un rettangolo, e restituisce l'immagine PIL ritagliata.

Uso:
    from app.core.screenshot import cattura_rettangolo
    img = cattura_rettangolo(parent)  # bloccante; PIL.Image o None

Il controllo e' bloccante: la funzione ritorna solo dopo che l'utente
ha confermato (Invio / doppio click) oppure annullato (Esc / chiudi).
"""

from __future__ import annotations

import sys
import tkinter as tk

try:
    from PIL import Image, ImageGrab, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False


def pil_disponibile() -> bool:
    return _HAS_PIL


# ======================================================================
# Rimozione forzata delle decorazioni (solo Windows)
# ======================================================================

def _rimuovi_decorazioni_win32(window):
    """
    Rimuove barra del titolo, bordi, pulsanti min/max/close da una
    finestra Tk usando le API Win32. Necessario perche' su Windows
    overrideredirect() viene spesso ignorato quando la finestra e'
    figlia di un'altra finestra (CustomTkinter).

    Non fa nulla su piattaforme non Windows o se la chiamata fallisce.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
    except Exception:
        return

    try:
        GWL_STYLE = -16
        GWL_EXSTYLE = -20
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000
        WS_BORDER = 0x00800000
        WS_DLGFRAME = 0x00400000
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        SWP_FRAMECHANGED = 0x0020
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_SHOWWINDOW = 0x0040

        hwnd = window.winfo_id()

        user32 = ctypes.windll.user32
        # rimuovi i bit di stile che disegnano la cornice
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style &= ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX |
                   WS_MAXIMIZEBOX | WS_SYSMENU | WS_BORDER | WS_DLGFRAME)
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        # rimuovi dallo stile esteso la voce in taskbar
        exstyle = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        exstyle &= ~WS_EX_APPWINDOW
        exstyle |= WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, exstyle)

        # applica le modifiche
        user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE |
            SWP_NOZORDER | SWP_SHOWWINDOW,
        )
    except Exception:
        pass


def _metti_in_primo_piano_win32(window):
    """Porta la finestra in primo piano a livello Win32 (HWND_TOPMOST)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        SWP_SHOWWINDOW = 0x0040
        hwnd = window.winfo_id()
        ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, 0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
        )
    except Exception:
        pass


# ======================================================================
# Cattura
# ======================================================================

def cattura_rettangolo(parent=None):
    """
    Apre l'overlay di selezione. Blocca finché l'utente non conferma
    o annulla. Ritorna:
    - PIL.Image  se l'utente ha selezionato un rettangolo e confermato
    - None       se ha annullato o se PIL non e' disponibile
    """
    if not _HAS_PIL:
        return None

    # 1) Screenshot dello schermo intero
    try:
        screenshot = ImageGrab.grab()
    except Exception:
        return None

    # 2) Root di riferimento (la finestra CTk o la root Tk)
    root = None
    if parent is not None:
        try:
            root = parent.winfo_toplevel()
        except Exception:
            root = None

    # 3) Crea il Toplevel
    top = tk.Toplevel(root) if root is not None else tk.Tk()

    sw = top.winfo_screenwidth()
    sh = top.winfo_screenheight()

    # 4) Imposta gli attributi Tk PRIMA di mostrare
    try:
        top.overrideredirect(True)
    except Exception:
        pass
    try:
        top.geometry(f"{sw}x{sh}+0+0")
    except Exception:
        pass
    try:
        top.attributes("-topmost", True)
    except Exception:
        pass
    try:
        top.configure(cursor="cross", bg="black")
    except Exception:
        pass

    # 5) Forza rimozione decorazioni Win32 (fix principale)
    top.update_idletasks()
    top.update()
    _rimuovi_decorazioni_win32(top)

    # 6) Prepara l'immagine schermo scurita
    dimmed = screenshot.copy()
    overlay = Image.new("RGB", dimmed.size, (0, 0, 0))
    dimmed = Image.blend(dimmed, overlay, 0.35)

    # allinea la dimensione al formato finestra (scaling Windows)
    if dimmed.size != (sw, sh):
        dimmed = dimmed.resize((sw, sh), Image.LANCZOS)

    tk_full = ImageTk.PhotoImage(dimmed)

    canvas = tk.Canvas(
        top, highlightthickness=0, bd=0,
        width=sw, height=sh, bg="black",
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_image(0, 0, image=tk_full, anchor="nw")
    canvas.image = tk_full

    result = {"image": None}
    state = {
        "x0": 0, "y0": 0, "x1": 0, "y1": 0,
        "rect": None, "drawing": False,
    }

    # 7) Handler mouse / tastiera

    def on_press(e):
        state["x0"] = e.x
        state["y0"] = e.y
        state["x1"] = e.x
        state["y1"] = e.y
        state["drawing"] = True
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            e.x, e.y, e.x, e.y,
            outline="#00d4ff", width=2,
        )

    def on_drag(e):
        if not state["drawing"]:
            return
        state["x1"] = e.x
        state["y1"] = e.y
        canvas.coords(
            state["rect"],
            state["x0"], state["y0"],
            state["x1"], state["y1"],
        )

    def on_release(e):
        state["drawing"] = False

    def on_confirm(e=None):
        x0 = min(state["x0"], state["x1"])
        y0 = min(state["y0"], state["y1"])
        x1 = max(state["x0"], state["x1"])
        y1 = max(state["y0"], state["y1"])
        if (x1 - x0) < 4 or (y1 - y0) < 4:
            return
        try:
            result["image"] = screenshot.crop((x0, y0, x1, y1))
        except Exception:
            result["image"] = None
        top.destroy()

    def on_cancel(e=None):
        result["image"] = None
        top.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Double-Button-1>", on_confirm)
    top.bind("<Return>", on_confirm)
    top.bind("<KP_Enter>", on_confirm)
    top.bind("<Escape>", on_cancel)
    top.protocol("WM_DELETE_WINDOW", on_cancel)

    # 8) Mostra e dai focus
    top.update_idletasks()
    try:
        top.lift()
    except Exception:
        pass
    _metti_in_primo_piano_win32(top)
    try:
        top.focus_force()
    except Exception:
        pass
    top.after(50, lambda: _metti_in_primo_piano_win32(top))
    top.after(50, top.focus_force)

    # 9) Attende la chiusura
    top.wait_window()
    return result["image"]