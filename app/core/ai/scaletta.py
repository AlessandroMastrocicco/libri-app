# -*- coding: utf-8 -*-
"""
scaletta.py - Estrazione della SCALETTA di un capitolo dalle slide.

Funzione richiesta dalla "gestione dispense": dato il PDF (o le PNG gia'
estratte) di una dispensa, produrre l'indice del capitolo senza lavoro
manuale. Due percorsi, con costo crescente:

  1. locale (costo ZERO): usa la cache delle schede-slide se esiste;
     altrimenti legge il testo incorporato nel PDF (PyMuPDF) e costruisce
     le schede con euristica (prima riga = titolo, bullet = punti).
  2. AI (classe RAGIONAMENTO, modello leggero): raffina i titoli locali in
     titoli editoriali coerenti, mantenendo l'ordine e il numero dei blocchi.

Il routing strategico (finestra di contesto, quota residua proporzionale,
affinita' di compito) e' delegato a scelta.scegli_strategico; la traduzione
HTTP->esito ai provider. Nessuna scrittura fuori da
`slide_estratte/_ai_scaletta_<slug>.json`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.ai.catalogo import RAGIONAMENTO, modelli_per_classe
from app.core.ai.contesto import carica_schede
from app.core.ai.prompt import costruisci_messaggi
from app.core.ai.router import OK, Router
from app.core.ai.scelta import scegli_strategico
from app.core.ai.tokeni import stima_token


# ======================================================================
# Struttura dati della scaletta
# ======================================================================

@dataclass
class VoceScaletta:
    """Un paragrafo previsto: titolo + slide che lo coprono."""
    titolo: str
    slide: list[int] = field(default_factory=list)
    concetti: list[str] = field(default_factory=list)

    def a_dict(self) -> dict:
        return {"titolo": self.titolo, "slide": self.slide,
                "concetti": self.concetti}


@dataclass
class Scaletta:
    dispensa: str = ""
    id_lezione: str = "L1"
    voci: list[VoceScaletta] = field(default_factory=list)
    fonte: str = "locale"            # locale | cache | ai
    token_spesi: int = 0
    modello_usato: str | None = None
    note: list[str] = field(default_factory=list)

    @property
    def n_slide(self) -> int:
        return sum(len(v.slide) for v in self.voci)

    def a_dict(self) -> dict:
        return {"dispensa": self.dispensa, "id_lezione": self.id_lezione,
                "fonte": self.fonte, "token_spesi": self.token_spesi,
                "modello_usato": self.modello_usato,
                "voci": [v.a_dict() for v in self.voci]}

    def to_markdown(self) -> str:
        """Output pronto da incollare/leggere: indice del capitolo."""
        righe = [f"# Scaletta — {self.dispensa}", ""]
        for i, v in enumerate(self.voci, 1):
            intervallo = ""
            if v.slide:
                fine = v.slide[-1]
                inizio = v.slide[0]
                intervallo = f" (slide {inizio}" + \
                    (f"-{fine}" if fine != inizio else "") + ")"
            righe.append(f"{i}. **{v.titolo}**{intervallo}")
            for c in v.concetti[:4]:
                righe.append(f"   - {c}")
        return "\n".join(righe) + "\n"


# ======================================================================
# Schede-slide SENZA modello (costo zero)
# ======================================================================

_BULLET = re.compile(r"^\s*(?:[•·▪◦‣∙*o-]|\d+[.)])\s+(?=\S)")
_TITOLO_MAX = 90


def _pulisci_riga(riga: str) -> str:
    r = _BULLET.sub("", riga.strip()).strip(" \t:;.,")
    return re.sub(r"\s+", " ", r)


def schede_da_testo(testo_pagine: list[str],
                    max_punti: int = 6) -> list[dict]:
    """Trasforma il testo estratto da ogni pagina in una scheda-slide.

    Euristica didattica: la prima riga significativa e' il titolo, le
    successive (bullet o frasi brevi) sono i punti. Righe troppo lunghe
    (paragrafi di trascrizione) vengono saltate come titolo.
    """
    schede: list[dict] = []
    for n, pagina in enumerate(testo_pagine, start=1):
        righe = [_pulisci_riga(x) for x in (pagina or "").splitlines()]
        righe = [x for x in righe if len(x) >= 3]
        titolo = ""
        punti: list[str] = []
        for r in righe:
            if not titolo and len(r) <= _TITOLO_MAX:
                titolo = r
                continue
            if len(punti) < max_punti and len(r) <= 200:
                punti.append(r)
        schede.append({"slide": n, "titolo": titolo or f"Slide {n}",
                       "punti": punti})
    return schede


def schede_da_pdf(pdf_path: Path) -> tuple[list[dict], list[str]]:
    """Prova la via gratuita: testo incorporato nel PDF (no OCR, no rete).

    Ritorna (schede, note). Liste vuote se il PDF e' scansionato o PyMuPDF
    manca: sara' la fase AI (visione) a prendere il relais.
    """
    note: list[str] = []
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return [], ["PyMuPDF non disponibile: servirà l'analisi AI."]
    try:
        with fitz.open(str(pdf_path)) as doc:
            pagine = [page.get_text("text") for page in doc]
    except Exception as e:                        # PDF corrotto/cifrato
        return [], [f"Lettura PDF fallita ({e}): servirà l'analisi AI."]
    utile = sum(1 for p in pagine if len((p or "").strip()) >= 40)
    if utile < max(1, len(pagine) // 3):
        return [], ["PDF senza testo incorporato (scansione): " \
                    "servirà l'analisi AI sulle immagini."]
    note.append(f"Testo letto da {utile}/{len(pagine)} pagine: analisi "
                "locale a costo zero.")
    return schede_da_testo(pagine), note


def schede_esistenti(libro_dir: Path, id_lezione: str) -> list[dict]:
    """Riuso totale: se le schede (AI o locali) ci sono gia', costo 0."""
    schede = carica_schede(libro_dir) or {}
    return list(schede.get(id_lezione) or [])


