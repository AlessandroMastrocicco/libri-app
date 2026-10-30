# -*- coding: utf-8 -*-
"""
orchestratore.py - Automazione END-TO-END di un capitolo (modalita' assistita).

E' la "regia" che sostituisce il copia/incolla manuale dell'utente:

    slide in cache?  --no--> analisi.analizza_slides   (fase visione)
         |                  (si': costo zero, riuso cache)
    pianificatore.partisci_schede -> titoli bozza
         |
    per ogni paragrafo pianificato:
        contesto.blocchi_per_writer + tokeni.assembla_contesto (budget)
        pipeline.genera_paragrafo_assistito (draft->valida->auto-ripara)
        salvataggio come _bozza + digest memoria (contesto.py)
         |
    report finale con costi e scelte di modello

Ogni responsabilita' resta nel proprio modulo; qui c'e' solo la sequenza.
Le funzioni sono puramente sincrone e testabili con provider stub: la UI le
richiama in un thread separato (vedi app/screens/crea_paragrafo.py).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.ai import contesto as _ctx
from app.core.ai import pianificatore
from app.core.ai.analisi import analizza_slides
from app.core.ai.pipeline import EsitoTask, genera_paragrafo_assistito
from app.core.ai.prompt import ISTRUZIONE_SOLO_CORPO, costruisci_messaggi
from app.core.ai.router import QuotaEsauritaException, Router
from app.core.ai.scelta import scegli_strategico
from app.core.ai.tokeni import assembla_contesto, stima_token_messaggi
from app.core.paragrafo import elenca_paragrafi, leggi_paragrafo


@dataclass
class RapportoCapitolo:
    ok: bool = False
    piano: pianificatore.Piano | None = None
    esiti: list[dict] = field(default_factory=list)   # per paragrafo
    token_totali: int = 0
    modelli_usati: list[str] = field(default_factory=list)
    note: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)


def _digest_precedenti(root: Path, slug: str, cap: int) -> list[dict]:
    p = _ctx.path_digest_capitolo(root, slug, cap)
    if p.is_file():
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            return list((d.get("paragrafi") or {}).values())
        except Exception:
            pass
    return []


def _ultimo_testo(root: Path, slug: str, cap: int, prima_di: str) -> str | None:
    """Ultimo paragrafo esistente (transizione stilistica, sliding window)."""
    ids = [i for i in elenca_paragrafi(root, slug, cap)
           if not i.endswith("_esercizi")]
    if not ids:
        return None
    return leggi_paragrafo(root, slug, cap, ids[-1])


def prepara_piano(*, root: Path, slug: str, cap: int, dispensa: str,
                 id_lezione: str = "L1", router: Router | None = None,
                 provider=None, ri_analizza: bool = False,
                 pesante: bool = False,
                 ) -> tuple[list[list[dict]], list[str]]:
    """Assicura le schede-slide (analisi se serve) e restituisce la partizione.

    Ritorna (blocchi, note). Costo: zero se la cache delle schede esiste gia'.
    """
    note: list[str] = []
    libro_dir = root / "libri" / slug
    schede = _ctx.carica_schede(libro_dir)
    if (not schede or not schede.get(id_lezione)) and provider is not None \
            and router is not None:
        es = analizza_slides(router=router, provider=provider,
                             libro_dir=libro_dir, dispensa=dispensa,
                             id_lezione=id_lezione, pesante=pesante)
        note.append(f"Analisi slide: {es.schede_nuove} nuove, "
                    f"{es.schede_cache} da cache, {es.token_spesi:,} token.")
        note.extend(es.errori)
        schede = _ctx.carica_schede(libro_dir)
    elenco = (schede or {}).get(id_lezione) or []
    if not elenco:
        return [], ["Nessuna scheda slide disponibile: estrarre le PNG "
                    "della dispensa o eseguire l'analisi."]
    blocchi = pianificatore.partisci_schede(
        [{**s, "id_lezione": id_lezione} for s in elenco])
    note.append(f"Piano: {len(blocchi)} paragrafi previsti.")
    return blocchi, note


def genera_capitolo_assistito(*, root: Path, slug: str, cap: int,
                              dispensa: str, id_lezione: str = "L1",
                              router: Router, provider,
                              pattern_completo: str,
                              meta_libro: dict | None = None,
                              titolo_capitolo: str = "",
                              budget_tok: int = 24_000,
                              max_paragrafi: int | None = None,
                              valida_fn,
                              su_progresso=None,
                              modello_fissato: str | None = None,
                              ) -> RapportoCapitolo:
    """Esegue il piano del capitolo dall'inizio alla fine.

    `su_progresso(testo)` e' una callback opzionale per la UI (thread-safe:
    deve solo mettere in coda messaggi). Nessun file di paragrafo viene
    sovrascritto: gli output validi vengono salvati col suffisso `_bozza`
    dalla UI chiamante (regola d'oro: approvazione umana).
    """
    rep = RapportoCapitolo()
    blocchi, note = prepara_piano(root=root, slug=slug, cap=cap,
                                  dispensa=dispensa, id_lezione=id_lezione,
                                  router=router, provider=provider)
    rep.note.extend(note)
    if not blocchi:
        rep.errori.append("Impossibile pianificare il capitolo.")
        return rep
    if max_paragrafi:
        blocchi = blocchi[:max_paragrafi]

    titoli = pianificatore.titoli_bozza(blocchi)
    digest_prev = _digest_precedenti(root, slug, cap)
    tok_digest = sum(d.get("token_stimati", 0) for d in digest_prev)
    rep.piano = pianificatore.stimapiano(blocchi,
                                         digest_precedenti_tok=tok_digest)
    schede_dict = {id_lezione: [s for b in blocchi for s in b]}

    for i, (blocco, titolo) in enumerate(zip(blocchi, titoli), start=1):
        if su_progresso:
            su_progresso(f"[{i}/{len(blocchi)}] {titolo}")
        # ---- CONTESTO AMPio a budget: selezione pertinente + assembler ----
        parole = [str(s.get("titolo") or "") for s in blocco][:6]
        pertinenti = _ctx.schede_pertinenti(schede_dict, parole,
                                            max_schede=len(blocco))
        blocchi_ctx = _ctx.blocchi_per_writer(
            meta_libro or {}, titolo_capitolo, titolo, pertinenti,
            digest_prev, _ultimo_testo(root, slug, cap, prima_di="99"),
            budget_tok)
        selezionati, usati = assembla_contesto(blocchi_ctx, budget_tok)
        testi = [b.testo for b in selezionati if b.testo.strip()]

        esito: EsitoTask = genera_paragrafo_assistito(
            router=router, provider=provider, contesto_blocchi=testi,
            pattern_completo=pattern_completo, titolo_paragrafo=titolo,
            valida_fn=valida_fn, budget_contesto_tok=budget_tok)
        rep.token_totali += esito.token_totali
        rep.modelli_usati.extend(esito.cambi_modello)
        rep.esiti.append({
            "n": i, "titolo": titolo, "ok": esito.ok,
            "contenuto": esito.contenuto, "modello": esito.modello_finale,
            "token": esito.token_totali, "errore": esito.errore,
        })
        if esito.ok:
            digest_prev = digest_prev + [
                _ctx.digest_paragrafo_locale(esito.contenuto or "")]
        else:
            rep.errori.append(f"Paragrafo {i} ({titolo}): {esito.errore}")

    rep.ok = any(e["ok"] for e in rep.esiti)
    return rep


def quota_residua_totale(router: Router, classe: str) -> int:
    """Somma dei token residui stimati per la classe: input per il
    pianificatore quando si vuole un check di fattibilita' globale."""
    from app.core.ai.catalogo import modelli_per_classe
    tot = 0
    for m in modelli_per_classe(classe):
        if m.quota_giorno_token:
            tot += max(m.quota_giorno_token - router._stato(m.id).token, 0)
    return tot
