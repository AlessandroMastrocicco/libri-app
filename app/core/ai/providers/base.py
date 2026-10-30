# -*- coding: utf-8 -*-
"""
providers/base.py - Contratto dei provider e registro (responsabilita' minime).

Ogni adapter concreto (openai_compat, gemini, ollama) implementa `chiama`.
La pipeline conosce SOLO questa interfaccia: puo' quindi essere testata con
stub iniettabili e sostituire un provider senza toccare l'orchestratore.

Firma uniforme (stessa della bozza pipeline):
    chiama(modello, messaggi, max_tokens) -> (testo, token_usati, esito)
dove esito e' una costante di router.py (OK / QUOTA_ESAURITA / ERRORE_RETE /
ERRORE_GENERICO), cosi' il router puo' reagire senza eccezioni sparse.
"""

from __future__ import annotations

from typing import Callable

from app.core.ai.catalogo import Modello
from app.core.ai.router import (ERRORE_GENERICO, ERRORE_RETE, OK,
                                QUOTA_ESAURITA)

# firma condivisa: (modello, messaggi, max_tokens) -> (testo, tok, esito)
ProviderFn = Callable[[Modello, list[dict], int], tuple[str, int, str]]


class ErroreProvider(RuntimeError):
    """Errore del provider gia' tradotto in esito per il router."""

    def __init__(self, esito: str, messaggio: str = ""):
        super().__init__(messaggio or esito)
        self.esito = esito


def esito_da_http(status: int, corpo: str = "") -> str:
    """Traduzione centralizzata stato HTTP -> esito del router.

    Unica sede dove i codici d'errore dei vari provider vengono interpretati:
    gli adapter restano file piccoli e omogenei.
    """
    if status == 200:
        return OK
    c = (corpo or "").lower()
    if status == 429:
        # 429 = rate limit/quota: per noi sempre "bruciato" (rollover UTC)
        return QUOTA_ESAURITA
    if status == 402:
        return QUOTA_ESAURITA
    if status in (401, 403):
        # chiave mancante/invalida: errore generico (cooldown breve, cosi'
        # un provider senza chiave non viene martellato)
        return ERRORE_GENERICO
    if "quota" in c or "rate limit" in c or "too many" in c:
        return QUOTA_ESAURITA
    if status >= 500:
        return ERRORE_RETE
    return ERRORE_GENERICO


# ======================================================================
# Registro: nome provider -> factory(api_key, base_url|None) -> ProviderFn
# ======================================================================

_REGISTRO: dict[str, Callable[..., ProviderFn]] = {}


def registra(nome: str):
    """Decoratore per registrare una factory di provider."""
    def deco(factory):
        _REGISTRO[nome] = factory
        return factory
    return deco


def factory_provider(nome: str):
    return _REGISTRO.get(nome)


def nomi_registrati() -> list[str]:
    return sorted(_REGISTRO)
