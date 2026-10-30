# -*- coding: utf-8 -*-
"""
trascrizione.py - FASE 1 del flusso "Genera scaletta capitolo": trascrizione
slide per slide delle dispense caricate, con persistenza in un DB locale.

Perche' un DB dedicato (e non solo la cache schede):
  * la trascrizione approfondita di una slide e' il prodotto PI' costoso
    dell'intero flusso (visione pesante + output lungo); se salvata qui,
    ogni slide viene analizzata UNA VOLTA SOLA per sempre, e i passaggi
    successivi (scaletta, scrittura paragrafi) rileggono testo a costo 0;
  * le figure rilevate vengono registrate come righe separate: servono al
    ritaglio AI e al blocco "Tratto da" dei fonti;
  * struttura a tabelle minime, consultabile anche all'esterno con sqlite3.

Token-ottimizzazioni applicate:
  * batch multi-immagine (taglia slide per chiamata: 1 system prompt pagato
    una volta ogni `taglia` slide);
  * cache su file DB con fingerprint dei PNG: slide gia' trascritte = 0 tok;
  * compressione immagini a monte (app.core.ai.visione, usata dai provider);
  * scelta strategica del modello: classe VISIONE_PESANTE (il piu' potente
    disponibile oggi con quota), escalation automatica tra modelli alla
    scadenza delle quote (router).

Responsabilita' MINIMA: solo trascrizione + persistenza. La partizione in
paragrafi vive in scaletta.py; l'UI in screens/estrattore_slide.py.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from app.core.ai.catalogo import VISIONE_PESANTE, modelli_per_classe
from app.core.ai.pipeline import continua_se_troncato
from app.core.ai.prompt import costruisci_messaggi
from app.core.ai.router import OK, QUOTA_ESAURITA, Router
from app.core.ai.scelta import scegli_strategico
from app.core.ai.tokeni import stima_token

NOME_DB = "_db_slide.db"          # dentro <libro>/slide_estratte/

# ----------------------------------------------------------------------
# Prompt di trascrizione (statico => prefix-cache friendly)
# Allineato alla Guida per l'AI-autore: sez. 5 Fase B (inventario completo)
# e sez. 12.3 (ogni figura separata, con posizione precisa nella slide).
# ----------------------------------------------------------------------

ISTRUZIONE_TRASCRIZIONE = (
    "Sei il trascrittore della FASE 1 di un libro universitario: per OGNI "
    "immagine di slide ricevuta produci una scheda JSON di INVENTARIO "
    "COMPLETO, cioe' tutto cio' che la slide contiene o implica, senza "
    "spiegazioni ne' commenti tuoi. Rispondi SOLO con un array JSON valido, "
    "senza markdown, un oggetto per immagine nello stesso ordine.\n"
    'Formato:\n'
    '[{"slide": <numero>, "titolo": "<titolo della slide>", '
    '"testo": "<trascrizione integrale fedele: frasi complete, elenchi '
    'separati da newline, formule in LaTeX inline $...$>", '
    '"concetti": ["<termine> [introdotto|ripreso]", ...], '
    '"figure": [{"tipo": "diagramma|schema|grafico|foto|disegno", '
    '"posizione": "in alto a sinistra|al centro|...", '
    '"descrizione": "<cosa rappresenta, cosa guardare>"}], '
    '"dubbi": ["<elemento illeggibile o ambiguo>", ...]}]\n'
    "Regole: `testo` deve permettere a uno studente di ricostruire la "
    "slide senza averla vista (passaggi impliciti marcati come 'implica:' "
    "su riga propria); mai riferimenti a 'questa slide dice'; in `figure` "
    "elenca SEPARATAMENTE ogni elemento visivo utile (mai testi, loghi, "
    "intestazioni o decorazioni), con posizione PRECISA nella slide; "
    "`dubbi` per cio' che non sei certo di aver letto (segnala, non "
    "indovinare); non inventare contenuti assenti."
)


def _array_json(testo: str) -> list[dict]:
    """Estrae il primo array JSON utile da una risposta (tollerante)."""
    m = re.search(r"\[[\s\S]*\]", testo or "")
    if not m:
        return []
    try:
        dati = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in dati if isinstance(d, dict)] if isinstance(dati, list) else []


def _fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha1()
    for p in sorted(str(x) for x in paths):
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).name}:{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            h.update(Path(p).name.encode())
    return h.hexdigest()[:16]


# ----------------------------------------------------------------------
# DB layer (responsabilita': solo schema + CRUD minimale)
# ----------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS slide (
    dispensa TEXT NOT NULL,
    n        INTEGER NOT NULL,
    file     TEXT,
    fp       TEXT,
    titolo   TEXT,
    testo    TEXT,
    concetti TEXT,                 -- JSON list[str]
    dubbi    TEXT,                 -- JSON list[str]
    modello  TEXT,
    token    INTEGER DEFAULT 0,
    PRIMARY KEY (dispensa, n)
);
CREATE TABLE IF NOT EXISTS figure (
    dispensa TEXT NOT NULL,
    n        INTEGER NOT NULL,
    idx      INTEGER NOT NULL,
    tipo     TEXT, posizione TEXT, descrizione TEXT,
    PRIMARY KEY (dispensa, n, idx)
);
"""

