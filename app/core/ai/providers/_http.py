# -*- coding: utf-8 -*-
"""
providers/_http.py - Trasporto HTTP minimale e sicuro (responsabilita' unica).

Un solo punto per: timeout, header di autenticazione, lettura corpo.
Nessuna dipendenza obbligatoria: usa `requests` se presente, altrimenti
urllib standard. I log non contengono mai la chiave API.
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TIMEOUT_S = 120  # i draft lunghi su free tier possono essere lenti


def post_json(url: str, payload: dict, chiavi_header: dict[str, str]
              ) -> tuple[int, dict, str]:
    """POST JSON -> (status, headers_dict, corpo_testo).

    Non solleva per status != 200: riporta il codice, cosi' il livello
    superiore traduce in esito router (pattern uniforme).
    Solleva URLError/Timeout solo per guasti di trasporto.
    """
    dati = json.dumps(payload).encode("utf-8")
    req = Request(url, data=dati, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (chiavi_header or {}).items():
        if v:
            req.add_header(k, v)
    try:
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            corpo = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers), corpo
    except HTTPError as e:
        corpo = ""
        try:
            corpo = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, dict(e.headers or {}), corpo


def estrai_int_headers(headers: dict, *nomi: str) -> int | None:
    """Lettura robusta (case-insensitive) di un header numerico, es.
    x-ratelimit-remaining-requests per sincronizzare il router alla realta'."""
    bassa = {k.lower(): v for k, v in (headers or {}).items()}
    for n in nomi:
        v = bassa.get(n.lower())
        if v is not None:
            try:
                return int(float(v))
            except (TypeError, ValueError):
                continue
    return None
