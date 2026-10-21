# -*- coding: utf-8 -*-
"""
paragrafo.py - Gestione dei paragrafi dentro un capitolo.
"""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

from app.core.libro import percorso_libro

# ======================================================================
# Costanti di validazione
# ======================================================================

_FUNZIONI_MOTORE = {
    "P", "regola", "definizione", "esempio", "attenzione", "errore",
    "collegamento", "ppt", "dritta", "recap", "separatore", "spazio",
    "codice", "tabella",
}

_STILI_NOTI = {
    "Capitolo", "Paragrafo", "Sottoparagrafo",
    "Testo", "TestoPiccolo",
    "ElencoPuntato", "ElencoNumerato",
    "Codice", "CodiceInline",
    "TitoloSezione",
}

_HELPER_IMMAGINI = ("immagine_locale", "figura", "_figura", "immagine")
_ESTENSIONI_IMMAGINI = (".png", ".jpg", ".jpeg", ".gif", ".bmp")
_FORMATO_PIL = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".gif": "GIF", ".bmp": "BMP"}

# ======================================================================
# Pulizia Markdown
# ======================================================================

def pulisci_codice_markdown(testo: str) -> str:
    """
    Rimuove i blocchi markdown (```python ... ```) che l'utente
    potrebbe aver copiato dalla chat di DeepSeek.
    """
    t = testo.strip()
    if t.startswith("```"):
        righe = t.splitlines()
        if righe and righe[0].startswith("```"):
            righe = righe[1:]
        if righe and righe[-1].strip().startswith("```"):
            righe = righe[:-1]
        t = "\n".join(righe).strip()
    return t

# ======================================================================
# Percorsi
# ======================================================================

def percorso_capitolo_dir(root: Path, slug: str, cap: int) -> Path:
    return percorso_libro(root, slug) / "capitoli" / f"capitolo_{cap:02d}"

def percorso_paragrafi_dir(root: Path, slug: str, cap: int) -> Path:
    return percorso_capitolo_dir(root, slug, cap) / "paragrafi"

def percorso_paragrafo(root: Path, slug: str, cap: int, par_id: str) -> Path:
    return percorso_paragrafi_dir(root, slug, cap) / f"paragrafo_{par_id}.py"

def percorso_immagini_capitolo(root: Path, slug: str, cap: int) -> Path:
    return percorso_capitolo_dir(root, slug, cap) / "immagini"


# ======================================================================
# Info
# ======================================================================

def paragrafo_esiste(root: Path, slug: str, cap: int, par_id: str) -> bool:
    return percorso_paragrafo(root, slug, cap, par_id).is_file()

def elenca_paragrafi(root: Path, slug: str, cap: int) -> list[str]:
    base = percorso_paragrafi_dir(root, slug, cap)
    if not base.is_dir(): return []
    res = []
    for f in base.glob("paragrafo_*.py"):
        if f.name.startswith("_"): continue
        res.append(f.stem.replace("paragrafo_", ""))
        
    def sort_key(pid):
        parts = pid.split("_")
        num = int(parts[0]) if parts[0].isdigit() else 999
        is_ex = 1 if pid.endswith("_esercizi") else 0
        return (num, is_ex)
        
    return sorted(res, key=sort_key)

def prossimo_numero(root: Path, slug: str, cap: int) -> int:
    numeri = elenca_paragrafi(root, slug, cap)
    max_n = 0
    for n in numeri:
        parte_num = n.split("_")[0]
        if parte_num.isdigit():
            max_n = max(max_n, int(parte_num))
    return max_n + 1

def leggi_paragrafo(root: Path, slug: str, cap: int, par_id: str) -> str | None:
    p = percorso_paragrafo(root, slug, cap, par_id)
    if not p.is_file(): return None
    try: return p.read_text(encoding="utf-8")
    except Exception: return None

def titolo_da_sorgente(contenuto: str, fallback: str = "") -> str:
    try:
        tree = ast.parse(contenuto)
    except SyntaxError:
        return fallback
    doc = ast.get_docstring(tree)
    if not doc: return fallback
    for riga in doc.splitlines():
        r = riga.strip()
        if r: return r
    return fallback

