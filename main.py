# -*- coding: utf-8 -*-
"""
main.py - Entry point dell'applicazione LIBRI.

Uso:
    python main.py                    # da sorgente (unica modalita' prevista:
                                      # gli utenti scaricano lo ZIP del codice)

Comportamento dei percorsi:

- Da sorgente (sviluppo):
    ROOT_APP    = cartella del progetto (dove sta main.py)
    ROOT_DATI   = ROOT_APP         -> i libri vivono in ./libri/

- Da eseguibile congelato (PyInstaller):
    ROOT_APP    = sys._MEIPASS     -> risorse interne (app/, motore/)
    ROOT_DATI   = %LOCALAPPDATA%/LIBRI_App   (o equivalente)
                                     -> i libri dell'utente vivono qui
    Al primo avvio, se ROOT_DATI/libri non esiste, viene creata
    e (se presente nel bundle) viene copiato un contenuto iniziale
    da RES_BUNDLE/libri_esempio/.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# ======================================================================
# 0) DPI awareness (Windows) - PRIMA di importare tkinter
# ======================================================================

if sys.platform.startswith("win"):
    try:
        import ctypes
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ======================================================================
# 1) Rilevamento modalita' (sorgente vs congelato)
# ======================================================================

def _is_frozen() -> bool:
    """True se stiamo girando dentro un bundle PyInstaller."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _cartella_risorse() -> Path:
    """
    Cartella in cui risiedono le risorse del programma (codice Python:
    app/, motore/, piu' eventuali dati di esempio).

    - Da sorgente: la cartella di main.py
    - Da congelato: sys._MEIPASS (dove PyInstaller estrae il bundle)
    """
    if _is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _cartella_dati_utente() -> Path:
    """
    Cartella in cui l'app puo' scrivere dati persistenti (libri/).

    - Da sorgente: la cartella di main.py (comportamento attuale)
    - Da congelato:
        Windows: %LOCALAPPDATA%\\LIBRI_App
        macOS:   ~/Library/Application Support/LIBRI_App
        Linux:   ~/.local/share/LIBRI_App
    """
    if not _is_frozen():
        return Path(__file__).resolve().parent

    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "LIBRI_App"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LIBRI_App"

    # Linux / altri
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "LIBRI_App"
    return Path.home() / ".local" / "share" / "LIBRI_App"


# ======================================================================
# 2) Preparazione delle cartelle
# ======================================================================

RES_BUNDLE = _cartella_risorse()   # dove stanno codice + risorse
ROOT_DATI = _cartella_dati_utente()  # dove l'app scrive (libri/, cache, ecc.)


def _copia_albero(src: Path, dest: Path) -> None:
    """Copia ricorsivamente src dentro dest (creando dest se manca)."""
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dest / item.name
        if item.is_dir():
            _copia_albero(item, target)
        else:
            try:
                shutil.copy2(item, target)
            except Exception:
                pass


def _prepara_cartella_dati() -> None:
    """
    Assicura che ROOT_DATI/libri esista.
    Al primo avvio da bundle, se e' presente RES_BUNDLE/libri_esempio/,
    ne copia il contenuto in ROOT_DATI/libri/.
    """
    try:
        ROOT_DATI.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[main] Impossibile creare {ROOT_DATI}: {e}")
        return

    libri_dir = ROOT_DATI / "libri"

    if libri_dir.is_dir():
        # Gia' presente: nulla da fare
        return

    # Primo avvio (o cartella cancellata): creiamo la cartella libri
    try:
        libri_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"[main] Impossibile creare {libri_dir}: {e}")
        return

    # Se il bundle contiene libri_esempio/, copiamolo
    esempio = RES_BUNDLE / "libri_esempio"
    if esempio.is_dir() and any(esempio.iterdir()):
        try:
            _copia_albero(esempio, libri_dir)
            print(f"[main] Contenuto iniziale copiato in {libri_dir}")
        except Exception as e:
            print(f"[main] Errore copiando libri_esempio: {e}")


# ======================================================================
# 3) sys.path
# ======================================================================

# Da sorgente: aggiungi la cartella del progetto
# Da bundle: i moduli sono gia' estratti in sys._MEIPASS che PyInstaller
#            mette automaticamente in sys.path
if str(RES_BUNDLE) not in sys.path:
    sys.path.insert(0, str(RES_BUNDLE))


# ======================================================================
# 4) Import dell'app (dopo la patch DPI e il setup percorsi)
# ======================================================================

from app.ui.app import App  # noqa: E402


# ======================================================================
# 5) Entry point
# ======================================================================

def main() -> None:
    _prepara_cartella_dati()

    # Log di avvio (utile in caso di debug da console)
    print(f"[main] modalita': {'bundle' if _is_frozen() else 'sorgente'}")
    print(f"[main] risorse  : {RES_BUNDLE}")
    print(f"[main] dati     : {ROOT_DATI}")

    app = App(ROOT_DATI)
    app.mainloop()


if __name__ == "__main__":
    main()