# -*- coding: utf-8 -*-
"""
motore_adapter.py - Ponte tra la UI e il motore ReportLab.

Responsabilita':
- bootstrap del motore (registrazione font) una sola volta;
- serializzazione delle build con un lock (il motore ha stato globale);
- ritorno di un BuildReport per la UI.
"""

from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path

from app.core.build_report import BuildReport


_lock = threading.Lock()
_bootstrap_fatto = False


def _bootstrap():
    global _bootstrap_fatto
    if _bootstrap_fatto:
        return
    from motore.fonts import registra_font
    registra_font()
    _bootstrap_fatto = True


def costruisci_libro_safe(nome_libro: str,
                          percorso_output: Path | None = None) -> BuildReport:
    """
    Costruisce il PDF del libro. Serializza le build con un lock
    perche' il motore usa stato globale (`set_libro_corrente`).
    """
    report = BuildReport(libro=nome_libro)
    t0 = time.time()

    with _lock:
        _bootstrap()
        try:
            from motore.builder import costruisci_libro
            pdf = costruisci_libro(
                nome_libro, percorso_output, report=report
            )
            report.pdf_path = Path(pdf)
            report.ok = report.n_errori == 0
        except Exception as e:
            report.errore(
                origine="sistema",
                contesto="build",
                messaggio=str(e),
                dettaglio=traceback.format_exc(),
            )
            report.ok = False

    report.durata_sec = time.time() - t0
    return report