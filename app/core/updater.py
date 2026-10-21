# -*- coding: utf-8 -*-
"""
updater.py - Controllo degli aggiornamenti dell'applicazione.

Attualmente legge un file locale (latest_version.json) nella root del progetto.
In futuro, basterà decommentare la parte di GitHub per renderlo globale.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen, Request

from app.version import __version__

# URL futuro per GitHub (sostituisci con il tuo utente e repo)
URL_GITHUB_RAW = "https://raw.githubusercontent.com/tuo-utente/tuo-repo/main/latest_version.json"


def _parse_version(v: str) -> tuple[int, ...]:
    """Trasforma '1.2.3' in (1, 2, 3) per un confronto corretto."""
    try:
        return tuple(map(int, v.strip().split(".")))
    except Exception:
        return (0, 0, 0)


def controlla_aggiornamenti(root_progetto: Path) -> dict | None:
    """
    Controlla se esiste una nuova versione.
    
    Ritorna un dizionario con i dati della nuova versione se disponibile,
    altrimenti None.
    """
    nuova_versione = None

    # ---------------------------------------------------------
    # 1. LOGICA LOCALE (Attiva per i test)
    # ---------------------------------------------------------
    json_path = Path(root_progetto) / "latest_version.json"
    if json_path.is_file():
        try:
            nuova_versione = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[updater] Errore lettura locale: {e}")

    # ---------------------------------------------------------
    # 2. LOGICA GITHUB (Da attivare in futuro)
    # ---------------------------------------------------------
    # if nuova_versione is None:
    #     try:
    #         req = Request(URL_GITHUB_RAW, headers={"User-Agent": "LIBRI-App"})
    #         with urlopen(req, timeout=3) as response:
    #             nuova_versione = json.loads(response.read().decode("utf-8"))
    #     except Exception as e:
    #         print(f"[updater] Nessun aggiornamento o errore di rete: {e}")

    # ---------------------------------------------------------
    # 3. CONFRONTO VERSIONI
    # ---------------------------------------------------------
    if not nuova_versione or not isinstance(nuova_versione, dict):
        return None

    v_remota = nuova_versione.get("version", "0.0.0")
    if _parse_version(v_remota) > _parse_version(__version__):
        return {
            "version": v_remota,
            "url": nuova_versione.get("url", ""),
            "changelog": nuova_versione.get("changelog", "Nessuna nota di rilascio."),
        }

    return None