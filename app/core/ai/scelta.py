# -*- coding: utf-8 -*-
"""
scelta.py - Scelta STRATEGICA del modello (livello sopra il router).

Il router risponde alla domanda "quale modello libero per questa classe?";
questo modulo risponde a "quale modello CONVIENE usare, dato il task?".

Criteri implementati (tutti locali, zero chiamate):
  * contest-first: scarta i modelli la cui finestra non copre prompt+output;
  * costo relativo: preferisce chi ha piu' quota residua PROPORZIONALE
    (evita di bruciare presto il provider piu' generoso);
  * affinita' di compito: piccoli bonus euristici (visione->Gemini,
    ragionamento->DeepSeek, scrittura veloce->Groq/Cerebras);
  * pacing RPMD: penalita' temporanea ai provider che rischiano il
    rate-limit al minuto (costerebbe una chiamata sprecata);
  * pin utente: se l'utente fissa un modello, lo usiamo SOLO se idoneo.

Responsabilita' minima: nessuna I/O, nessuna rete; riceve dati pronti.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.ai.catalogo import (LOCAL, MODELLO_VISIONE_PREFERITO,
                                  MODELLO_RAGIONAMENTO_PREFERITO,
                                  MODELLO_SCRITTURA_PREFERITO, Modello)
from app.core.ai.router import Router

PESO_CONTESTO = 10_000   # dominio assoluto: inadatto => escluso
PESO_QUOTA = 100         # usanza relativa 0..1 pesa fino a 100
PESO_BONUS = 40          # affinita' compito
PESO_PACING = 60         # penalita' rischio rate-limit al minuto


@dataclass(frozen=True)
class PunteggioModello:
    """Risultato ispezionabile della scelta (per UI/telemetria/test)."""
    modello_id: str
    punteggio: float
    motivi: tuple[str, ...]


def _bonus_affinita(m: Modello, classe: str, richiede_vision: bool) -> tuple[float, str]:
    if richiede_vision and m.vision and m.id == MODELLO_VISIONE_PREFERITO:
        return 1.0, "preferito per visione slide"
    if classe == LOCAL:
        return 0.0, ""
    if classe == "ragionamento" and m.id == MODELLO_RAGIONAMENTO_PREFERITO:
        return 1.0, "preferito per struttura capitoli"
    if classe == "scrittura" and m.id == MODELLO_SCRITTURA_PREFERITO:
        return 1.0, "preferito per scrittura paragrafi"
    return 0.0, ""


def valuta(router: Router, candidati: list[Modello], *, classe: str,
           token_input: int, token_output_stimato: int,
           richiede_vision: bool = False,
           richieste_ultimi_60s: dict[str, int] | None = None) -> list[PunteggioModello]:
    """Calcola i punteggi di tutti i candidati (nessun effetto collaterale).

    `richieste_ultimi_60s`: conteggio locale recente per provider/modello,
    usato dal pacing; opzionale (test e prime esecuzioni possono ometterlo).
    """
    score_richieste = richieste_ultimi_60s or {}
    out: list[PunteggioModello] = []
    for m in candidati:
        motivi: list[str] = []
        p = 0.0

        # --- 1. fattibilita' contesto (hard, pesantissima) ---
        necessario = token_input + token_output_stimato
        slack = m.contesto - necessario
        if slack < 0:
            p -= PESO_CONTESTO
            motivi.append(f"contesto insufficiente ({necessario} > {m.contesto})")
        elif slack < 2_048:
            p -= PESO_CONTESTO / 2
            motivi.append("finestra appena sufficiente: rischio troncamento")

        # --- 2. quota residua relativa (soft) ---
        frazione = router.frazione_usata(m)
        p -= PESO_QUOTA * frazione
        if frazione >= 1:
            motivi.append("quota giornaliera esaurita")
        elif frazione >= 0.75:
            motivi.append("quota quasi esaurita")

        # --- 3. disponibilita' dichiarata dal router ---
        if not router.disponibile(m, token_input + token_output_stimato):
            p -= PESO_QUOTA          # cooldown/bruciato: forte penalita'
            motivi.append("non disponibile (cooldown o bruciato)")

        # --- 4. affinita' di compito ---
        bonus, perche = _bonus_affinita(m, classe, richiede_vision)
        p += PESO_BONUS * bonus
        if perche:
            motivi.append(perche)

        # --- 5. pacing rpmd: evita una chiamata gia' condannata dal 429 ---
        n_recenti = score_richieste.get(m.id, 0)
        if m.rpmd and n_recenti >= m.rpmd * 0.9:
            p -= PESO_PACING
            motivi.append(f"rischio rate-limit/minuto ({n_recenti}/{m.rpmd})")

        if not motivi:
            motivi.append("idoneo: contesto, quota e capacita' sufficienti")
        out.append(PunteggioModello(m.id, round(p, 2), tuple(motivi)))
    out.sort(key=lambda s: -s.punteggio)
    return out


def scegli_strategico(router: Router, candidati: list[Modello], *,
                      classe: str, token_input: int,
                      token_output_stimato: int,
                      richiede_vision: bool = False,
                      modello_fissato: str | None = None,
                      richieste_ultimi_60s: dict[str, int] | None = None,
                      ) -> tuple[Modello | None, PunteggioModello | None]:
    """Restituisce (modello, spiegazione). None se nessun candidato conviene.

    Il pin dell'utente vince solo se il modello fissato e' tecnicamente
    idoneo (contesto/vision/disponibilita'): altrimenti si degrada
    elegantemente sul routing automatico.
    """
    punteggi = valuta(router, candidati, classe=classe,
                      token_input=token_input,
                      token_output_stimato=token_output_stimato,
                      richiede_vision=richiede_vision,
                      richieste_ultimi_60s=richieste_ultimi_60s)
    by_id = {m.id: m for m in candidati}
    if modello_fissato and modello_fissato in by_id:
        for s in punteggi:
            if s.modello_id == modello_fissato and s.punteggio > -PESO_CONTESTO / 2:
                return by_id[s.modello_id], s
    for s in punteggi:
        if s.punteggio > -PESO_CONTESTO / 2:      # scartati gli inadatti
            return by_id[s.modello_id], s
    return None, (punteggi[0] if punteggi else None)
