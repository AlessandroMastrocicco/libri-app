# -*- coding: utf-8 -*-
"""
analisi.py - Automazione della FASE 1: analisi delle slide con AI vision.

E' il sostituto automatico del "copia le regole e incollale in chat":
prende le PNG estratte dal PDF della dispensa, le manda a un modello di
VISIONE (classe VISIONE_LEGGERA, escalation a PESANTE su richiesta) e
produce le SCHEDE-SLIDE strutturate che tutta l'infrastruttura riusa:

    {id_lezione: [{slide, titolo, punti[], figure[]}, ...]}

Token-ottimizzazioni applicate (documentate anche in docs/):
  * batch multi-immagine per singola chiamata (1 system prompt pagato N volte
    -> 1 volta ogni `taglia` slide);
  * compressione immagini (visione.py: resize+JPEG+cache): payload dimezzato;
  * cache su disco con fingerprint dei file: slide gia' analizzate costano 0;
  * troncamento controllato: se la risposta si taglia, si riparte dalla coda
    (pipeline.continua_se_troncato) invece di rigenerare tutto;
  * scelta strategica: Gemini preferito per la visione, pin utente rispettato
    solo se idoneo (scelta.py).

Nessuna scrittura fuori dalla cache `_ai_schede_slide.json`: il resto della
pipeline (pianificatore/scrittura) legge solo da li'.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.ai.catalogo import VISIONE_LEGGERA, VISIONE_PESANTE
from app.core.ai.contesto import carica_schede, salva_schede
from app.core.ai.pipeline import continua_se_troncato
from app.core.ai.prompt import costruisci_messaggi
from app.core.ai.router import OK, QUOTA_ESAURITA, Router
from app.core.ai.scelta import scegli_strategico
from app.core.ai.tokeni import stima_token
from app.core.slide_extract import cartella_estrazione

# ----------------------------------------------------------------------
# Prompt di analisi (statico => cache-friendly per i provider compatibili)
# ----------------------------------------------------------------------

ISTRUZIONE_ANALISI = (
    "Sei un indicizzatore di dispense universitarie. Per OGNI immagine "
    "ricevuta (una slide) produci una scheda JSON. Rispondi SOLO con un "
    "array JSON valido, senza markdown ne' commenti. Formato:\n"
    '[{"slide": <numero>, "titolo": "...", "punti": ["...", '
    '"..."], "figure": ["descrizione breve diagramma"]}, ...]\n'
    "Regole: un array elemento per immagine, nello stesso ordine; massimo "
    "6 punti per slide, ciascuno <= 20 parole; non inventare contenuti; "
    "`slide` = numero indicato nel testo che accompagna le immagini."
)


def _scheda_piu_grande(text: str) -> list[dict]:
    """Estrae il primo array JSON utile da una risposta (tollerante)."""
    m = re.search(r"\[[\s\S]*\]", text or "")
    if not m:
        return []
    try:
        dati = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return [d for d in dati if isinstance(d, dict)] if isinstance(dati, list) else []


@dataclass
class EsitoAnalisi:
    ok: bool = False
    schede_nuove: int = 0
    schede_cache: int = 0
    token_spesi: int = 0
    modelli_usati: list[str] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)


def _fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha1()
    for p in sorted(str(x) for x in paths):
        try:
            st = Path(p).stat()
            h.update(f"{Path(p).name}:{st.st_size}:{int(st.st_mtime)}".encode())
        except OSError:
            h.update(Path(p).name.encode())
    return h.hexdigest()[:16]


def _meta_path(libro_dir: Path) -> Path:
    return libro_dir / "slide_estratte" / "_ai_schede_meta.json"


def _leggi_meta(libro_dir: Path) -> dict:
    p = _meta_path(libro_dir)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"versione": 1, "batch": {}, "singole": {}}


def _salva_meta(libro_dir: Path, meta: dict) -> None:
    p = _meta_path(libro_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def _chunk(lista: list, n: int) -> list[list]:
    return [lista[i:i + n] for i in range(0, len(lista), n)]


def analizza_slides(*, router: Router, provider, libro_dir: Path,
                    dispensa: str, id_lezione: str = "L1",
                    taglia: int = 4, pesante: bool = False,
                    budget_tok: int = 30_000,
                    modello_fissato: str | None = None) -> EsitoAnalisi:
    """Analizza TUTTE le slide estratte di una dispensa (con cache).

    `provider`: funzione `(modello, messaggi, max_tokens) -> (testo, tok,
    esito)` (di solito ProviderComposito.chiama). `taglia`: slide per
    chiamata; `pesante`: usa la classe VISIONE_PESANTE (diagrammi/formule).
    Ritorna EsitoAnalisi; scrive SOLO la cache schede.
    """
    esito = EsitoAnalisi()
    # la cartella di estrazione vive sotto libri/<slug>/slide_estratte/<dispensa>
    root = libro_dir.parent.parent if libro_dir.parent.name == "libri" \
        else Path(".")
    try:
        cartella = cartella_estrazione(root, libro_dir.name, dispensa)
    except Exception:
        cartella = libro_dir / "slide_estratte" / dispensa
    png = sorted(set(list(cartella.glob("pagina_*.png"))
                     + list(cartella.glob("*S[0-9][0-9][0-9]*.png"))))
    if not png:
        esito.errori.append(f"Nessuna slide trovata in {cartella}")
        return esito

    vecchie = carica_schede(libro_dir) or {}
    elenco: list[dict] = list(vecchie.get(id_lezione) or [])
    per_slide = {int(s.get("slide") or 0): s for s in elenco}
    meta = _leggi_meta(libro_dir)
    batch_ok = set(meta["batch"].values())
    singole_ok = meta["singole"]

    classe = VISIONE_PESANTE if pesante else VISIONE_LEGGERA
    candidati = router_scegli_candidati(router, classe, modello_fissato)

    for gruppo in _chunk(png, taglia):
        n_iniziale = int(re.sub(r"\D", "", gruppo[0].name) or 1)
        chiavi_batch = _fingerprint(gruppo)
        gia_visto = all((str(i + n_iniziale) in singole_ok)
                        for i in range(len(gruppo)))
        if chiavi_batch in batch_ok or gia_visto:
            esito.schede_cache += len(gruppo)
            continue

        # --- messaggio multimodale: numerazione ESPLICITA per slide ---
        etichette = [{"type": "text",
                      "text": f"SLIDE NUMERO {i + n_iniziale}:"}
                     for i in range(len(gruppo))]
        parti: list[dict] = [{"type": "text", "text": ISTRUZIONE_ANALISI}]
        for etichetta, path in zip(etichette, gruppo):
            parti.append(etichetta)
            parti.append({"type": "image_ref", "path": str(path)})
        messaggi, _k = costruisci_messaggi(
            "Indicizzi slide accademiche in JSON. Solo output JSON.", [], "")
        messaggi.append({"role": "user", "content": parti})

        tok_in = stima_token(json.dumps(parti, ensure_ascii=False)) \
            + sum(700 for _ in gruppo)   # costo immagine tipico
        modello, _punto = scegli_strategico(
            router, candidati, classe=classe, token_input=tok_in,
            token_output_stimato=2_000, richiede_vision=True,
            modello_fissato=modello_fissato)
        if modello is None:
            esito.errori.append("Nessun modello vision disponibile oggi.")
            return esito
        esito.modelli_usati.append(modello.id)

        testo, tok, ris = provider(modello, messaggi, min(modello.max_output,
                                                          3_000))
        if ris == OK and "[[TRONCATO]]" in testo:
            extra_tok = 0
            testo, extra_tok = continua_se_troncato(provider, modello,
                                                    messaggi, testo)
            tok += extra_tok
        router.registra_esito(modello, ris, tok)
        esito.token_spesi += tok
        if ris != OK:
            if ris == QUOTA_ESAURITA:
                continue          # switch automatico: prossimo chunk/prov.
            esito.errori.append(f"Esito {ris} su {modello.id}")
            continue

        schede = _scheda_piu_grande(testo.replace("[[TRONCATO]]", ""))
        if len(schede) < len(gruppo):
            esito.errori.append(
                f"Batch {gruppo[0].name}: attese {len(gruppo)} schede, "
                f"ricevute {len(schede)}")
        for i, path in enumerate(gruppo):
            num = i + n_iniziale
            scheda = schede[i] if i < len(schede) else {}
            scheda.setdefault("slide", num)
            scheda["file"] = path.name
            per_slide[num] = scheda
            esito.schede_nuove += 1
            meta["singole"][str(num)] = _fingerprint([path])
        meta["batch"][chiavi_batch] = True
        _salva_meta(libro_dir, meta)

    elenco = [per_slide[k] for k in sorted(per_slide)]
    vecchie[id_lezione] = elenco
    salva_schede(libro_dir, vecchie)
    esito.ok = bool(esito.schede_nuove or esito.schede_cache)
    return esito


def router_scegli_candidati(router: Router, classe: str,
                            modello_fissato: str | None):
    """Candidati della classe + eventuale modello fissato dall'utente."""
    from app.core.ai.catalogo import modelli_per_classe, trova_modello
    cands = list(modelli_per_classe(classe))
    if modello_fissato:
        m = trova_modello(modello_fissato)
        if m and m.vision and m.id not in [c.id for c in cands]:
            cands.append(m)
    return cands