def leggi_teoria_origine(contenuto: str, fallback: str = "") -> str:
    try:
        tree = ast.parse(contenuto)
    except SyntaxError:
        return fallback
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_TEORIA_ORIGINE":
                    try:
                        return str(ast.literal_eval(node.value))
                    except Exception:
                        pass
    return fallback


# ======================================================================
# Validazione
# ======================================================================

def _frammento_riga(sorgente: str, riga: int, contesto: int = 2) -> str:
    if not sorgente: return ""
    righe = sorgente.splitlines()
    if not righe or riga < 1 or riga > len(righe): return ""
    inizio = max(0, riga - 1 - contesto)
    fine = min(len(righe), riga + contesto)
    larghezza = len(str(fine))
    out = []
    for i in range(inizio, fine):
        num = i + 1
        prefisso = "> " if num == riga else "  "
        out.append(f"{prefisso}{num:>{larghezza}} | {righe[i]}")
    return "\n".join(out)


def _suggerimento_sintassi(e: SyntaxError) -> str:
    msg = (e.msg or "").lower()
    if "unexpected indent" in msg: return "Riduci o rimuovi l'indentazione della riga."
    if "expected an indented block" in msg: return "Manca l'indentazione del blocco."
    if "unindent does not match" in msg: return "L'indentazione non e' allineata."
    if "unexpected eof" in msg: return "Il file termina prima del previsto."
    if "invalid syntax" in msg: return "Sintassi non valida. Controlla la riga segnalata."
    if "eol while scanning" in msg: return "Stringa non chiusa. Verifica le virgolette."
    return "Correggi la sintassi della riga segnalata."


def _analizza_import(tree: ast.Module) -> tuple[bool, bool, list[str]]:
    ha_stili = False
    ha_componenti = False
    messaggi = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "motore.stili": ha_stili = True
            elif node.module == "motore.componenti": ha_componenti = True
    if not ha_stili: messaggi.append("Import mancante: 'from motore.stili import STILI'")
    if not ha_componenti: messaggi.append("Import mancante: 'from motore.componenti import ...'")
    return ha_stili, ha_componenti, messaggi


def _chiamate_sconosciute(tree: ast.Module) -> list[str]:
    sospette = []
    nomi_ok = {
        "print", "range", "len", "str", "int", "float", "list",
        "dict", "tuple", "set", "bool", "enumerate", "zip", "map",
        "filter", "sorted", "min", "max", "sum", "abs", "round",
        "isinstance", "hasattr", "getattr", "setattr", "type",
        "Spacer", "Paragraph", "PageBreak", "Table", "TableStyle",
        "KeepTogether", "ListFlowable", "ListItem", "Image", "cm",
    }
    nomi_ok.update(_HELPER_IMMAGINI)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            nome = node.func.id
            if nome not in _FUNZIONI_MOTORE and nome not in nomi_ok and not nome.startswith("_"):
                sospette.append(nome)
    return sorted(set(sospette))


def _stili_sconosciuti(tree: ast.Module) -> list[str]:
    sconosciuti = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "STILI":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str) and node.slice.value not in _STILI_NOTI:
                sconosciuti.add(node.slice.value)
    return sorted(sconosciuti)


def _immagini_referenziate(tree: ast.Module) -> list[dict]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _HELPER_IMMAGINI:
            nome = None
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                nome = node.args[0].value
            if nome is None:
                for kw in (node.keywords or []):
                    if kw.arg == "nome_file" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        nome = kw.value.value
            if nome:
                out.append({"nome": nome, "riga": node.lineno})
    return out


def _cartelle_immagini_candidate(root: Path, slug: str, cap: int) -> list[Path]:
    libro_dir = percorso_libro(root, slug)
    cap_dir = percorso_capitolo_dir(root, slug, cap)
    return [cap_dir / "immagini", libro_dir / "immagini", libro_dir / "catture", libro_dir / "slide_estratte"]


