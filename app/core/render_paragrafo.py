# -*- coding: utf-8 -*-
"""
render_paragrafo.py - Rendering del singolo paragrafo in PDF di anteprima.
"""

from __future__ import annotations

import hashlib
import importlib
import sys
import threading
import time
import traceback
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate

from app.core.build_report import BuildReport
from app.core.paragrafo import percorso_paragrafo
from app.core.libro import percorso_libro


_lock = threading.Lock()


def cartella_cache(root: Path, slug: str) -> Path:
    c = percorso_libro(root, slug) / "_cache_render"
    c.mkdir(parents=True, exist_ok=True)
    return c

def percorso_cache_pdf(root: Path, slug: str, cap: int, par_id: str) -> Path:
    return cartella_cache(root, slug) / f"paragrafo_{cap:02d}_{par_id}.pdf"

def percorso_cache_hash(root: Path, slug: str, cap: int, par_id: str) -> Path:
    return cartella_cache(root, slug) / f"paragrafo_{cap:02d}_{par_id}.sha"


def _hash_sorgente(root: Path, slug: str, cap: int, par_id: str) -> str | None:
    p = percorso_paragrafo(root, slug, cap, par_id)
    if not p.is_file(): return None
    try: contenuto = p.read_bytes()
    except Exception: return None
    return hashlib.sha1(contenuto).hexdigest()

def cache_valida(root: Path, slug: str, cap: int, par_id: str) -> bool:
    pdf = percorso_cache_pdf(root, slug, cap, par_id)
    sha = percorso_cache_hash(root, slug, cap, par_id)
    if not pdf.is_file() or not sha.is_file(): return False
    try: h_salvato = sha.read_text(encoding="utf-8").strip()
    except Exception: return False
    h_corrente = _hash_sorgente(root, slug, cap, par_id)
    return h_corrente is not None and h_corrente == h_salvato


def _assicura_root_nel_path(root: Path):
    r = str(root)
    if r not in sys.path: sys.path.insert(0, r)

def _carica_modulo_paragrafo(root: Path, slug: str, cap: int, par_id: str):
    _assicura_root_nel_path(root)
    package = f"libri.{slug}.capitoli.capitolo_{cap:02d}.paragrafi"
    nome = f"paragrafo_{par_id}"
    for k in list(sys.modules.keys()):
        if k.endswith(f"{package}.{nome}") or k == f"{package}.{nome}":
            del sys.modules[k]
    return importlib.import_module(f"{package}.{nome}")


def renderizza_paragrafo(root: Path, slug: str, cap: int, par_id: str, forza: bool = False, report: BuildReport | None = None) -> dict:
    t0 = time.time()
    risultato = {"ok": False, "pdf": None, "da_cache": False, "durata_sec": 0.0, "errore": None}

    if not forza and cache_valida(root, slug, cap, par_id):
        risultato["ok"] = True
        risultato["pdf"] = percorso_cache_pdf(root, slug, cap, par_id)
        risultato["da_cache"] = True
        risultato["durata_sec"] = time.time() - t0
        return risultato

    pdf_out = percorso_cache_pdf(root, slug, cap, par_id)

    with _lock:
        try:
            _assicura_root_nel_path(root)
            from motore.fonts import registra_font
            registra_font()

            from motore import immagini as _im
            from motore import formule as _fo
            from motore import grafici as _gr
            from motore import diagrammi as _di
            _im.set_libro_corrente(slug)
            _fo.set_libro_corrente(slug)
            _gr.set_libro_corrente(slug)
            _di.set_libro_corrente(slug)

            mod = _carica_modulo_paragrafo(root, slug, cap, par_id)
            if not hasattr(mod, "story"):
                raise AttributeError(f"paragrafo_{par_id} non espone story()")
            flowables = mod.story()
            if not isinstance(flowables, list):
                raise TypeError(f"story() ha restituito {type(flowables).__name__}, attesa lista")

            doc = SimpleDocTemplate(
                str(pdf_out), pagesize=A4,
                leftMargin=2 * cm, rightMargin=2 * cm,
                topMargin=2 * cm, bottomMargin=2 * cm,
                title=f"{slug} {cap}.{par_id}",
            )
            doc.build(flowables)

            h = _hash_sorgente(root, slug, cap, par_id)
            if h:
                percorso_cache_hash(root, slug, cap, par_id).write_text(h, encoding="utf-8")

            risultato["ok"] = True
            risultato["pdf"] = pdf_out
            risultato["da_cache"] = False

        except Exception as e:
            tb = traceback.format_exc()
            risultato["errore"] = f"{type(e).__name__}: {e}"
            if report is not None:
                report.errore(origine="paragrafo", contesto=f"{cap}.{par_id}", messaggio=str(e), dettaglio=tb)

    risultato["durata_sec"] = time.time() - t0
    return risultato


def invalida_cache_paragrafo(root: Path, slug: str, cap: int, par_id: str) -> None:
    for p in (percorso_cache_pdf(root, slug, cap, par_id), percorso_cache_hash(root, slug, cap, par_id)):
        try:
            if p.is_file(): p.unlink()
        except Exception: pass

def invalida_cache_capitolo(root: Path, slug: str, cap: int) -> None:
    from app.core.paragrafo import elenca_paragrafi
    for par_id in elenca_paragrafi(root, slug, cap):
        invalida_cache_paragrafo(root, slug, cap, par_id)

def invalida_cache_libro(root: Path, slug: str) -> None:
    import shutil
    c = percorso_libro(root, slug) / "_cache_render"
    if c.is_dir():
        try: shutil.rmtree(c)
        except Exception: pass