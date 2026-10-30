# -*- coding: utf-8 -*-
"""
tokeni.py - Algoritmi di stima e ottimizzazione dei token (bozza).

Nessun download di tokenizer pesanti: la stima euristica e' CJK-safe ed e'
calibrata per i modelli chat moderni (BPE ~4 char/token sul latino).
Se `tiktoken` sara' disponibile potra' sostituire la stima per la
calibrazione, ma l'interfaccia resta questa.
"""

from __future__ import annotations

from dataclasses import dataclass


# ======================================================================
# Stima
# ======================================================================

_PESI = {
    # classi di caratteri -> tokeni per carattere (frazione)
    "latino": 0.25,      # ~4 char/tok
    "cirillico_cjk": 0.20,  # ~5 char/tok (i CJK spesso 1 tok/char o 1 tok/2char)
    "markup": 0.34,      # ~3 char/tok: punteggiatura, codice, whitespace
}


def _peso_carattere(c: str) -> float:
    o = ord(c)
    if c.isascii():
        if c.isalnum() or c == " ":
            return _PESI["latino"]
        return _PESI["markup"]
    # Cirillico
    if 0x0400 <= o <= 0x04FF:
        return _PESI["cirillico_cjk"]
    # CJK e simili (ideogrammi, hangul, kana): densita' token alta
    if (0x3040 <= o <= 0x30FF) or (0x3400 <= o <= 0x9FFF) or \
       (0xAC00 <= o <= 0xD7AF) or (0xF900 <= o <= 0xFAFF):
        return 0.60  # ~1.7 char/tok: gli ideogrammi costano cari
    # Latino esteso (accentati IT/FR/DE): comportamento vicino al latino
    if 0x00C0 <= o <= 0x024F:
        return 0.28
    # Matematica/simboli rari: spesso token dedicati
    if 0x2000 <= o <= 0x2BFF or 0x1D400 <= o <= 0x1D7FF:
        return 0.50
    return _PESI["markup"]


def stima_token(testo: str) -> int:
    """Stima conservativa dei token di una stringa (mai sottostimare)."""
    if not testo:
        return 0
    tot = sum(_peso_carattere(c) for c in testo)
    return int(tot) + 1


def stima_token_messaggi(messaggi: list[dict]) -> int:
    """Token stimati di una lista messaggi stile OpenAI, overhead incluso."""
    tot = 0
    for m in messaggi:
        tot += 4  # overhead per messaggio (ruolo, delimitatori)
        contenuto = m.get("content", "")
        if isinstance(contenuto, str):
            tot += stima_token(contenuto)
        elif isinstance(contenuto, list):  # multimodale
            for parte in contenuto:
                if parte.get("type") == "text":
                    tot += stima_token(parte.get("text", ""))
                elif parte.get("type") == "image_url":
                    # immagine ~1024px: ~800-1200 token a seconda del provider
                    tot += 1_100
    tot += 2  # overhead risposta
    return tot


# ======================================================================
# Troncamento sicuro
# ======================================================================

def troncava_per_righe(testo: str, max_token: int, coda: str = "…[troncato]") -> str:
    """Taglia il testo riga per riga restando sotto il budget; non spezza
    mai una riga a meta' (preserva la leggibilita' per il modello)."""
    righe = testo.splitlines(keepends=True)
    out: list[str] = []
    usati = 0
    budget = max_token - stima_token(coda)
    for r in righe:
        t = stima_token(r)
        if usati + t > budget:
            break
        out.append(r)
        usati += t
    if not out:
        # nemmeno una riga sta nel budget: tagliamo per caratteri, sempre
        # con la coda applicata, per non restituire un testo sopra budget.
        appross = max(0, int(budget * 3))
        return testo[:appross] + coda
    return "".join(out).rstrip("\n") + "\n" + coda


# ======================================================================
# Budget assembler
# ======================================================================

@dataclass
class BloccoContesto:
    """Un pezzo di contesto con priorita' d'uso (1 = indispensabile)."""
    nome: str
    testo: str
    priorita: int = 50
    comprimibile: bool = True   # puo' essere troncato invece che escluso

    @property
    def costo(self) -> int:
        return stima_token(self.testo)


def assembla_contesto(blocchi: list[BloccoContesto], budget: int,
                      margine_uscita: int = 1024) -> tuple[list[BloccoContesto], int]:
    """Budget assembler: riempe il contesto per priorita' crescente; i blocchi
    oltre il tetto vengono troncati (se comprimibili) o esclusi. Restituisce
    (blocchi_finali, token_usati). Il margine_uscita e' riservato all'output."""
    utile = budget - margine_uscita
    ordinati = sorted(blocchi, key=lambda b: (b.priorita, -b.costo))
    selezionati: list[BloccoContesto] = []
    usati = 0
    scarti: list[str] = []
    for b in ordinati:
        if usati + b.costo <= utile:
            selezionati.append(b)
            usati += b.costo
            continue
        se_serve_troncare = b.comprimibile and b.priorita <= 60
        if se_serve_troncare:
            spazio = utile - usati
            if spazio > 60:  # sotto 60 token il blocco e' inutile
                tagliato = troncava_per_righe(b.testo, spazio)
                b2 = BloccoContesto(b.nome + " (troncato)", tagliato,
                                    b.priorita, False)
                selezionati.append(b2)
                usati += b2.costo
            else:
                scarti.append(b.nome)
        else:
            scarti.append(b.nome)
    return selezionati, usati
