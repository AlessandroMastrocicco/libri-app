# -*- coding: utf-8 -*-
"""
io_sicuro.py - Scrittura file atomica.

Scrive su un file temporaneo nella stessa cartella e poi lo sostituisce
con os.replace(): se l'app si chiude a meta' scrittura, il file originale
resta intatto (importante: molti file del progetto sono moduli Python
che vengono importati).
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path


def scrivi_testo(path, contenuto: str, encoding: str = "utf-8") -> Path:
    """Scrive `contenuto` in `path` in modo atomico. Ritorna il Path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name + ".", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        # newline=None: stesso comportamento di Path.write_text
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(contenuto)
            f.flush()
            os.fsync(f.fileno())

        # Su Windows os.replace puo' fallire per un attimo se un antivirus
        # o un altro processo sta leggendo il file di destinazione.
        ultimo_errore = None
        for _ in range(5):
            try:
                os.replace(tmp, path)
                return path
            except PermissionError as e:
                ultimo_errore = e
                time.sleep(0.1)
        raise ultimo_errore  # type: ignore[misc]
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
