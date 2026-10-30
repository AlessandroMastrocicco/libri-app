# -*- coding: utf-8 -*-
"""
pianificatore.py - Pianificazione strategica della generazione (nuovo).

Due decisioni "di strategia" che prima spettavano all'utente:

1. QUANTI PARAGRAFI e con quali titoli per un capitolo: algoritmo di
   partizione che distribuisce le slide pertinenti in blocchi tematici
   coesi (vicinanza di lezione + affinita' lessicale), con vincoli
   3..6 paragrafi per capitolo come nella pratica editoriale del progetto.

2. COSTO STIMATO DI UN PIANO: per ogni paragrafo pianificato stima i token
   di input (contesto) e output (draft ~1500-3000 parole) e verifica che le
   quote residue dei provider lo coprano; se il piano eccede, propone una
   riduzione (meno paragrafi o analisi slide saltata perche' gia' in cache).

Nessuna chiamata di rete: il pianificatore e' locale, deterministico e
testabile; il modello forte di ragionamento verra' usato (in pipeline) solo
per raffinare i titoli quando la partizione euristica e' ambigua.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from app.core.ai.tokeni import stima_token


# ======================================================================
# Partizione tematica delle slide -> paragrafi
# ======================================================================

_PARAGRAFO_MIN = 3
_PARAGRAFO_MAX = 6
_SLIDE_PER_PARAGRAFO = 6      # densita' obiettivo: ~6 slide per paragrafo


def _token_testo(scheda: dict) -> set[str]:
    blob = json.dumps(scheda, ensure_ascii=False).lower()
    return {w for w in re.findall(r"[a-zàèéìòù_]{4,}", blob)}


def partisci_schede(schede: list[dict]) -> list[list[dict]]:
    """Raggruppa le schede-slide in blocchi tematici contigui.

    Algoritmo: ordinamento per (lezione, slide); poi scansione con finestra
    di similarita' Jaccard fra testi adiacenti. Un taglio va messo quando
    l'affinita' scende sotto la soglia MA solo se il blocco corrente ha gia'
    almeno meta' della densita' obiettivo (evita micro-paragrafi). Il numero
    finale di blocchi viene normalizzato nell'intervallo [3, 6] unendo i
    blocchi piu' simili o spezzando i piu' densi.
    """
    if not schede:
        return []
    def chiave_ordine(s):
        lez = str(s.get("id_lezione") or s.get("lezione") or "L1")
        try:
            n_lez = int(re.sub(r"\D", "", lez) or 1)
        except ValueError:
            n_lez = 1
        return (n_lez, int(s.get("slide") or 0))
    ordinate = sorted(schede, key=chiave_ordine)

    # ---- fase 1: tagli per affinita' ----
    blocchi: list[list[dict]] = [[ordinate[0]]]
    insiemi = [_token_testo(ordinate[0])]
    for s, tokens in zip(ordinate[1:], [_token_testo(x) for x in ordinate[1:]]):
        prec = insiemi[-1]
        inter = len(prec & tokens)
        unione = max(len(prec | tokens), 1)
        jaccard = inter / unione
        # media mobile del blocco contro il nuovo elemento
        cumulato = set().union(*insiemi) if len(insiemi) <= 6 else prec
        aff_blocco = len(cumulato & tokens) / max(len(cumulato | tokens), 1)
        soglia = 0.06
        denso = len(blocchi[-1]) >= _SLIDE_PER_PARAGRAFO // 2
        if (jaccard < soglia and aff_blocco < soglia and denso) or \
           len(blocchi[-1]) >= _SLIDE_PER_PARAGRAFO * 2:
            blocchi.append([s])
            insiemi.append(tokens)
        else:
            blocchi[-1].append(s)
            insiemi.append(prec | tokens)

    # ---- fase 2: normalizza conteggio in [MIN, MAX] ----
    while len(blocchi) > _PARAGRAFO_MAX:
        # unisci i due blocchi adiacenti piu' simili
        migliore, idx = -1.0, 0
        for i in range(len(blocchi) - 1):
            a = set().union(*[_token_testo(x) for x in blocchi[i]])
            b = set().union(*[_token_testo(x) for x in blocchi[i + 1]])
            sim = len(a & b) / max(len(a | b), 1)
            if sim > migliore:
                migliore, idx = sim, i
        blocchi[idx] = blocchi[idx] + blocchi[idx + 1]
        del blocchi[idx + 1]

    if len(blocchi) < _PARAGRAFO_MIN:
        totale = sum(len(b) for b in blocchi)
        target = min(_PARAGRAFO_MIN, max(totale // 2, 1))
        while len(blocchi) < target:
            # spezza il blocco piu' lungo a meta'
            i_max = max(range(len(blocchi)), key=lambda i: len(blocchi[i]))
            b = blocchi[i_max]
            if len(b) < 2:
                break
            meta = len(b) // 2
            blocchi[i_max:i_max + 1] = [b[:meta], b[meta:]]

    return blocchi


# ======================================================================
# Bozza di scaletta (titoli) senza modello: dai titoli delle slide
# ======================================================================

def titoli_bozza(blocchi: list[list[dict]]) -> list[str]:
    """Titolo provvisorio: take il titolo della slide piu' rappresentativa
    (quella con piu' punti). Servono da input al modello di ragionamento e
    da fallback assoluto se il modello non e' disponibile."""
    out = []
    for i, blocco in enumerate(blocchi, 1):
        candidati = sorted(
            blocco,
            key=lambda s: len(s.get("punti") or []), reverse=True)
        titolo = ""
        for c in candidati:
            t = str(c.get("titolo") or "").strip()
            if t:
                titolo = t
                break
        out.append(titolo or f"Paragrafo {i}")
    return out


# ======================================================================
# Stima costi del piano e verifica strategica delle quote
# ======================================================================

@dataclass
class CostoParagrafo:
    titolo: str
    n_slide: int
    input_tok: int
    output_tok: int

    @property
    def totale(self) -> int:
        return self.input_tok + self.output_tok


@dataclass
class Piano:
    paragrafi: list[CostoParagrafo] = field(default_factory=list)
    fattibile: bool = True
    note: list[str] = field(default_factory=list)

    @property
    def costo_totale(self) -> int:
        return sum(p.totale for p in self.paragrafi)


_PAROLE_MIN, _PAROLE_MAX = 1_500, 3_000      # contratto del pattern
_TOK_PER_PAROLA_IT = 1.6                     # stima media it-latino
_PREZZO_SCHEDA_IN = 350                      # token medi scheda slide nel prompt


def stimapiano(blocchi: list[list[dict]], *, digest_precedenti_tok: int = 0,
               quota_residua_per_paragrafo: int | None = None) -> Piano:
    """Stima il costo dell'intero capitolo e dichiara se e' fattibile oggi.

    `quota_residua_per_paragrafo`: budget token medio disponibile per
    paragrafo presso i modelli SCRITTURA selezionabili dal router. Se il
    piano lo supera, il piano viene marcato non fattibile con nota operativa
    (l'UI proporra': ridurre i paragrafi, rimandare a dopo il rollover,
    oppure passare alla modalita' manuale per gli ultimi).
    """
    titoli = titoli_bozza(blocchi)
    piano = Piano()
    for blocco, titolo in zip(blocchi, titoli):
        input_tok = (_PREZZO_SCHEDA_IN * len(blocco)
                     + digest_precedenti_tok + 2_600)  # contratto+istruzioni
        output_tok = int((_PAROLE_MIN + _PAROLE_MAX) / 2 * _TOK_PER_PAROLA_IT)
        piano.paragrafi.append(CostoParagrafo(titolo, len(blocco),
                                              input_tok, output_tok))
    if quota_residua_per_paragrafo is not None:
        oltre = [p for p in piano.paragrafi
                 if p.totale > quota_residua_per_paragrafo]
        if oltre:
            piano.fattibile = False
            piano.note.append(
                f"{len(oltre)}/{len(piano.paragrafi)} paragrafi superano la "
                f"quota residua stimata ({quota_residua_per_paragrafo:,} tok). "
                "Riduci i paragrafi o attendi il rollover UTC.")
    return piano


def suggerisci_riduzione(piano: Piano, quota_residua: int) -> list[str]:
    """Scelte strategiche alternative quando il piano non e' fattibile oggi."""
    opzioni = []
    n_coperti = 0
    cumulato = 0
    for p in piano.paragrafi:
        if cumulato + p.totale > quota_residua:
            break
        cumulato += p.totale
        n_coperti += 1
    if n_coperti:
        opzioni.append(f"Genera ora i primi {n_coperti} paragrafi "
                       f"(~{cumulato:,} token) e rimanda i restanti.")
    k = math.ceil(piano.costo_totale / max(quota_residua, 1))
    if k > 1:
        opzioni.append(f"Attendere {k} rollover UTC per completare il piano.")
    opzioni.append("Usare la modalita' manuale (copia regole) per i restanti.")
    return opzioni
