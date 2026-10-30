# -*- coding: utf-8 -*-
"""
providers/ollama.py - Adapter per Ollama locale (fallback offline, zero quota).

Endpoint standard http://localhost:11434/api/chat. Le immagini viaggiano nel
campo `images` come base64 puro (schema Ollama, non OpenAI).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from app.core.ai.catalogo import Modello
from app.core.ai.providers._http import post_json
from app.core.ai.providers.base import ProviderFn, esito_da_http, registra
from app.core.ai.router import ERRORE_RETE, OK

URL_LOCALE = "http://localhost:11434/api/chat"


def _a_ollama(messaggi: list[dict]) -> list[dict]:
    out = []
    from app.core.ai.visione import immagine_in_bytes
    for m in messaggi:
        contenuto = m.get("content")
        testo = ""
        imgs: list[str] = []
        if isinstance(contenuto, str):
            testo = contenuto
        elif isinstance(contenuto, list):
            for p in contenuto:
                if p.get("type") == "text":
                    testo += p.get("text", "") + "\n"
                elif p.get("type") in ("image_ref", "image_url"):
                    raw = immagine_in_bytes(p.get("path") or "")
                    if raw:
                        imgs.append(base64.b64encode(raw).decode())
        msg = {"role": m["role"], "content": testo.strip()}
        if imgs:
            msg["images"] = imgs
        out.append(msg)
    return out


def crea(api_key: str = "", base_url: str | None = None) -> ProviderFn:
    def chiama(modello: Modello, messaggi: list[dict],
               max_tokens: int) -> tuple[str, int, str]:
        url = base_url or URL_LOCALE
        payload = {
            "model": modello.nome,
            "messages": _a_ollama(messaggi),
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.2},
        }
        try:
            status, _, corpo = post_json(url, payload, {})
        except Exception:
            return "", 0, ERRORE_RETE
        esito = esito_da_http(status, corpo)
        if esito != OK:
            return "", 0, esito
        try:
            dati = json.loads(corpo)
            testo = (dati.get("message") or {}).get("content", "")
            tok = int(dati.get("eval_count", 0)) + \
                int(dati.get("prompt_eval_count", 0))
            if dati.get("done_reason") == "length":
                testo += "\n[[TRONCATO]]"
            return testo, tok, OK
        except (ValueError, json.JSONDecodeError):
            return "", 0, "errore_generico"
    return chiama


registra("ollama")(crea)