def _cerca_immagine(nome_file: str, cartelle: list[Path]) -> Path | None:
    nome = (nome_file or "").strip().replace("\\", "/")
    if not nome: return None
    for base in cartelle:
        if base.is_dir():
            candidato = base / nome
            if candidato.is_file(): return candidato
    return None


def immagini_mancanti(root: Path, slug: str, cap: int, contenuto: str) -> list[dict]:
    ref = estrai_immagini_referenziate(contenuto)
    if not ref: return []
    cartelle = _cartelle_immagini_candidate(root, slug, cap)
    out = []
    for r in ref:
        if _cerca_immagine(r["nome"], cartelle) is None:
            out.append(r)
    return out


def elenca_immagini_disponibili(root: Path, slug: str) -> list[Path]:
    libro_dir = percorso_libro(root, slug)
    estensioni = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}
    out = []
    for nome_cartella in ("immagini", "slide_estratte", "catture"):
        base = libro_dir / nome_cartella
        if base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() and not p.name.startswith("_") and p.suffix.lower() in estensioni:
                    out.append(p)
    out.sort(key=lambda p: str(p).lower())
    return out


def path_atteso_immagine(root: Path, slug: str, cap: int, nome_referenziato: str) -> Path:
    return percorso_immagini_capitolo(root, slug, cap) / nome_referenziato.strip().replace("\\", "/")


def associa_immagine(root: Path, slug: str, cap: int, nome_referenziato: str, path_sorgente: Path) -> dict:
    nome = (nome_referenziato or "").strip().replace("\\", "/")
    if not nome: return {"ok": False, "path": None, "errore": "Nome vuoto."}
    src = Path(path_sorgente)
    if not src.is_file(): return {"ok": False, "path": None, "errore": f"File non trovato: {src}"}
    dest = path_atteso_immagine(root, slug, cap, nome)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.resolve() != dest.resolve() or not dest.is_file():
            shutil.copy2(src, dest)
    except Exception as e:
        return {"ok": False, "path": None, "errore": f"Errore: {e}"}
    return {"ok": True, "path": dest, "errore": None}


def salva_immagine_da_pil(root: Path, slug: str, cap: int, nome_referenziato: str, image_pil) -> dict:
    nome = (nome_referenziato or "").strip().replace("\\", "/")
    if not nome: return {"ok": False, "path": None, "errore": "Nome vuoto."}
    if image_pil is None: return {"ok": False, "path": None, "errore": "Immagine nulla."}
    dest = path_atteso_immagine(root, slug, cap, nome)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        ext = dest.suffix.lower()
        fmt = _FORMATO_PIL.get(ext, "PNG")
        img = image_pil
        if fmt == "JPEG" and img.mode not in ("RGB", "L"): img = img.convert("RGB")
        elif fmt != "JPEG" and img.mode not in ("RGB", "RGBA", "L", "P"): img = img.convert("RGBA")
        img.save(str(dest), fmt)
    except Exception as e:
        return {"ok": False, "path": None, "errore": f"Errore: {e}"}
    return {"ok": True, "path": dest, "errore": None}


def estrai_immagini_referenziate(contenuto: str) -> list[dict]:
    try:
        tree = ast.parse(pulisci_codice_markdown(contenuto))
    except SyntaxError:
        return []
    return _immagini_referenziate(tree)


