# -*- coding: utf-8 -*-
"""
providers/gemini.py - Adapter per Google Gemini API (free tier).

Responsabilita': tradurre i messaggi interni nello schema generateContent di
Gemini e leggere usageMetadata + header x-ratelimit-* (il free tier Gemini ha
finestre ANCHE orarie: l'header residuo viene passato al router via
`ultimo_residuo`, cosi' il pre-check diventa realistico).
Nessuna logica di quota/prompt qui.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from app.core.ai.catalogo import Modello
from app.core.ai.providers._http import estrai_int_headers, post_json
from app.core.ai.providers.base import ProviderFn, esito_da_http, registra
from app.core.ai.router import ERRORE_RETE, OK

URL_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _a_gemini(messaggi: list[dict]) -> tuple[list[dict], dict | None]:
    """system -> systemInstruction; resto -> contents con role user/model."""
    parts_contenuto: list[dict] = []
    contents: list[dict] = []
    system = None
    for m in messaggi:
        if m["role"] == "system":
            system = m["content"]
            continue
        parti = []
        contenuto = m.get("content")
        if isinstance(contenuto, str):
            if contenuto:
                parti.append({"text": contenuto})
        elif isinstance(contenuto, list):
            from app.core.ai.visione import immagine_in_bytes
            for p in contenuto:
                if p.get("type") == "text":
                    parti.append({"text": p.get("text", "")})
                elif p.get("type") in ("image_ref", "image_url"):
                    path = p.get("path") or ""
                    raw = immagine_in_bytes(path)
                    if raw:
                        mime = "image/png"
                        est = Path(str(path)).suffix.lower()
                        if est in (".jpg", ".jpeg"):
                            mime = "image/jpeg"
                        parti.append({"inline_data":
                                      {"mime_type": mime,
                                       "data": base64.b64encode(raw).decode()}})
        if parti:
            contents.append({"role": "user" if m["role"] == "user"
                             else "model", "parts": parti})
    return contents, ({"parts": [{"text": system}]} if system else None)


def crea(api_key: str = "", base_url: str | None = None) -> ProviderFn:
    stato = {"ultimo_residuo": None}

    def chiama(modello: Modello, messaggi: list[dict],
               max_tokens: int) -> tuple[str, int, str]:
        url_base = base_url or URL_BASE
        contents, system = _a_gemini(messaggi)
        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2,
            },
        }
        if system:
            payload["systemInstruction"] = system
        try:
            status, resp_h, corpo = post_json(
                f"{url_base}/{modello.nome}:generateContent",
                payload, {"x-goog-api-key": api_key})
        except Exception:
            return "", 0, ERRORE_RETE
        esito = esito_da_http(status, corpo)
        stato["ultimo_residuo"] = estrai_int_headers(
            resp_h, "x-ratelimit-remaining")
        if esito != OK:
            return "", 0, esito
        try:
            dati = json.loads(corpo)
            testi = [p.get("text", "")
                     for c in dati.get("candidates", [])
                     for p in c.get("content", {}).get("parts", [])]
            testo = "".join(testi)
            uso = dati.get("usageMetadata") or {}
            tok = int(uso.get("totalTokenCount") or 0) or len(testo) // 4
            fine = (dati.get("candidates") or [{}])[0].get("finishReason")
            if fine == "MAX_TOKENS":
                testo += "\n[[TRONCATO]]"
            return testo, tok, OK
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            return "", 0, "errore_generico"

    chiama.stato_provider = stato   # introspezione per il pannello UI/router
    return chiama


registra("gemini")(crea)