# Colonne esplicite: mai INSERT ... VALUES senza lista colonne (fragile).
_COLS_SLIDE = ("dispensa, n, file, fp, titolo, testo, concetti, dubbi, "
               "modello, token")
_COLS_FIGURA = "dispensa, n, idx, tipo, posizione, descrizione"


class DbSlide:
    """Database SQLite delle trascrizioni di UN libro (cartella slide_estratte)."""

    def __init__(self, cartella_slide: Path):
        self.path = Path(cartella_slide) / NOME_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.path), timeout=15)
        self._con.executescript(_SCHEMA)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.chiudi()

    # -- letture -------------------------------------------------------
    def gia_analizzate(self, dispensa: str) -> dict[int, str]:
        """{numero_slide: fingerprint} per lo short-circuit sui costi."""
        righe = self._con.execute(
            "SELECT n, fp FROM slide WHERE dispensa=?", (dispensa,)).fetchall()
        return {int(n): (fp or "") for n, fp in righe}

    def leggi(self, dispensa: str) -> list[dict]:
        """Tutte le trascrizioni di una dispensa, ordinate per slide."""
        righe = self._con.execute(
            "SELECT n, file, titolo, testo, concetti, dubbi, modello, token "
            "FROM slide WHERE dispensa=? ORDER BY n", (dispensa,)).fetchall()
        out: list[dict] = []
        for n, file, titolo, testo, concetti, dubbi, modello, token in righe:
            figs = self._con.execute(
                "SELECT tipo, posizione, descrizione FROM figure "
                "WHERE dispensa=? AND n=? ORDER BY idx", (dispensa, n)
            ).fetchall()
            out.append({
                "slide": n, "file": file, "titolo": titolo, "testo": testo,
                "concetti": json.loads(concetti or "[]"),
                "dubbi": json.loads(dubbi or "[]"),
                "modello": modello, "token": token,
                "figure": [{"tipo": t, "posizione": p, "descrizione": d}
                           for t, p, d in figs],
            })
        return out

    # -- scritture -----------------------------------------------------
    def salva_scheda(self, dispensa: str, scheda: dict, *, file: str,
                     fp: str = "", modello: str = "", token: int = 0) -> None:
        n = int(schededa_num(scheda))
        if not fp and self._con.execute(
                "SELECT 1 FROM slide WHERE dispensa=? AND n=? AND fp<>''",
                (dispensa, n)).fetchone():
            return          # non schiacciare una trascrizione reale col sync
        self._con.execute(
            f"INSERT OR REPLACE INTO slide ({_COLS_SLIDE}) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (dispensa, n, file, fp,
             str(scheda.get("titolo") or "").strip(),
             str(scheda.get("testo") or "").strip(),
             json.dumps([str(c) for c in scheda.get("concetti") or []],
                        ensure_ascii=False),
             json.dumps([str(d) for d in scheda.get("dubbi") or []],
                        ensure_ascii=False),
             modello, token))
        self._con.execute(
            "DELETE FROM figure WHERE dispensa=? AND n=?", (dispensa, n))
        for i, f in enumerate(scheda.get("figure") or []):
            if not isinstance(f, dict):
                continue
            self._con.execute(
                f"INSERT OR REPLACE INTO figure ({_COLS_FIGURA}) "
                "VALUES (?,?,?,?,?,?)",
                (dispensa, n, i, str(f.get("tipo") or ""),
                 str(f.get("posizione") or ""),
                 str(f.get("descrizione") or "")))
        self._con.commit()

    def chiudi(self):
        try:
            self._con.close()
        except Exception:
            pass


def schededa_num(scheda: dict) -> int:
    """Numero di slide dalla scheda (tollerante: 'L1_S003', 3, '3')."""
    raw = scheda.get("slide")
    cifre = re.sub(r"\D", "", str(raw if raw is not None else ""))
    return int(cifre) if cifre else 0


def schede_per_partizione(trascrizioni: list[dict],
                          id_lezione: str = "L1") -> list[dict]:
    """Traduce le righe del DB nel formato-tabelle del pianificatore.

    Vantaggio economico dichiarato nel flusso: la partizione in paragrafi
    legge SOLO testo gia' pagato (titolo+testo+concetti), mai immagini:
    una slide trascritta una volta con il modello potente non viene piu'
    rianalizzata nei passaggi successivi.
    """
    out: list[dict] = []
    for t in trascrizioni:
        figure = "; ".join(f"{f.get('tipo','figura')} {f.get('posizione','')}".strip()
                           for f in (t.get("figure") or [])[:6])
        punti = [str(c) for c in (t.get("concetti") or [])][:8]
        if figure:
            punti.append(f"figure: {figure}")
        corpo = " ".join(filter(None, [str(t.get("titolo") or ""),
                                       str(t.get("testo") or "")[:900]]))
        out.append({"slide": int(t.get("slide") or 0),
                    "id_lezione": id_lezione,
                    "titolo": str(t.get("titolo") or "").strip(),
                    "punti": punti,
                    "centralita": t.get("centralita"),
                    "_corpo": corpo})
    return out


