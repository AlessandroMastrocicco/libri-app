# -*- coding: utf-8 -*-
"""
contesto.py - Memoria e costruzione del contesto per i task AI (bozza).

Fonti di contesto riusate dall'esistente:
  * slide estratte: libri/<slug>/slide_estratte/<dispensa>/pagina_XXX.png
    con mappatura lezioni in _mappatura_lezioni.json;
  * paragrafi esistenti: AST + docstring per il digest locale;
  * mappature figure: capitolo_XX/immagini/_mappatura_slide.json.

Il digest viene generato LOCALMENTE quando possibile (euristica sulle
P() del modulo) e solo opzionalmente da un modello (classe SCRITTURA
leggera) per qualita' migliore. In questo modo la memoria non costa quota.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from app.core.ai.tokeni import BloccoContesto, stima_token


# ======================================================================
# Slide -> schede strutturate (output della fase di visione, cache su disco)
# ======================================================================

def path_cache_schede(libro_dir: Path) -> Path:
    return libro_dir / "slide_estratte" / "_ai_schede_slide.json"


def carica_schede(libro_dir: Path) -> dict | None:
    p = path_cache_schede(libro_dir)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def salva_schede(libro_dir: Path, schede: dict) -> None:
    """schede: {id_lezione: [{slide, titolo, punti: [..], figure: [..]}]}

    Dopo la scrittura della cache JSON sincronizza anche il DB slide
    (trascrizione.py), cosi' il testo delle trascrizioni AI e' consultabile
    in SQL e le due rappresentazioni restano allineate. Costo: 0 token.
    """
    p = path_cache_schede(libro_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(schede, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(p)
    try:                                   # best-effort, mai bloccante
        from app.core.ai.trascrizione import DbSlide
        dispensa = str(schede.get("_dispensa") or "L1")
        with DbSlide(p.parent) as db:
            for id_lez, elenco in schede.items():
                if id_lez.startswith("_") or not isinstance(elenco, list):
                    continue
                for s in elenco:
                    if not isinstance(s, dict) or not s.get("slide"):
                        continue
                    figure = [{"tipo": str(f)[:40], "posizione": "",
                               "descrizione": str(f)}
                              for f in (s.get("figure") or [])
                              if isinstance(f, str)]
                    db.salva_scheda(dispensa, {
                        "slide": s.get("slide"), "titolo": s.get("titolo"),
                        "testo": "\n".join(str(p_) for p_ in
                                           (s.get("punti") or [])),
                        "concetti": s.get("punti") or [],
                        "dubbi": s.get("dubbi") or [],
                        "centralita": s.get("centralita"),
                        "figure": figure},
                        file=str(s.get("file") or ""), fp="",
                        modello=str(s.get("modello") or "cache-json"),
                        token=int(s.get("token") or 0))
    except Exception:
        pass


def schede_pertinenti(schede: dict, parole_chiave: list[str],
                      max_schede: int = 8) -> list[dict]:
    """Selezione economica: solo le schede slide che toccano l'argomento,
    invece di tutte le slide del capitolo nel prompt del writer."""
    if not isinstance(schede, dict):
        return []
    chiavi = [k.lower() for k in parole_chiave if k]
    punteggi: list[tuple[float, dict]] = []
    for id_lez, elenco in schede.items():
        for scheda in elenco:
            testo = json.dumps(scheda, ensure_ascii=False).lower()
            punteggio = sum(1 for k in chiavi if k and k in testo)
            # bonus lieve per vicinanza numerica alla lezione corrente
            punteggi.append((punteggio, {"id_lezione": id_lez, **scheda}))
    punteggi.sort(key=lambda x: -x[0])
    return [s for _, s in punteggi[:max_schede]]


# ======================================================================
# Digest dei paragrafi (memoria locale, zero quota)
# ======================================================================

def digest_paragrafo_locale(contenuto: str) -> dict:
    """Riassunto strutturale estratto via AST, senza chiamare nessun modello:
    titolo, prime frasi delle P(), figure citate. Serve come memoria a costo
    zero; potra' essere raffinato dal modello solo se la qualita' non basta."""
    out = {"titolo": "", "concetti": [], "figure": [], "token_stimati": 0}
    try:
        tree = ast.parse(contenuto)
    except SyntaxError:
        return out
    doc = ast.get_docstring(tree)
    if doc:
        for riga in doc.splitlines():
            if riga.strip():
                out["titolo"] = riga.strip()
                break
    for node in ast.walk(tree):
        # chiamate P("...") / definizione("...") -> concetti
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
           and node.args and isinstance(node.args[0], ast.Constant) \
           and isinstance(node.args[0].value, str):
            fn = node.func.id
            if fn in ("P", "definizione", "regola", "esempio"):
                frase = re.split(r"(?<=[.!?])\s+", node.args[0].value.strip())
                inizio = frase[0][:220] if frase else ""
                if inizio:
                    out["concetti"].append(inizio)
        # figura("L1_S003_x.png")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
           and node.func.id == "figura" and node.args \
           and isinstance(node.args[0], ast.Constant):
            out["figure"].append(str(node.args[0].value))
    out["concetti"] = out["concetti"][:12]
    blob = json.dumps(out, ensure_ascii=False)
    out["token_stimati"] = stima_token(blob)
    return out


def path_digest_capitolo(root: Path, slug: str, cap: int) -> Path:
    return (root / "libri" / slug / "capitoli" / f"capitolo_{cap:02d}"
            / "_ai_digest.json")


def aggiorna_digest(root: Path, slug: str, cap: int, par_id: str,
                    contenuto: str) -> dict:
    p = path_digest_capitolo(root, slug, cap)
    dati: dict = {"versione": 1, "paragrafi": {}}
    if p.is_file():
        try:
            vecchio = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(vecchio.get("paragrafi"), dict):
                dati["paragrafi"] = vecchio["paragrafi"]
        except Exception:
            pass
    dati["paragrafi"][par_id] = digest_paragrafo_locale(contenuto)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dati, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(p)
    return dati


# ======================================================================
# Indice figure globale (anti-duplicazione)
# ======================================================================

def indice_figure(root: Path, slug: str) -> dict[str, dict]:
    """nome_file -> {lezione, slide, capitoli[]} usando i pattern Lx_Sxxx
    dai nomi file e le mappature _mappatura_slide.json esistenti."""
    indice: dict[str, dict] = {}
    base = root / "libri" / slug / "capitoli"
    if not base.is_dir():
        return indice
    from app.core.slide_extract import riferimento_slide_da_nome
    for img in base.glob("capitolo_*/immagini/*.png"):
        rif = riferimento_slide_da_nome(img.name) or {}
        indice.setdefault(img.name, {"lezione": rif.get("id_lezione"),
                                     "slide": rif.get("slide"),
                                     "capitoli": []})
        indice[img.name]["capitoli"].append(img.parent.parent.name)
    return indice


# ======================================================================
# Assemblaggio finale per il writer
# ======================================================================

def blocchi_per_writer(meta_libro: dict, titolo_capitolo: str,
                       titolo_paragrafo: str, schede: list[dict],
                       digest_precedenti: list[dict],
                       ultimo_paragrafo: str | None,
                       budget_tok: int) -> list[BloccoContesto]:
    """Ordina i blocchi per utilita': contratto > obiettivo > slide >
    digest > transizione. Il taglio vero lo fa assembla_contesto()."""
    blocchi = [
        BloccoContesto("meta_libro",
                       f"Libro: {meta_libro.get('soggetto','')} — "
                       f"{meta_libro.get('dominio','')}", priorita=40),
        BloccoContesto("capitolo",
                       f"Capitolo: {titolo_capitolo}", priorita=30),
        BloccoContesto("paragrafo_obiettivo",
                       f"Paragrafo da scrivere: {titolo_paragrafo}",
                       priorita=5, comprimibile=False),
        BloccoContesto("slide", "\n\n".join(
            json.dumps(s, ensure_ascii=False) for s in schede), priorita=10),
        BloccoContesto("digest_precedenti", "\n".join(
            f"- {d.get('titolo','')}: " + "; ".join(d.get("concetti", [])[:3])
            for d in digest_precedenti), priorita=35),
    ]
    if ultimo_paragrafo:
        # sliding window: solo le ultime ~600 token dell'ultimo paragrafo,
        # servono per lo stile della transizione, non per il contenuto.
        coda = ultimo_paragrafo[-2400:]
        blocchi.append(BloccoContesto(
            "transizione", coda, priorita=45))
    return blocchi