# ======================================================================
# Partizione + titoli (riusa il pianificatore esistente)
# ======================================================================

def scaletta_locale(schede: list[dict], *, dispensa: str = "",
                    id_lezione: str = "L1",
                    fonte: str = "locale") -> Scaletta:
    """Costruisce la scaletta dalle schede con l'algoritmo del pianificatore
    (partizione tematica Jaccard + normalizzazione 3..6 blocchi)."""
    from app.core.ai import pianificatore

    scaletta = Scaletta(dispensa=dispensa, id_lezione=id_lezione,
                        fonte=fonte)
    if not schede:
        scaletta.note.append("Nessuna scheda slide disponibile.")
        return scaletta
    blocchi = pianificatore.partisci_schede(
        [{**s, "id_lezione": id_lezione} for s in schede])
    titoli = pianificatore.titoli_bozza(blocchi)
    for blocco, titolo in zip(blocchi, titoli):
        concetti = [str(s.get("titolo") or "").strip() for s in blocco]
        scaletta.voci.append(VoceScaletta(
            titolo=titolo,
            slide=[int(s.get("slide") or 0) for s in blocco],
            concetti=[c for c in concetti if c][:6]))
    return scaletta


# ======================================================================
# Raffinamento AI dei titoli (classe RAGIONAMENTO, modelli leggeri)
# ======================================================================

ISTRUZIONE_SCALETTA = (
    "Sei un curatore editoriale di dispense universitarie. Ricevi la "
    "scaletta BOZZA di un capitolo (blocchi di slide con titoli grezzi). "
    "Riscrivi SOLO i titoli in forma editoriale (max 8 parole, lingua "
    "italiana, fedeli ai concetti elencati, senza inventare). Non cambiare "
    "numero, ordine o contenuti dei blocchi. Rispondi SOLO con un array "
    'JSON: [{"titolo": "..."}, ...]'
)


def _titoli_json(text: str, attesi: int) -> list[str]:
    m = re.search(r"\[[\s\S]*\]", text or "")
    if not m:
        return []
    try:
        dati = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = [str(d.get("titolo") or "").strip()
           for d in dati if isinstance(d, dict)]
    return out if len(out) == attesi else []


def raffinamento_con_ai(*, router: Router, provider, scaletta: Scaletta,
                        modello_fissato: str | None = None) -> Scaletta:
    """Sostituisce i titoli-bozza con titoli editoriali generati da un
    modello LEGGERO di ragionamento (task semplice: contest small, ~1k tok).

    Su qualunque errore (quota, JSON malformato, conteggio diverso) la
    scaletta resta quella locale: il raffinamento e' puramente opzionale.
    """
    if not scaletta.voci:
        return scaletta
    bozza = [{"titolo": v.titolo, "concetti": v.concetti[:4]}
             for v in scaletta.voci]
    payload = json.dumps(bozza, ensure_ascii=False)
    messaggi, _k = costruisci_messaggi(
        "Riscrivi titoli di scaletta in italiano. Solo output JSON.",
        [payload], ISTRUZIONE_SCALETTA)
    tok_in = stima_token(messaggi[1]["content"]) + 400
    candidati = list(modelli_per_classe(RAGIONAMENTO))
    modello, _punto = scegli_strategico(
        router, candidati, classe=RAGIONAMENTO, token_input=tok_in,
        token_output_stimato=600, richiede_vision=False,
        modello_fissato=modello_fissato)
    if modello is None:
        scaletta.note.append("Nessun modello ragionamento disponibile oggi: "
                             "titoli locali mantenuti.")
        return scaletta
    testo, tok, ris = provider(modello, messaggi, min(modello.max_output,
                                                      1_500))
    router.registra_esito(modello, ris, tok)
    scaletta.token_spesi += tok
    if ris != OK:
        scaletta.note.append(f"Raffinamento saltato ({ris}): titoli locali.")
        return scaletta
    titoli = _titoli_json(testo.replace("[[TRONCATO]]", ""),
                          len(scaletta.voci))
    if not titoli:
        scaletta.note.append("Risposta AI non interpretabile: titoli locali.")
        return scaletta
    for voce, nuovo in zip(scaletta.voci, titoli):
        if nuovo:
            voce.titolo = nuovo
    scaletta.fonte = "ai"
    scaletta.modello_usato = modello.id
    return scaletta


