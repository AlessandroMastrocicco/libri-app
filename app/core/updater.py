# -*- coding: utf-8 -*-
"""Controllo degli aggiornamenti pubblicati su GitHub."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.version import __version__

URL_GITHUB_RAW = "https://raw.githubusercontent.com/AlessandroMastrocicco/libri-app/main/latest_version.json"


def _parse_version(v: str) -> tuple[int, ...] | None:
    """Trasforma una versione numerica come '1.2.3' in una tupla."""
    parti = v.strip().split(".")
    if not parti or any(not parte.isdecimal() for parte in parti):
        return None
    return tuple(map(int, parti))


def controlla_aggiornamenti(root_progetto: Path) -> dict | None:
    """Restituisce i metadati remoti se GitHub pubblica una versione più recente."""
    richiesta = Request(
        URL_GITHUB_RAW,
        headers={"User-Agent": "LIBRI-App", "Cache-Control": "no-cache"},
    )
    try:
        with urlopen(richiesta, timeout=5) as risposta:
            nuova_versione = json.loads(risposta.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as e:
        print(f"[updater] Impossibile controllare gli aggiornamenti GitHub: {e}")
        nuova_versione = None

    if not isinstance(nuova_versione, dict):
        percorso_locale = Path(root_progetto) / "latest_version.json"
        try:
            nuova_versione = json.loads(percorso_locale.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as e:
            print(f"[updater] Impossibile leggere i metadati locali: {e}")
            return None

    versione_remota = nuova_versione.get("version")
    if not isinstance(versione_remota, str):
        print("[updater] I metadati di aggiornamento non contengono una versione valida.")
        return None

    versione_corrente = _parse_version(__version__)
    versione_nuova = _parse_version(versione_remota)
    if versione_corrente is None or versione_nuova is None:
        print("[updater] Formato della versione non valido nei metadati di aggiornamento.")
        return None

    if versione_nuova > versione_corrente:
        return {
            "version": versione_remota,
            "url": nuova_versione.get(
                "url", "https://github.com/AlessandroMastrocicco/libri-app/releases"
            ),
            "changelog": nuova_versione.get(
                "changelog", "Consulta la pagina delle release per le novità."
            ),
        }

    return None