# -*- coding: utf-8 -*-
"""
router.py - Scelta del modello per classe di compito e rotazione automatica
delle quote giornaliere (bozza).

Logica:
  1. ogni task dichiara una CLASSE di capacita' minima (catalogo);
  2. il router considera solo i modelli che supportano la classe;
  3. pre-check di quota PRIMA di consumare una chiamata: se i token stimati
     superano la quota residua, si passa al modello successivo;
  4. su esito "quota esaurita" (429/402) il modello viene marcato bruciato
     fino al rollover UTC; errori di rete -> cooldown temporaneo;
  5. lo stato sopravvive ai riavvii in libri/_ai_quota.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.core.ai.catalogo import MODELLI, Modello, modelli_per_classe


# ======================================================================
# Esiti che il provider adapter deve riportare al router
# ======================================================================

OK = "ok"
QUOTA_ESAURITA = "quota_esaurita"   # 429/402 con hint quota -> bruciato a giorno
ERRORE_RETE = "errore_rete"          # timeout/DNS -> cooldown breve
ERRORE_GENERICO = "errore_generico"  # 5xx / risposta malformata -> cooldown breve

_GIORNO_UTC = 0  # mezzanotte UTC = rollover

_PATH_STATO = Path("libri") / "_ai_quota.json"


def _oggi_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _oggi_per(ora_fn) -> str:
    return ora_fn().strftime("%Y-%m-%d")


@dataclass
class StatoModello:
    richieste: int = 0
    token: int = 0
    bruciato_giorno: str | None = None      # data UTC del rollover corrente
    cooldown_fino: str | None = None        # ISO timestamp

    def a_dict(self) -> dict:
        return {"richieste": self.richieste, "token": self.token,
                "bruciato_giorno": self.bruciato_giorno,
                "cooldown_fino": self.cooldown_fino}

    @staticmethod
    def da_dict(d: dict) -> "StatoModello":
        return StatoModello(
            richieste=int(d.get("richieste", 0)),
            token=int(d.get("token", 0)),
            bruciato_giorno=d.get("bruciato_giorno"),
            cooldown_fino=d.get("cooldown_fino"),
        )


class QuotaEsauritaException(RuntimeError):
    """Nessun modello della classe ha quota sufficiente: il task va in pausa."""
    def __init__(self, classe: str, prossimi_rollover: datetime):
        super().__init__(
            f"Quote gratuite esaurite per tutti i modelli della classe "
            f"'{classe}'. Riprova dopo il rollover ({prossimi_rollover:%Y-%m-%d %H:%M} UTC) "
            f"o usa la modalita' manuale."
        )
        self.classe = classe
        self.prossimi_rollover = prossimi_rollover


class Router:
    def __init__(self, path_stato: Path | None = None,
                 ora_adesso=None):
        self.path_stato = path_stato or _PATH_STATO
        self._ora = ora_adesso or (lambda: datetime.now(timezone.utc))
        self.stato: dict[str, StatoModello] = {}
        self._giorno_corrente = _oggi_utc()
        self._carica()

    # ---------------- persistenza ----------------

    def _carica(self) -> None:
        try:
            if self.path_stato.is_file():
                dati = json.loads(self.path_stato.read_text(encoding="utf-8"))
                if dati.get("giorno") == _oggi_per(self._ora):
                    self.stato = {
                        k: StatoModello.da_dict(v)
                        for k, v in (dati.get("modelli") or {}).items()
                    }
                # giorno diverso: rollover implicito (stato ripartito)
        except Exception:
            self.stato = {}

    def salva(self) -> None:
        try:
            self.path_stato.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "versione": 1,
                "giorno": _oggi_per(self._ora),
                "modelli": {k: v.a_dict() for k, v in self.stato.items()},
            }
            tmp = self.path_stato.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(self.path_stato)
        except Exception as e:  # non bloccare mai l'app per la telemetry
            print(f"[router] impossibile salvare lo stato quote: {e}")

    # ---------------- interrogazione ----------------

    def _stato(self, chiave: str) -> StatoModello:
        return self.stato.setdefault(chiave, StatoModello())

    def disponibile(self, m: Modello, token_stimati: int = 0) -> bool:
        s = self._stato(m.id)
        oggi = _oggi_per(self._ora)
        if s.bruciato_giorno == oggi:
            return False
        if s.cooldown_fino:
            try:
                if self._ora() < datetime.fromisoformat(s.cooldown_fino):
                    return False
            except ValueError:
                pass
        if m.quota_giorno_richieste and s.richieste >= m.quota_giorno_richieste:
            return False
        if m.quota_giorno_token and \
           s.token + max(token_stimati, 1) > m.quota_giorno_token:
            return False
        return True

    def frazione_usata(self, m: Modello) -> float:
        """Quota gia' consumata, come frazione 0..1 del vincolo piu' stretto."""
        s = self._stato(m.id)
        frazioni = []
        if m.quota_giorno_richieste:
            frazioni.append(s.richieste / m.quota_giorno_richieste)
        if m.quota_giorno_token:
            frazioni.append(s.token / m.quota_giorno_token)
        return max(frazioni) if frazioni else 0.0

    def scegli(self, classe: str, token_stimati: int = 0,
              richiede_vision: bool = False,
              esclusi: tuple[str, ...] = ()) -> Modello:
        """Restituisce il miglior modello disponibile per la classe.

        Ordine: priorita' statica crescente, poi minore usanza relativa.
        raises QuotaEsauritaException se nessuno e' utilizzabile.
        """
        candidati = [m for m in modelli_per_classe(classe)
                     if m.id not in esclusi
                     and (not richiede_vision or m.vision)
                     and self.disponibile(m, token_stimati)]
        if not candidati:
            raise QuotaEsauritaException(classe, self._prossimo_rollover())
        candidati.sort(key=lambda m: (m.priorita, self.frazione_usata(m)))
        return candidati[0]

    def _prossimo_rollover(self) -> datetime:
        ora = self._ora()
        domani = (ora + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        return domani.astimezone(timezone.utc)

    # ---------------- aggiornamenti post-chiamata ----------------

    def registra_esito(self, m: Modello, esito: str,
                      token_usati: int = 0) -> None:
        s = self._stato(m.id)
        if esito == OK:
            s.richieste += 1
            s.token += max(token_usati, 0)
        elif esito == QUOTA_ESAURITA:
            s.bruciato_giorno = _oggi_per(self._ora)
        elif esito in (ERRORE_RETE, ERRORE_GENERICO):
            s.cooldown_fino = (self._ora() + timedelta(minutes=15)
                               ).isoformat()
        self.salva()

    def riepilogo(self) -> list[dict]:
        """Per il pannello UI: stato odierno di tutti i modelli."""
        out = []
        for m in MODELLI:
            s = self._stato(m.id)
            out.append({
                "modello": m.id,
                "classi": list(m.classi),
                "richieste": s.richieste,
                "token": s.token,
                "quota_richieste": m.quota_giorno_richieste,
                "quota_token": m.quota_giorno_token,
                "bruciato": s.bruciato_giorno == _oggi_per(self._ora),
                "in_cooldown": bool(s.cooldown_fino) and
                              self._ora() < datetime.fromisoformat(
                                  s.cooldown_fino.replace("Z", "+00:00"))
                              if s.cooldown_fino else False,
            })
        return out
