# -*- coding: utf-8 -*-
"""
providers/__init__.py - Facciata del pacchetto provider.

`costruisci_fornitore(root_progetto)` monta il provider composito: sceglie
l'adapter giusto per ogni modello del catalogo in base alle chiavi presenti
in configurazione (`libri/_ai_config.json`) o nelle variabili d'ambiente.
La pipeline riceve UN SOLO oggetto `chiama(modello, messaggi, max_tokens)`.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.core.ai.catalogo import Modello
from app.core.ai.providers import gemini, ollama, openai_compat  # noqa: F401
from app.core.ai.providers.base import factory_provider, nomi_registrati
from app.core.ai.impostazioni import LeggiChiavi
from app.core.ai.router import ERRORE_GENERICO, OK

__all__ = ["costruisci_fornitore", "nomi_registrati", "ProviderComposito"]


class ProviderComposito:
    """Instrada ogni chiamata all'adapter del provider del modello.

    Se la chiave manca, ritorna esito errore SENZA toccare la rete: il router
    mettera' il modello in cooldown e passera' oltre (switch automatico).
    """

    def __init__(self, root_progetto: Path | None = None):
        self._letti = LeggiChiavi(root_progetto or Path("libri"))
        self._cache: dict[str, object] = {}

    def _per(self, provider: str):
        if provider not in self._cache:
            factory = factory_provider(provider)
            if factory is None:
                self._cache[provider] = None
                return None
            chiave = self._letti.per(provider)
            base_url = self._letti.base_url(provider)
            self._cache[provider] = factory(api_key=chiave, base_url=base_url)
        return self._cache[provider]

    def ha_chiavi(self) -> list[str]:
        return self._letti.provider_con_chiave()

    def chiama(self, modello: Modello, messaggi: list[dict],
               max_tokens: int) -> tuple[str, int, str]:
        fn = self._per(modello.provider)
        if fn is None:
            return "", 0, ERRORE_GENERICO   # provider non supportato
        if modello.provider != "ollama" and not self._letti.per(modello.provider):
            return "", 0, ERRORE_GENERICO   # nessuna chiave: niente rete
        return fn(modello, messaggi, max_tokens)


def costruisci_fornitore(root_progetto: Path | None = None
                         ) -> ProviderComposito:
    return ProviderComposito(root_progetto)