def _valida_immagini(root: Path, slug: str, cap: int, contenuto: str, risultato: dict) -> None:
    referenziate = estrai_immagini_referenziate(contenuto)
    if not referenziate: return
    cartelle = _cartelle_immagini_candidate(root, slug, cap)
    mancanti, trovate = [], []
    prima_riga = None
    for ref in referenziate:
        if _cerca_immagine(ref["nome"], cartelle) is None:
            mancanti.append(ref["nome"])
            if prima_riga is None: prima_riga = ref["riga"]
        else:
            trovate.append(ref["nome"])
    if mancanti:
        riga = prima_riga or 1
        risultato["tipo_errore"] = "immagine"
        risultato["errore"] = f"Immagini non trovate ({len(mancanti)}): " + ", ".join(f"'{m}'" for m in mancanti) + f" (riga {riga})."
        risultato["dettagli"]["tipo"] = "immagine mancante"
        risultato["dettagli"]["riga"] = riga
        risultato["dettagli"]["frammento"] = _frammento_riga(contenuto, riga)
        risultato["dettagli"]["elementi_mancanti"].extend(f"immagine: {m}" for m in mancanti)
        if trovate: risultato["dettagli"]["elementi_ok"].append(f"{len(trovate)} immagini trovate")
        risultato["dettagli"]["suggerimento"] = f"Verranno copiati in: {percorso_immagini_capitolo(root, slug, cap)}"
        risultato["ok"] = False
    else:
        risultato["dettagli"]["elementi_ok"].append(f"{len(trovate)} immagini referenziate trovate")


def valida_contenuto(contenuto: str, root: Path | None = None, slug: str | None = None, cap: int | None = None) -> dict:
    contenuto = pulisci_codice_markdown(contenuto)
    
    risultato = {
        "ok": False, "tipo_errore": None, "errore": None,
        "dettagli": {"riga": None, "colonna": None, "tipo": None, "frammento": None, "suggerimento": None, "elementi_mancanti": [], "elementi_ok": []},
        "warning": [], "ha_story": False, "ha_metadati": False,
    }
    if not contenuto or not contenuto.strip():
        risultato["tipo_errore"] = "struttura"
        risultato["errore"] = "Il contenuto e' vuoto."
        return risultato
    try:
        tree = ast.parse(contenuto)
    except SyntaxError as e:
        risultato["tipo_errore"] = "sintassi"
        risultato["errore"] = f"Errore di sintassi alla riga {e.lineno}: {e.msg}"
        risultato["dettagli"]["riga"] = e.lineno
        risultato["dettagli"]["colonna"] = e.offset
        risultato["dettagli"]["frammento"] = _frammento_riga(contenuto, e.lineno or 1)
        risultato["dettagli"]["suggerimento"] = _suggerimento_sintassi(e)
        return risultato
    
    risultato["dettagli"]["elementi_ok"].append("sintassi Python valida")

    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "story":
            risultato["ha_story"] = True
            break
    if not risultato["ha_story"]:
        risultato["tipo_errore"] = "struttura"
        risultato["errore"] = "Manca la funzione 'def story():'."
        risultato["dettagli"]["elementi_mancanti"].append("def story()")
        return risultato
    risultato["dettagli"]["elementi_ok"].append("def story() presente")

    ha_stili, ha_comp, msg_imp = _analizza_import(tree)
    if ha_stili: risultato["dettagli"]["elementi_ok"].append("import da motore.stili")
    if ha_comp: risultato["dettagli"]["elementi_ok"].append("import da motore.componenti")
    for m in msg_imp: risultato["warning"].append(m)

    if ha_comp:
        sconosciute = _chiamate_sconosciute(tree)
        if sconosciute: risultato["warning"].append("Chiamate a funzioni non documentate: " + ", ".join(sconosciute))
    if ha_stili:
        stili_sconosciuti = _stili_sconosciuti(tree)
        if stili_sconosciuti: risultato["warning"].append("Chiavi STILI sconosciute: " + ", ".join(repr(x) for x in stili_sconosciuti))

    if root is not None and slug is not None and cap is not None:
        _valida_immagini(root, slug, cap, contenuto, risultato)
        if risultato["tipo_errore"] == "immagine": return risultato

    risultato["ok"] = True
    return risultato


# ======================================================================
# Creazione / Aggiornamento / Eliminazione
# ======================================================================

