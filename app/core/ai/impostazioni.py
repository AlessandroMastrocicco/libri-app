# -*- coding: utf-8 -*-
"""
impostazioni.py - Configurazione AI utente: chiavi API, consenso privacy,
preferenze di routing. Unica sede che legge `.env` e `libri/_ai_config.json`.

Regole di sicurezza ereditate dalla bozza:
  * le chiavi stanno in variabili d'ambiente o nel file `.env` (fuori repo);
    `_ai_config.json` conserva SOLO preferenze non sensibili;
  * nessun provider cloud viene usato finche' l'utente non da' consenso
    esplicito (`privacy.consenso_cloud = true`); Ollama locale e' sempre
    utilizzabile perche' i dati non escono dalla macchina.
"""

from __future__ import annotations

import json
from pathlib import Path

# Variabili d'ambiente riconosciute per provider
AMB = {
    "groq": "GROQ_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "cerebras": "CEREBRAS_API_KEY",
    "sambanova": "SAMBANOVA_API_KEY",
    "github": "GITHUB_TOKEN",
    "deepseek": "DEEPSEEK_API_KEY",
}

_PATH_ENV = ".env"


class LeggiChiavi:
    """Lettura unitaria: config JSON (non segreta) + env/.env (segreta)."""

    def __init__(self, root_progetto: Path | None = None):
        self._root = Path(root_progetto or "libri")
        self._config = self._leggi_config()
        self._env = self._leggi_env()

    # ---------- sorgenti ----------

    def _leggi_config(self) -> dict:
        p = self._root / "_ai_config.json"
        if p.is_file():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict):
                    return d
            except Exception:
                pass
        return {}

    def _leggi_env(self) -> dict:
        import os
        valori = {k: v for k, v in os.environ.items()}
        try:
            from dotenv import load_dotenv
            # popola anche os.environ; rileggiamo per sicurezza
            load_dotenv(_PATH_ENV)
            valori.update({k: v for k, v in os.environ.items() if v})
        except Exception:
            pass
        return valori

    # ---------- interrogazioni ----------

    def per(self, provider: str) -> str:
        """Chiave del provider: config > env > .env (stringa vuota se assente)."""
        cfg = (self._config.get("chiavi") or {}).get(provider)
        if cfg:
            return str(cfg)
        var = AMB.get(provider)
        if var:
            return str(self._env.get(var) or "")
        return ""

    def base_url(self, provider: str) -> str | None:
        urls = self._config.get("base_url") or {}
        v = urls.get(provider)
        return str(v) if v else None

    def consenso_cloud(self) -> bool:
        return bool((self._config.get("privacy") or {})
                    .get("consenso_cloud", False))

    def provider_con_chiave(self) -> list[str]:
        return sorted([p for p in AMB if self.per(p)])

    def provider_attivabili(self) -> list[str]:
        """Provider usabili adesso: chiave presente E (cloud => consenso)."""
        out = []
        if self.per("ollama") or True:  # ollama non richiede chiave
            out.append("ollama")
        for p in self.provider_con_chiave():
            if self.consenso_cloud():
                out.append(p)
        return sorted(set(out))

    # ---------- scritture (non segrete) ----------

    def salva_preferenze(self, *, consenso_cloud: bool | None = None,
                         modello_fissato: str | None = None) -> None:
        """Aggiorna solo i campi non sensibili; le chiavi non vengono mai
        scritte qui (restano in .env per non finire nei backup del libro)."""
        p = self._root / "_ai_config.json"
        cfg = dict(self._config)
        priv = dict(cfg.get("privacy") or {})
        if consenso_cloud is not None:
            priv["consenso_cloud"] = bool(consenso_cloud)
        cfg["privacy"] = priv
        if modello_fissato is not None:
            routing = dict(cfg.get("routing") or {})
            routing["modello_fissato"] = modello_fissato or None
            cfg["routing"] = routing
        self._config = cfg
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        tmp.replace(p)

    def modello_fissato(self) -> str | None:
        v = (self._config.get("routing") or {}).get("modello_fissato")
        return str(v) if v else None
