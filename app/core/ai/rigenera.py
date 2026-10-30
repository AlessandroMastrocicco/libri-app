# -*- coding: utf-8 -*-
"""
rigenera.py - Rigenerazione guidata di un paragrafo esistente (logica pura).

Responsabilita' unica: ricostruire i messaggi per il modello a partire da
    1. FONTI   : le slide coinvolte, ricavate dal codice attuale del
                 paragrafo (mappature immagini + pattern Lx_Sxxx nei nomi
                 file e nei blocchi Fonti); se sono gia' schedate si riusa
                 la cache (costo zero), altrimenti si analizzano con la
                 classe VISIONE;
    2. VERSIONE: il testo attuale del paragrafo (contesto ampio: digest dei
                 paragrafi precedenti + coda dell'ultimo, come nel ciclo
                 normale);
    3. LINEE GUIDA: Guida per l'AI-autore + manuale tecnico (blocco statico
                 identico alla prima generazione => prompt cache riutilizzata);
    4. ISTRUZIONI DELL'UTENTE: cosa cambiare (priorita' massima nel task).

Il pipeline draft->valida->auto-ripara di `pipeline.genera_paragrafo_assistito`
viene riusato cosi' com'e': qui si costruisce SOLO il contesto specifico della
rigenerazione. Nessun file toccato: il chiamante UI decide se scrivere.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.ai.analisi import analizza_slides  # noqa: F401 (usato in assicurati_schede)
from app.core.ai.contesto import (blocchi_per_writer, carica_schede)
from app.core.ai.pipeline import EsitoTask, genera_paragrafo_assistito
from app.core.ai.router import Router
from app.core.ai.tokeni import BloccoContesto, assembla_contesto
from app.core.paragrafo import titolo_da_sorgente

# ----------------------------------------------------------------------
# Estrazione delle fonti (slide) dal codice del paragrafo
# ----------------------------------------------------------------------

_RIF_LEZIONE = re.compile(r"L(\d+)[_-]S(?:LIDE)?[_-]?0*(\d+)", re.IGNORECASE)


def estrai_riferimenti_slide(contenuto: str) -> dict[str, set[int]]:
    """id_lezione -> insieme di numeri slide citati nel paragrafo.

    Due fonti di verita', unite: i riferimenti Lx_Syyy nel testo (blocchi
    Fonti / nomi file delle figure) e -- per via della mappatura -- cio' che
    l'utente ha associato alle immagini. Qui bastano i pattern nel codice:
    sono obbligatori per la guida autore (sez. 11.2).
    """
    rif: dict[str, set[int]] = {}
    for m in _RIF_LEZIONE.finditer(contenuto or ""):
        lezione = f"L{int(m.group(1))}"
        rif.setdefault(lezione, set()).add(int(m.group(2)))
    return rif


def percorso_slide(libro_dir: Path, dispensa: str, numero: int) -> Path | None:
    """PNG estratta della slide `numero` nella dispensa indicata."""
    cart = libro_dir / "slide_estratte" / dispensa
    if not cart.is_dir():
        return None
    candidati = sorted(cart.glob(f"pagina_{numero:03d}.png"))
    return candidati[0] if candidati else None


def slide_coinvolte(*, root: Path, slug: str, contenuto: str,
                    dispensa_hint: str | None = None) -> list[tuple[str, int, Path]]:
    """[(id_lezione, n_slide, path_png)] per tutte le slide citate.

    La dispensa viene cercata tra le cartelle di slide_estratte usando
    l'hint (dispensa corrente) e poi per deduzione (una dispensa contiene
    tipicamente una sola lezione Lx).
    """
    libro_dir = root / "libri" / slug
    base = libro_dir / "slide_estratte"
    dispense = []
    if base.is_dir():
        dispense = [p.name for p in sorted(base.iterdir()) if p.is_dir()]
    if dispensa_hint and dispensa_hint in dispense:
        dispense = [dispensa_hint] + [d for d in dispense if d != dispensa_hint]

    out: list[tuple[str, int, Path]] = []
    visti: set[tuple[str, int]] = set()
    for lezione, numeri in sorted(estrai_riferimenti_slide(contenuto).items()):
        for dispensa in dispense:
            # dispensa compatibile? deduci la lezione dai PNG o dal nome
            ok_dispensa = (lezione.lower().replace("l", "lezione")
                           in dispensa.lower() or lezione.lower() in dispensa.lower())
            if not ok_dispensa and len(dispense) > 1:
                continue
            for n in sorted(numeri):
                chiave = (lezione, n)
                if chiave in visti:
                    break
                png = percorso_slide(libro_dir, dispensa, n)
                if png:
                    visti.add(chiave)
                    out.append((lezione, n, png))
    return out


# ----------------------------------------------------------------------
# Schedatura mirata delle sole slide coinvolte (cache-first)
# ----------------------------------------------------------------------

def schede_per_lezione(libro_dir: Path, id_lezione: str) -> list[dict]:
    schede = carica_schede(libro_dir) or {}
    return scheda_ordina(schede.get(id_lezione) or [])


def scheda_ordina(elenco: list[dict]) -> list[dict]:
    def k(s: dict) -> int:
        try:
            return int(str(s.get("slide", 0)).strip().lstrip("SLside").lstrip("Side").lstrip("s") or 0)
        except Exception:
            return 0
    return sorted(elenco, key=k)


def assicurati_schede(*, router: Router, provider, libro_dir: Path,
                      dispensa: str, id_lezione: str,
                      note: list[str]) -> None:
    """Se la cache non ha ancora le schede della lezione, esegui l'analisi
    visione (costo una tantum, poi riuso). Fallendo, si prosegue solo col
    testo del paragrafo: la rigenerazione non si blocca."""
    schede = carica_schede(libro_dir) or {}
    if schede.get(id_lezione):
        return
    try:
        esito = analizza_slides(router=router, provider=provider,
                                libro_dir=libro_dir, dispensa=dispensa,
                                id_lezione=id_lezione)
        if getattr(esito, "schede_nuove", 0) or getattr(esito, "schede_cache", 0):
            note.append(
                f"Schedate {getattr(esito, 'schede_nuove', 0)} slide nuove "
                f"della lezione {id_lezione} "
                f"({getattr(esito, 'token_spesi', 0)} token visione).")
    except Exception as e:  # pragma: no cover - rete/quota
        note.append(f"Analisi slide non riuscita ({type(e).__name__}): "
                    "rigenerazione basata solo sul testo attuale.")


# ----------------------------------------------------------------------
# Messaggi specifici della rigenerazione
# ----------------------------------------------------------------------

def blocco_versione_attuale(contenuto: str, max_caratteri: int = 60_000) -> str:
    """Versione attuale del paragrafo, con guardia di troncamento esplicito
    (meglio dichiarare il taglio che imbrogliare il modello)."""
    c = contenuto or ""
    if len(c) > max_caratteri:
        return c[:max_caratteri] + "\n\n[...truncated...]"
    return c


def istruzione_rigenerazione(titolo: str, istruzioni_utente: str) -> str:
    return (
        f"RIGENERAZIONE GUIDATA del paragrafo '{titolo}'.\n"
        "Ti diamo: (a) le SLIDE di origine, (b) la VERSIONE ATTUALE del "
        "paragrafo, (c) le ISTRUZIONI DELL'UTENTE sui cambiamenti voluti.\n"
        "Le istruzioni dell'utente hanno priorita' massima su tutto, MA "
        "senza mai violare la guida autore (fonti in coda ai sottoparagrafi, "
        "nessun riferimento alle slide nel corpo, lunghezza decisa dal "
        "contenuto, confini tra paragrafi).\n"
        "Cosa fare:\n"
        "1. leggi la versione attuale e individua esattamente i punti che "
        "le istruzioni vogliono modificare;\n"
        "2. SALDA di nuovo ogni debito di spiegazione toccato dalla modifica, "
        "consultando le slide originali (non fidarti della memoria);\n"
        "3. conserva tutto cio' che le istruzioni non toccano: stesso filo "
        "logico, stessi rimandi interni, stesse figure;\n"
        "4. aggiornane i blocchi Fonti/Tratto da/Elaborazione dove il "
        "contenuto e' cambiato (slide precise Lx_Syyy);\n"
        "5. produci il paragrafo COMPLETO rigenerato, non un diff.\n\n"
        "ISTRUZIONI DELL'UTENTE:\n" + (istruzioni_utente or "").strip() + "\n\n"
        "Procedi: mini-piano sintetico della modifica, poi il codice."
    )


# ----------------------------------------------------------------------
# Entry point (usato dalla UI in un thread separato)
# ----------------------------------------------------------------------

def rigenera_paragrafo(*, router: Router, provider, root: Path, slug: str,
                       cap: int, par_id: str, contenuto: str,
                       istruzioni_utente: str,
                       pattern_completo: str,
                       dispensa_hint: str | None = None,
                       valida_fn) -> tuple[EsitoTask, list[str]]:
    """Rigenera il paragrafo applicando le istruzioni utente. Ritorna
    (esito, note) — esito.contenuto e' pronto per essere scritto dall'UI
    (che lo salvera' solo dopo validazione umana)."""
    note: list[str] = []
    libro_dir = root / "libri" / slug
    titolo = titolo_da_sorgente(contenuto, fallback=f"{cap}.{par_id}")

    # 1) FONTI: slide coinvolte (dal codice del paragrafo) ------------------
    coinvolte = slide_coinvolte(root=root, slug=slug, contenuto=contenuto,
                                dispensa_hint=dispensa_hint)
    schede_usate: list[dict] = []
    lezioni = sorted({lez for lez, _n, _p in coinvolte})
    if lezioni:
        # schedatura cache-first SOLO delle lezioni citate dal paragrafo
        for lez in lezioni:
            assicurati_schede(router=router, provider=provider,
                              libro_dir=libro_dir,
                              dispensa=(coinvolte[0][2].parent.name),
                              id_lezione=lez, note=note)
        schede = carica_schede(libro_dir) or {}
        for lez, n, _png in coinvolte:
            for s in scheda_ordina(schede.get(lez) or []):
                try:
                    num = int(str(s.get("slide", "")).strip() or -1)
                except Exception:
                    continue
                if num == n:
                    schede_usate.append({"id_lezione": lez, **s})
        note.append(f"Fonti recuperate: {len(coinvolte)} slide, "
                    f"{len(schede_usate)} schede in cache.")
    else:
        note.append("Nessun riferimento Lx_Syyy trovato nel paragrafo: "
                    "rigenerazione basata su testo attuale + istruzioni.")

    # 2) CONTESTO AMPIO: digest precedenti + coda paragrafo vicino ----------
    digest_p = _digest_precedenti_locali(root, slug, cap, escludi=par_id)
    ultimo = _ultimo_testo_locale(root, slug, cap, prima_di=par_id)

    blocchi_ctx = blocchi_per_writer(
        {"soggetto": slug, "dominio": ""}, f"Capitolo {cap}", titolo,
        schede_usate, digest_p, ultimo, budget_tok=24_000)
    # blocco dedicato: la VERSIONE ATTUALE e' il cuore della rigenerazione
    blocchi_ctx.insert(3, BloccoContesto(
        "versione_attuale",
        "VERSIONE ATTUALE DEL PARAGRAFO (da cui partire):\n\n"
        + blocco_versione_attuale(contenuto), priorita=6,
        comprimibile=False))
    selezionati, _usati = assembla_contesto(blocchi_ctx, 24_000)
    testi = [b.testo for b in selezionati if b.testo.strip()]

    # 3+4) pipeline riusato: statico guida+manuale, task = rigenerazione ----
    istruzione = istruzione_rigenerazione(titolo, istruzioni_utente)
    esito = genera_paragrafo_assistito(
        router=router, provider=provider, contesto_blocchi=testi,
        pattern_completo=pattern_completo, titolo_paragrafo=titolo,
        valida_fn=valida_fn, istruzione_task=istruzione)
    return esito, note


# ----------------------------------------------------------------------
# Helper di contesto locale (stessa logica dell'orchestratore, minima)
# ----------------------------------------------------------------------

def _digest_precedenti_locali(root: Path, slug: str, cap: int,
                              escludi: str) -> list[dict]:
    p = (root / "libri" / slug / "capitoli" / f"capitolo_{cap:02d}"
         / "_ai_digest.json")
    if not p.is_file():
        return []
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        paras = d.get("paragrafi") or {}
        return [v for k, v in paras.items() if k != escludi]
    except Exception:
        return []


def _ultimo_testo_locale(root: Path, slug: str, cap: int,
                         prima_di: str) -> str | None:
    """Sliding window: coda del paragrafo che precede quello corrente."""
    from app.core.paragrafo import elenca_paragrafi, leggi_paragrafo
    ids = elenca_paragrafi(root, slug, cap)
    if prima_di in ids:
        i = ids.index(prima_di)
        if i > 0:
            return leggi_paragrafo(root, slug, cap, ids[i - 1])
    return None