def crea_paragrafo(root: Path, slug: str, cap: int, par_id: str, contenuto: str, **kwargs) -> dict:
    contenuto = pulisci_codice_markdown(contenuto)
    
    risultato = {"ok": False, "path": None, "warning": [], "errori": [], "validazione": None}
    cap_dir = percorso_capitolo_dir(root, slug, cap)
    if not cap_dir.is_dir():
        risultato["errori"].append(f"Il capitolo {cap:02d} non esiste.")
        return risultato
    path_par = percorso_paragrafo(root, slug, cap, par_id)
    if path_par.exists() and not kwargs.get("sovrascrivi", False):
        risultato["errori"].append(f"Il paragrafo esiste gia': {path_par}")
        return risultato

    val = valida_contenuto(contenuto, root=root, slug=slug, cap=cap)
    risultato["validazione"] = val
    if not val["ok"]:
        risultato["errori"].append(val["errore"] or "Contenuto non valido.")
        return risultato
    risultato["warning"].extend(val["warning"])

    try:
        path_par.parent.mkdir(parents=True, exist_ok=True)
        path_par.write_text(contenuto, encoding="utf-8")
        risultato["path"] = path_par
    except Exception as e:
        risultato["errori"].append(f"Errore scrivendo {path_par}: {e}")
        return risultato
    risultato["ok"] = True
    return risultato


def aggiorna_paragrafo(root: Path, slug: str, cap: int, par_id: str, contenuto: str) -> dict:
    contenuto = pulisci_codice_markdown(contenuto)
    
    risultato = {"ok": False, "path": None, "warning": [], "errori": [], "validazione": None}
    path_par = percorso_paragrafo(root, slug, cap, par_id)
    if not path_par.is_file():
        risultato["errori"].append(f"Paragrafo non trovato: {path_par}")
        return risultato
    val = valida_contenuto(contenuto, root=root, slug=slug, cap=cap)
    risultato["validazione"] = val
    if not val["ok"]:
        risultato["errori"].append(val["errore"] or "Contenuto non valido.")
        return risultato
    risultato["warning"].extend(val["warning"])
    try:
        path_par.write_text(contenuto, encoding="utf-8")
        risultato["path"] = path_par
    except Exception as e:
        risultato["errori"].append(f"Errore scrivendo {path_par}: {e}")
        return risultato
    risultato["ok"] = True
    return risultato


def informazioni_eliminazione_paragrafo(root: Path, slug: str, cap: int, par_id: str) -> dict:
    p = percorso_paragrafo(root, slug, cap, par_id)
    info = {
        "esiste": p.is_file(), "path": p if p.is_file() else None,
        "titolo": f"{cap}.{par_id}", "dimensione_byte": 0,
    }
    if not info["esiste"]: return info
    try: info["dimensione_byte"] = p.stat().st_size
    except Exception: pass
    try:
        sorgente = p.read_text(encoding="utf-8")
        info["titolo"] = titolo_da_sorgente(sorgente, fallback=f"{cap}.{par_id}")
    except Exception: pass
    return info


def elimina_paragrafo(root: Path, slug: str, cap: int, par_id: str, **kwargs) -> dict:
    risultato = {"ok": False, "path_par": None, "errori": []}
    path_par = percorso_paragrafo(root, slug, cap, par_id)
    if not path_par.is_file():
        risultato["errori"].append(f"Paragrafo non trovato: {path_par}")
        return risultato
    try:
        path_par.unlink()
        risultato["path_par"] = path_par
        risultato["ok"] = True
    except Exception as e:
        risultato["errori"].append(f"Errore eliminando {path_par}: {e}")
    return risultato


def riepilogo_paragrafo(root: Path, slug: str, cap: int, par_id: str) -> dict | None:
    contenuto = leggi_paragrafo(root, slug, cap, par_id)
    if contenuto is None: return None
    
    is_ex = par_id.endswith("_esercizi")
    teoria_orig = ""
    if is_ex:
        default_id = par_id.replace("_esercizi", "")
        teoria_orig = leggi_teoria_origine(contenuto, fallback=default_id)
        
    return {
        "id": f"{cap}.{par_id}",
        "titolo": titolo_da_sorgente(contenuto, fallback=f"{cap}.{par_id}"),
        "righe": contenuto.count("\n") + 1,
        "byte": len(contenuto.encode("utf-8")),
        "path": percorso_paragrafo(root, slug, cap, par_id),
        "is_esercizi": is_ex,
        "teoria_origine": teoria_orig,
    }