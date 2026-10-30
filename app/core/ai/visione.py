# -*- coding: utf-8 -*-
"""
visione.py - Preparazione delle immagini per i modelli vision (responsabilita' unica).

Token-ottimizzazione applicata qui:
  * ridimensionamento a cap (default 1568 px lato massimo): quasi tutti i
    provider tokenizzano le immagini su griglie fisse, quindi inviare un PNG
    4K costa banda e latenza senza aumentare i token utili;
  * conversione JPEG qualita' 82 quando possibile (Pillow presente) per
    dimezzare il payload base64;
  * cache dei dati gia' convertiti in memoria (la stessa slide viene riusata
    da piu' task della pipeline: la paghi una volta).

Nessuna dipendenza obbligatoria da Pillow: se manca, passa il file originale.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

LATO_MAX = 1568
_QUALITA_JPEG = 82
_cache: dict[tuple[str, int], Optional[str]] = {}


def _comprimi(raw: bytes, lato_max: int) -> bytes:
    """Ridimensiona/ricodifica con Pillow se disponibile; altrimenti noop."""
    try:
        from io import BytesIO
        from PIL import Image
    except ImportError:
        return raw
    try:
        img = Image.open(BytesIO(raw))
        img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > lato_max:
            scala = lato_max / max(w, h)
            img = img.resize((max(1, int(w * scala)),
                              max(1, int(h * scala))))
        out = BytesIO()
        img.save(out, "JPEG", quality=_QUALITA_JPEG, optimize=True)
        nuovo = out.getvalue()
        # usa la versione compressa solo se davvero piu' piccola
        return nuovo if len(nuovo) < len(raw) else raw
    except Exception:
        return raw


def immagine_in_bytes(path: str | Path, lato_max: int = LATO_MAX
                      ) -> bytes | None:
    """Legge e comprime l'immagine; None se il file non esiste."""
    p = Path(str(path))
    if not p.is_file():
        return None
    chiave = (str(p), lato_max)
    if chiave in _cache:
        cached = _cache[chiave]
        if cached is None:
            return None
        return base64.b64decode(cached.split(",", 1)[1]) \
            if "," in cached else None
    try:
        raw = _comprimi(p.read_bytes(), lato_max)
    except OSError:
        return None
    b64 = base64.b64encode(raw).decode()
    mime = "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "image/png"
    _cache[chiave] = f"data:{mime};base64,{b64}"
    return raw


def immagine_in_data_url(path: str | Path,
                         lato_max: int = LATO_MAX) -> str | None:
    """Data-URL pronto per gli schemi OpenAI-compatible (con cache)."""
    p = Path(str(path))
    if not p.is_file():
        return None
    chiave = (str(p), lato_max)
    if chiave in _cache:
        return _cache[chiave]
    raw = immagine_in_bytes(p, lato_max)
    if raw is None:
        _cache[chiave] = None
        return None
    mime = "image/jpeg" if raw[:3] == b"\xff\xd8\xff" else "image/png"
    url = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
    _cache[chiave] = url
    return url


def svuota_cache() -> None:
    _cache.clear()
