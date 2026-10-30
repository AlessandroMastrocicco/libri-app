# -*- coding: utf-8 -*-
"""
providers/openai_compat.py - Adapter per i provider OpenAI-compatible.

Copre: Groq, Mistral, OpenRouter, Cerebras, SambaNova, GitHub Models,
DeepSeek (e ogni futuro endpoint compatibile via base_url custom).
Responsabilita': tradurre messaggi/payload nello schema /chat/completions e
leggere usage + header di rate-limit. Niente logica di quota (router) ne' di
prompt (prompt.py): single responsibility.
"""

from __future__ import annotations

import json

from app.core.ai.catalogo import Modello
from app.core.ai.providers._http import estrai_int_headers, post_json
from app.core.ai.providers.base import ProviderFn, esito_da_http, registra
from app.core.ai.router import ERRORE_RETE, OK

# Base URL noti (free tier). Estendibili in configurazione senza toccare il
# codice: qualsiasi endpoint /chat/completions funziona.
BASE_URL = {
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "cerebras": "https://api.cerebras.ai/v1",
    "sambanova": "https://api.sambanova.ai/v1",
    "github": "https://models.inference.ai.azure-api.vn",
    "deepseek": "https://api.deepseek.com/v1",
}


def _converti_messaggi(messaggi: list[dict]) -> list[dict]:
    """Mappa i blocchi interni ({'type':'image_ref', 'path':...}) nel formato
    image_url con data-URL base64 richiesto dagli endpoint compatibili."""
    from app.core.ai.visione import immagine_in_data_url
    out = []
    for m in messaggi:
        contenuto = m.get("content")
        if isinstance(contenuto, list):
            parti = []
            for p in contenuto:
                if p.get("type") == "text":
                    parti.append({"type": "text", "text": p.get("text", "")})
                elif p.get("type") == "image_ref":
                    data_url = immagine_in_data_url(p.get("path", ""))
                    if data_url:
                        parti.append({"type": "image_url",
                                      "image_url": {"url": data_url}})
            out.append({"role": m["role"], "content": parti})
        else:
            out.append({"role": m["role"], "content": contenuto or ""})
    return out


def crea(modello_base: str | None = None, api_key: str = "",
         base_url: str | None = None) -> ProviderFn:
    """Factory: restituisce la funzione `chiama` per un provider compatibile.

    `modello_base` e' solo per il default del nome; il nome reale arriva dal
    Modello del catalogo a ogni chiamata.
    """
    def chiama(modello: Modello, messaggi: list[dict],
               max_tokens: int) -> tuple[str, int, str]:
        url_base = base_url or BASE_URL.get(modello.provider)
        if not url_base:
            return "", 0, ERRORE_RETE
        payload = {
            "model": modello.nome,
            "messages": _converti_messaggi(messaggi),
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if modello.provider == "openrouter":
            # richiesta obbligatoria OpenRouter per attribuzione gratuita
            headers["HTTP-Referer"] = "https://github.com/AlessandroMastrocicco/libri-app"
            headers["X-Title"] = "LIBRI"
        try:
            status, resp_headers, corpo = post_json(
                url_base.rstrip("/") + "/chat/completions", payload, headers)
        except Exception:
            return "", 0, ERRORE_RETE
        esito = esito_da_http(status, corpo)
        if esito != OK:
            return "", 0, esito
        try:
            dati = json.loads(corpo)
            testo = dati["choices"][0]["message"]["content"] or ""
            uso = dati.get("usage") or {}
            tok = int(uso.get("total_tokens") or 0)
            residuo = estrai_int_headers(
                resp_headers, "x-ratelimit-remaining-requests",
                "x-ratelimit-remaining")
            # (residuo viene usato dal chiamante tramite RateLimitInfo)
            if tok == 0:
                tok = len(testo) // 4
            troncato = (dati["choices"][0].get("finish_reason")
                        == "length")
            return (testo + ("\n[[TRONCATO]]" if troncato else "")), tok, esito
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            return "", 0, "errore_generico"

    return chiama


for _nome in ("groq", "mistral", "openrouter", "cerebras", "sambanova",
              "github", "deepseek"):
    registra(_nome)(crea)