# ======================================================================
# API principale usata dalla UI (gestione dispense)
# ======================================================================

def estrai_scaletta(*, root: Path, slug: str, dispensa: str,
                    pdf_path: Path | None = None,
                    id_lezione: str | None = None,
                    router: Router | None = None, provider=None,
                    forza_ai: bool = False,
                    modello_fissato: str | None = None) -> Scaletta:
    """Scalietta del capitolo partendo dalle slide della dispensa.

    Strategia a costo crescente (documentata in docs/BOZZA_SISTEMA_AI.md):
      cache schede (0 tok) -> testo PDF locale (0 tok) -> visione AI
      (se `provider` e nessuna scheda) -> ragionamento AI per i titoli
      (solo se `router`+`provider` forniti).
    Nessun file di capitolo viene toccato: si scrive solo la cache
    `_ai_scaletta_<dispensa>.json` accanto alle schede.
    """
    libro_dir = Path(root) / "libri" / slug
    cartella = libro_dir / "slide_estratte"
    if id_lezione is None:
        id_lezione = _id_lezione_da_dispensa(cartella, dispensa)

    # --- 1. cache: costo zero garantito --------------------------------
    schede = schede_esistenti(libro_dir, id_lezione)
    fonte = "cache"
    if not schede:
        # --- 2. via locale gratuita: testo incorporato nel PDF ---------
        note: list[str] = []
        if pdf_path and Path(pdf_path).is_file():
            schede, note = schede_da_pdf(Path(pdf_path))
        if not schede and provider is not None and router is not None:
            # --- 3. visione AI (gia' implementata in analisi.py) -------
            from app.core.ai.analisi import analizza_slides
            es = analizza_slides(router=router, provider=provider,
                                 libro_dir=libro_dir, dispensa=dispensa,
                                 id_lezione=id_lezione)
            note.extend(es.errori)
            schede = schede_esistenti(libro_dir, id_lezione)
            fonte = "visione-ai"
        elif schede:
            fonte = "pdf-locale"
        else:
            fonte = "vuoto"
            note.append("Estrai prima le pagine della dispensa (o fornisci "
                        "il PDF originale).")
        scaletta = scaletta_locale(schede, dispensa=dispensa,
                                   id_lezione=id_lezione, fonte=fonte)
        scaletta.note.extend(note)
        if schede and router is not None and provider is not None:
            scaletta = raffinamento_con_ai(
                router=router, provider=provider, scaletta=scaletta,
                modello_fissato=modello_fissato)
        salva_scaletta(cartella, scaletta)
        return scaletta

    # --- cache colpita: riusa anche la scalietta salvata, se coerente --
    salvata = leggi_scaletta(cartella, dispensa)
    if salvata and not forza_ai:
        return salvata
    scaletta = scaletta_locale(schede, dispensa=dispensa,
                               id_lezione=id_lezione, fonte="cache")
    if router is not None and provider is not None:
        scaletta = raffinamento_con_ai(
            router=router, provider=provider, scaletta=scaletta,
            modello_fissato=modello_fissato)
    salva_scaletta(cartella, scaletta)
    return scaletta


# ----------------------------------------------------------------------
# Persistenza (accanto alla cache schede, stessa cartella)
# ----------------------------------------------------------------------

def _slug_nome(nome: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (nome or "").lower()).strip("-")
    return s or "dispensa"


def path_scaletta(cartella_slide: Path, dispensa: str) -> Path:
    return cartella_slide / f"_ai_scaletta_{_slug_nome(dispensa)}.json"


def salva_scaletta(cartella_slide: Path, scaletta: Scaletta) -> Path:
    p = path_scaletta(cartella_slide, scaletta.dispensa)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(scaletta.a_dict(), ensure_ascii=False,
                              indent=1), encoding="utf-8")
    tmp.replace(p)
    return p


def leggi_scaletta(cartella_slide: Path, dispensa: str) -> Scaletta | None:
    p = path_scaletta(cartella_slide, dispensa)
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return Scaletta(
            dispensa=d.get("dispensa", dispensa),
            id_lezione=d.get("id_lezione", "L1"),
            voci=[VoceScaletta(**v) for v in d.get("voci", [])],
            fonte=d.get("fonte", "cache"),
            token_spesi=int(d.get("token_spesi", 0)),
            modello_usato=d.get("modello_usato"),
            note=list(d.get("note", [])))
    except Exception:
        return None


def _id_lezione_da_dispensa(cartella_slide: Path, dispensa: str) -> str:
    """Allinea la lezione della dispensa tramite la mappatura esistente."""
    p = Path(cartella_slide) / "_mappatura_lezioni.json"
    if p.is_file():
        try:
            mappa = json.loads(p.read_text(encoding="utf-8"))
            for nome, idl in (mappa.get("per_dispensa") or {}).items():
                if _slug_nome(nome) == _slug_nome(dispensa):
                    return str(idl)
        except Exception:
            pass
    return "L1"