# ----------------------------------------------------------------------
# Trascrizione massiva (worker side: chiamare fuori dal thread UI)
# ----------------------------------------------------------------------

@dataclass
class EsitoTrascrizione:
    ok: bool = False
    nuove: int = 0
    in_cache: int = 0
    token_spesi: int = 0
    modelli_usati: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)


def _chunk(lista: list, n: int) -> list[list]:
    return [lista[i:i + n] for i in range(0, len(lista), n)]


def trascrivi_dispensa(*, router: Router, provider, libro_dir: Path,
                       dispensa: str, png: list[Path], taglia: int = 3,
                       modello_fissato: str | None = None,
                       max_slide: int | None = None,
                       callback_progresso=None,
                       callback_annullato=None
                       ) -> EsitoTrascrizione:
    """Trascrive slide-per-slide una dispensa nel DB (con cache fingerprint).

    `provider`: `(modello, messaggi, max_tokens) -> (testo, tok, esito)`
    (ProviderComposito.chiama). Usa la classe VISIONE_PESANTE: e' l'unica
    passata costosa del flusso, successiva (scaletta/paragrafi) riusera'
    il testo a costo zero. `callback_progresso(fatto, totale, tok)` e
    `callback_annullato() -> bool` sono opzionali (UI reattiva).
    Ritorna EsitoTrascrizione; scrive solo il DB.
    """
    esito = EsitoTrascrizione()
    if not png:
        esito.errori.append("Nessuna PNG da trascrivere.")
        return esito
    if max_slide:
        png = png[:max_slide]

    cartella = libro_dir / "slide_estratte"
    with DbSlide(cartella) as db:
        fatte = db.gia_analizzate(dispensa)
        candidati = list(modelli_per_classe(VISIONE_PESANTE))
        totale = len(png)
        fatto = 0

        def _progresso():
            if callback_progresso:
                try:
                    callback_progresso(fatto, totale, esito.token_spesi)
                except Exception:
                    pass

        for gruppo in _chunk(png, taglia):
            if callback_annullato and callback_annullato():
                esito.errori.append("Interruzione richiesta dall'utente.")
                break
            nums = [int(re.sub(r"\D", "", p.name) or i + 1)
                    for i, p in enumerate(gruppo)]
            fp = _fingerprint(gruppo)
            if all(fatte.get(n) == fp for n in nums):
                esito.in_cache += len(gruppo)
                fatto += len(gruppo)
                _progresso()
                continue

            parti: list[dict] = [{"type": "text",
                                  "text": ISTRUZIONE_TRASCRIZIONE}]
            for n, path in zip(nums, gruppo):
                parti.append({"type": "text", "text": f"SLIDE NUMERO {n}:"})
                parti.append({"type": "image_ref", "path": str(path)})
            messaggi, _ = costruisci_messaggi(
                "Trascrivi slide accademiche in JSON. Solo output JSON.",
                [], "")
            messaggi.append({"role": "user", "content": parti})

            tok_in = stima_token(json.dumps(parti, ensure_ascii=False)) \
                + sum(700 for _ in gruppo)
            modello, _ = scegli_strategico(
                router, candidati, classe=VISIONE_PESANTE, token_input=tok_in,
                token_output_stimato=2_500, richiede_vision=True,
                modello_fissato=modello_fissato)
            if modello is None:
                esito.errori.append(
                    "Nessun modello vision disponibile oggi: riprova dopo "
                    "il rinnovo delle quote (le slide gia' trascritte restano "
                    "nel DB).")
                return esito
            esito.modelli_usati.append(modello.id)

            testo, tok, ris = provider(modello, messaggi,
                                       min(modello.max_output, 4_000))
            if ris == OK and "[[TRONCATO]]" in testo:
                extra = 0
                testo, extra = continua_se_troncato(provider, modello,
                                                    messaggi, testo)
                tok += extra
            router.registra_esito(modello, ris, tok)
            esito.token_spesi += tok
            if ris != OK:
                if ris == QUOTA_ESAURITA:
                    continue      # switch automatico: prossimo chunk/modello
                esito.errori.append(f"Esito {ris} su {modello.id}")
                continue

            schede = _array_json(testo.replace("[[TRONCATO]]", ""))
            if len(schede) < len(gruppo):
                esito.errori.append(
                    f"Batch {gruppo[0].name}: attese {len(gruppo)} schede, "
                    f"ricevute {len(schede)}")
            for i, path in enumerate(gruppo):
                scheda = schede[i] if i < len(schede) else {}
                scheda.setdefault("slide", nums[i])
                db.salva_scheda(dispensa, scheda, file=path.name, fp=fp,
                                modello=modello.id,
                                token=tok // max(len(gruppo), 1))
                esito.nuove += 1
            fatto += len(gruppo)
            _progresso()

        esito.ok = bool(esito.nuove or esito.in_cache)
    return esito
