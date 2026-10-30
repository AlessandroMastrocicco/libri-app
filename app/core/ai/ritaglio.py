# -*- coding: utf-8 -*-
"""
ritaglio.py - Ritaglio AI delle figure dalle slide (responsabilita' unica: logica).

Alternativa automatica al ritaglio manuale col mouse nel dialog "Cattura da
dispensa": un modello VISIONE osserva la slide e propone il bounding box
normalizzato (0..1) di ogni elemento visivo utile (diagrammi, schemi,
grafici, foto), ESCLUDENDO testi, intestazioni e decorazioni (Guida per
l'AI-autore, sez. 12: solo contenuto visivo vero).

Pipeline (a costo crescente):
  1. cache su disco `_ai_ritagli.json` keyed by (file, fingerprint, hint):
     la stessa slide riproposta in paragrafi diversi costa 0 token;
  2. euristica locale gratuita: whitespace detection + bordi pagina (se
     Pillow presente) -> proposta a costo zero usata come fallback e come
     vincolo di plausibilita' per validare le coordinate AI;
  3. chiamata vision con scelta strategica del modello (scelta.py): classe
     VISIONE_PESANTE per diagrammi/formule, escalation gestita dal router
     (quota esaurita -> switch automatico al candidato successivo).

Output: `RitaglioProposto` con box normalizzato + didascalia; `applica_ritaglio`
converte il box in crop PIL sull'immagine originale (lossless, nessuna
ricodifica intermedia).

Nessuna dipendenza di rete qui: il trasporto e' il provider iniettato.
Nessuna scrittura fuori dalla cache dei ritagli.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.ai.catalogo import VISIONE_PESANTE, modelli_per_classe
from app.core.ai.pipeline import continua_se_troncato
from app.core.ai.prompt import costruisci_messaggi
from app.core.ai.router import OK, QUOTA_ESAURITA, Router
from app.core.ai.scelta import scegli_strategico
from app.core.ai.tokeni import stima_token

# ----------------------------------------------------------------------
# Prompt (statico => cache-friendly). Allineato alla Guida autore §12:
# una figura per elemento visivo, posizione precisa, niente decorazioni.
# ----------------------------------------------------------------------

ISTRUZIONE_RITAGLIO = (
    "Sei il ritagliatore di figure per un libro universitario. Ricevi UNA "
    "slide e devi individuare ogni elemento VISIVO autonomo meritevole di "
    "finire nel libro: diagrammi, schemi a blocchi, grafici, tabelle "
    "grafiche, fotografie, disegni, formule centrali presentate come "
    "blocco isolato. IGNORA completamente: titoli della slide, elenchi "
    "puntati di testo, note a pie', loghi, numeri di pagina, decorazioni, "
    "frecce puramente ornamentali. Per ciascuna figura prodici un box "
    "rettangolare che la INCLUDE INTERAMENTE con un piccolo margine, senza "
    "abbracciare testo circostante. Coordinate NORMALIZZATE 0..1 rispetto "
    "alla slide (x0,y0 angolo alto-sinistra, x1,y1 basso-destra). "
    "Rispondi SOLO con array JSON valido, senza markdown:\n"
    '[{"figura": 1, "tipo": "diagramma|schema|grafico|foto|formula", '
    '"box": [x0, y0, x1, y1], "didascalia": "<cosa guardare, <=15 parole>", '
    '"posizione": "in alto a destra"}]\n'
    "Regole: massimo 4 figure (le piu' utili); ordine = dall'alto verso il "
    "basso; se NON c'e' nulla di ritagliabile rispondi []; non inventare "
    "figure; box minimo plausibile 0.05 di lato."
)


@dataclass
class FiguraSlide:
    """Una figura individuata nella slide (box normalizzato 0..1)."""
    tipo: str = "figura"
    box: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    didascalia: str = ""
    posizione: str = ""

    def a_dict(self) -> dict:
        return {"tipo": self.tipo, "box": list(self.box),
                "didascalia": self.didascalia, "posizione": self.posizione}

    @staticmethod
    def da_dict(d: dict) -> "FiguraSlide":
        try:
            x0, y0, x1, y1 = [float(v) for v in d.get("box") or []][:4]
        except (TypeError, ValueError):
            x0, y0, x1, y1 = 0.0, 0.0, 1.0, 1.0
        return FiguraSlide(
            tipo=str(d.get("tipo") or "figura"),
            box=(x0, y0, x1, y1),
            didascalia=str(d.get("didascalia") or ""),
            posizione=str(d.get("posizione") or ""),
        )


@dataclass
class EsitoRitaglio:
    """Risultato della localizzazione figure su una slide."""
    ok: bool = False
    figure: list[FiguraSlide] = field(default_factory=list)
    fonte: str = "nessuna"          # cache | ai | euristica
    token_spesi: int = 0
    modello_usato: str | None = None
    errori: list[str] = field(default_factory=list)


# ======================================================================
# Utilita' geometriche (pure, testabili senza immagini)
# ======================================================================

def _valida_box(box) -> tuple[float, float, float, float] | None:
    """Normalizza/clampa un box AI; None se geometricamente assurdo."""
    try:
        x0, y0, x1, y1 = [float(v) for v in box][:4]
    except (TypeError, ValueError):
        return None
    # alcuni modelli restituiscono 0..1000 (formato Qwen-VL): riscala
    if max(x0, y0, x1, y1) > 1.5:
        x0, y0, x1, y1 = (v / 1000.0 for v in (x0, y0, x1, y1))
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0, x1 = max(0.0, min(1.0, x0)), max(0.0, min(1.0, x1))
    y0, y1 = max(0.0, min(1.0, y0)), max(0.0, min(1.0, y1))
    if (x1 - x0) < 0.04 or (y1 - y0) < 0.04:      # troppo piccolo = rumore
        return None
    if (x1 - x0) >= 0.98 and (y1 - y0) >= 0.98:   # slide intera = inutile
        return None
    return (round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))


def box_in_pixel(box: tuple[float, float, float, float],
                 w: int, h: int, margine_px: int = 6
                 ) -> tuple[int, int, int, int]:
    """Box normalizzato -> tuple crop PIL in pixel, con margine clampato."""
    x0, y0, x1, y1 = box
    px0 = max(0, int(round(x0 * w)) - margine_px)
    py0 = max(0, int(round(y0 * h)) - margine_px)
    px1 = min(w, int(round(x1 * w)) + margine_px)
    py1 = min(h, int(round(y1 * h)) + margine_px)
    if px1 - px0 < 8:
        px1 = min(w, px0 + 8)
    if py1 - py0 < 8:
        py1 = min(h, py0 + 8)
    return (px0, py0, px1, py1)


def applica_ritaglio(img, box: tuple[float, float, float, float],
                     margine_px: int = 6):
    """Ritaglia davvero (PIL, lossless sulla copia). Ritorna Image o None."""
    try:
        w, h = img.size
        return img.crop(box_in_pixel(box, w, h, margine_px))
    except Exception:
        return None


# ======================================================================
# Euristica locale gratuita (fallback e validatore di plausibilita')
# ======================================================================

def _euristica_box(path: Path) -> list[tuple[float, float, float, float]]:
    """Individua regioni dense non-bianche escluse le bande titolo/piede.

    Algoritmo minimale a costo zero: binarizza, proietta orizzontale,
    raggruppa i blocchi contigui di contenuto. Usato quando l'AI non e'
    disponibile; la qualita' e' inferiore ma sempre meglio del vuoto.
    """
    try:
        from PIL import Image
    except ImportError:
        return []
    try:
        img = Image.open(str(path)).convert("L")
        img.thumbnail((400, 400))
        w, h = img.size
        px = img.load()
        densita_riga = []
        for y in range(h):
            scuri = sum(1 for x in range(w) if px[x, y] < 200)
            densita_riga.append(scuri / max(1, w))
        soglia = 0.03
        blocchi, inizio = [], None
        for y, d in enumerate(densita_riga):
            attiva = d > soglia
            if attiva and inizio is None:
                inizio = y
            elif not attiva and inizio is not None:
                if y - inizio >= max(6, int(h * 0.06)):
                    blocchi.append((inizio, y))
                inizio = None
        if inizio is not None and h - inizio >= max(6, int(h * 0.06)):
            blocchi.append((inizio, h))
        # escludi banda titolo (primi ~12%) e piede (~6%)
        utile = [(a, b) for a, b in blocchi
                 if b > h * 0.14 and a < h * 0.94] or blocchi
        out = []
        for a, b in utile[:4]:
            out.append((0.02, round(a / h, 4), 0.98, round(b / h, 4)))
        return out
    except Exception:
        return []


# ======================================================================
# Cache su disco (la stessa slide riproposta non si paga due volte)
# ======================================================================

def _fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha1()
    for p in sorted(str(x) for x in paths):
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).name}:{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            h.update(Path(p).name.encode())
    return h.hexdigest()[:16]


def _cache_path(libro_dir: Path) -> Path:
    return libro_dir / "slide_estratte" / "_ai_ritagli.json"


def _leggi_cache(libro_dir: Path) -> dict:
    p = _cache_path(libro_dir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"versione": 1, "entries": {}}


def _salva_cache(libro_dir: Path, cache: dict) -> None:
    p = _cache_path(libro_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


# ======================================================================
# Parsing risposta AI (tollerante, come analisi._scheda_piu_grande)
# ======================================================================

def _parse_figure(testo: str) -> list[FiguraSlide]:
    m = re.search(r"\[[\s\S]*\]", testo or "")
    if not m:
        return []
    try:
        dati = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(dati, list):
        return []
    figure: list[FiguraSlide] = []
    for item in dati:
        if not isinstance(item, dict):
            continue
        f = FiguraSlide.da_dict(item)
        box = _valida_box(item.get("box"))
        if box is None:
            continue
        f.box = box
        figure.append(f)
    return figure[:4]


# ======================================================================
# API principale
# ======================================================================

def localizza_figure(*, router: Router, provider, slide_path: Path,
                     libro_dir: Path, hint: str = "",
                     modello_fissato: str | None = None) -> EsitoRitaglio:
    """Trova le figure ritagliabili in UNA slide (cache -> AI -> euristica).

    `provider`: `(modello, messaggi, max_tokens) -> (testo, tok, esito)`
    (ProviderComposito.chiama). `hint`: eventuale descrizione della figura
    cercata (es. nome file dell'immagine referenziata dal paragrafo) per
    scegliere fra piu' proposte. Ritorna EsitoRitaglio; scrive solo cache.
    """
    esito = EsitoRitaglio()
    path = Path(str(slide_path))
    if not path.is_file():
        esito.errori.append(f"Slide non trovata: {path}")
        return esito

    cache = _leggi_cache(libro_dir)
    chiave = f"{path.name}|{_fingerprint([path])}|{hint.strip().lower()[:60]}"
    entry = cache["entries"].get(chiave)
    if entry is not None:
        esito.figure = [FiguraSlide.da_dict(f) for f in entry.get("figure", [])]
        esito.fonte = "cache"
        esito.ok = True
        return esito

    # --- chiamata vision con scelta strategica (classe pesante: geometria) ---
    candidati = [m for m in modelli_per_classe(VISIONE_PESANTE) if m.vision]
    tok_in = stima_token(ISTRUZIONE_RITAGLIO) + 700 + stima_token(hint)
    modello, _punto = scegli_strategico(
        router, candidati, classe=VISIONE_PESANTE, token_input=tok_in,
        token_output_stimato=400, richiede_vision=True,
        modello_fissato=modello_fissato)
    if modello is not None:
        testi = [ISTRUZIONE_RITAGLIO]
        if hint:
            testi.append(f"Cerca in particolare: {hint}.")
        messaggi, _k = costruisci_messaggi(
            "Localizzi figure in slide accademiche. Solo output JSON.",
            [], "")
        parti = [{"type": "text", "text": "\n\n".join(testi)},
                 {"type": "image_ref", "path": str(path)}]
        messaggi.append({"role": "user", "content": parti})
        testo, tok, ris = provider(modello, messaggi,
                                   min(modello.max_output, 800))
        if ris == OK and "[[TRONCATO]]" in testo:
            extra = 0
            testo, extra = continua_se_troncato(provider, modello,
                                                messaggi, testo)
            tok += extra
        router.registra_esito(modello, ris, tok)
        esito.token_spesi = tok
        esito.modello_usato = modello.id
        if ris == OK:
            esito.figure = _parse_figure(testo.replace("[[TRONCATO]]", ""))
            if esito.figure:
                esito.fonte = "ai"
                esito.ok = True
                cache["entries"][chiave] = {
                    "figure": [f.a_dict() for f in esito.figure]}
                _salva_cache(libro_dir, cache)
                return esito
            esito.errori.append("AI: nessuna figura individuata.")
        elif ris != QUOTA_ESAURITA:
            esito.errori.append(f"Esito {ris} su {modello.id}.")
        else:
            esito.errori.append("Quota vision esaurita oggi.")

    # --- fallback gratuito: euristica locale (mai blocco totale) ---
    eur = _euristica_box(path)
    if eur:
        esito.figure = [FiguraSlide(tipo="regione", box=b,
                                    didascalia="regione di contenuto (euristica)")
                        for b in eur]
        esito.fonte = "euristica"
        esito.ok = True
    return esito


def suggerisci_figura(esito: EsitoRitaglio, hint: str = "") -> FiguraSlide | None:
    """Sceglie la proposta migliore per l'utente (hint nel match, poi area)."""
    if not esito.figure:
        return None
    if hint:
        h = hint.lower()
        parole = [w for w in re.split(r"[^a-z0-9]+", h) if len(w) >= 4]
        migliori = [f for f in esito.figure
                    if any(p in (f.didascalia + " " + f.posizione + " "
                                 + f.tipo).lower() for p in parole)]
        if migliori:
            return max(migliori, key=lambda f: (f.box[2] - f.box[0])
                       * (f.box[3] - f.box[1]))
    return max(esito.figure, key=lambda f: (f.box[2] - f.box[0])
               * (f.box[3] - f.box[1]))
