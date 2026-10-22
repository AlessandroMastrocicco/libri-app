# -*- coding: utf-8 -*-
"""
slide_extract.py - Estrazione di pagine da un PDF come immagini PNG,
piu' gestione delle catture manuali.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

from app.core.io_sicuro import scrivi_testo


# ======================================================================
# Utility
# ======================================================================

def _slug(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]", "", s)
    return s or "senza_nome"


def _id_lezione_valido(valore: str) -> bool:
    return re.fullmatch(r"L[1-9]\d*", valore or "", flags=re.IGNORECASE) is not None


def _id_lezione_da_nome(nome: str) -> str | None:
    match = re.match(
        r"^(?:L|LEZIONE)[ _-]*0*(\d+)(?:$|[_ -])",
        nome or "",
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    numero = int(match.group(1))
    return f"L{numero}" if numero > 0 else None


def _mappa_lezioni(libro_dir: Path, cartelle: list[Path]) -> dict[str, str]:
    path_mappa = libro_dir / "slide_estratte" / "_mappatura_lezioni.json"
    mappa_precedente = {}
    if path_mappa.is_file():
        try:
            dati = json.loads(path_mappa.read_text(encoding="utf-8"))
            if not isinstance(dati, dict):
                raise ValueError("formato JSON non valido")
            valori = dati.get("lezioni", {})
            if isinstance(valori, dict):
                mappa_precedente = {
                    nome: identificatore
                    for nome, identificatore in valori.items()
                    if isinstance(nome, str)
                    and isinstance(identificatore, str)
                    and _id_lezione_valido(identificatore)
                }
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"[slide_extract] Impossibile leggere la mappatura delle lezioni: {e}")

    risultato = {}
    usati = set()

    for cartella in cartelle:
        identificatore = mappa_precedente.get(cartella.name)
        if identificatore and identificatore.upper() not in usati:
            risultato[cartella.name] = identificatore.upper()
            usati.add(identificatore.upper())

    for cartella in cartelle:
        if cartella.name in risultato:
            continue
        identificatore = _id_lezione_da_nome(cartella.name)
        if identificatore and identificatore not in usati:
            risultato[cartella.name] = identificatore
            usati.add(identificatore)

    prossimo = 1
    for cartella in cartelle:
        if cartella.name in risultato:
            continue
        while f"L{prossimo}" in usati:
            prossimo += 1
        risultato[cartella.name] = f"L{prossimo}"
        usati.add(f"L{prossimo}")
        prossimo += 1

    if mappa_precedente != risultato:
        try:
            scrivi_testo(
                path_mappa,
                json.dumps({"versione": 1, "lezioni": risultato},
                           ensure_ascii=False, indent=2),
            )
        except OSError as e:
            print(f"[slide_extract] Impossibile salvare la mappatura delle lezioni: {e}")

    return risultato


def riferimento_slide_da_nome(nome_file: str) -> dict | None:
    match = re.search(
        r"(?<![A-Z0-9])L(\d+)[_-]S(?:LIDE)?[_-]?0*(\d+)(?!\d)",
        Path(nome_file).name,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    lezione, slide = int(match.group(1)), int(match.group(2))
    if lezione < 1 or slide < 1:
        return None
    return {"id_lezione": f"L{lezione}", "slide": slide}


def percorso_mappatura_immagini(root: Path, libro: str, cap: int) -> Path:
    return (
        Path(root) / "libri" / libro / "capitoli"
        / f"capitolo_{cap:02d}" / "immagini" / "_mappatura_slide.json"
    )


def leggi_mappatura_immagine(root: Path, libro: str, cap: int,
                             nome_file: str) -> dict | None:
    path = percorso_mappatura_immagini(root, libro, cap)
    if not path.is_file():
        return None
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[slide_extract] Impossibile leggere la mappatura delle immagini: {e}")
        return None
    immagini = dati.get("immagini", {}) if isinstance(dati, dict) else {}
    mappatura = immagini.get(Path(nome_file).name) if isinstance(immagini, dict) else None
    if not isinstance(mappatura, dict):
        return None
    identificatore = mappatura.get("id_lezione")
    slide = mappatura.get("slide")
    if (not isinstance(identificatore, str)
            or not _id_lezione_valido(identificatore)
            or isinstance(slide, bool)
            or not isinstance(slide, int)
            or slide < 1):
        return None
    return {
        "id_lezione": identificatore.upper(),
        "slide": slide,
        "dispensa": mappatura.get("dispensa", ""),
    }


def salva_mappatura_immagine(root: Path, libro: str, cap: int,
                             nome_file: str, id_lezione: str,
                             dispensa: str, slide: int) -> dict:
    identificatore = (id_lezione or "").upper()
    if not _id_lezione_valido(identificatore):
        return {"ok": False, "errore": "Identificatore lezione non valido."}
    if not isinstance(slide, int) or slide < 1:
        return {"ok": False, "errore": "Numero slide non valido."}
    nome = Path(nome_file).name
    if not nome:
        return {"ok": False, "errore": "Nome immagine non valido."}

    path = percorso_mappatura_immagini(root, libro, cap)
    dati = {"versione": 1, "immagini": {}}
    if path.is_file():
        try:
            dati_letti = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(dati_letti, dict) or not isinstance(dati_letti.get("immagini"), dict):
                return {"ok": False, "errore": "Il file di mappatura delle immagini non è valido."}
            dati = dati_letti
        except (OSError, json.JSONDecodeError) as e:
            return {"ok": False, "errore": f"Impossibile leggere la mappatura delle immagini: {e}"}

    dati["immagini"][nome] = {
        "id_lezione": identificatore,
        "dispensa": dispensa,
        "slide": slide,
    }
    try:
        scrivi_testo(path, json.dumps(dati, ensure_ascii=False, indent=2))
    except OSError as e:
        return {"ok": False, "errore": f"Impossibile salvare la mappatura delle immagini: {e}"}
    return {"ok": True, "path": path}


def _dpi_da_qualita(qualita: str) -> int:
    return {
        "bassa": 96,
        "media": 150,
        "alta": 200,
        "max":   300,
    }.get(qualita, 150)


def estrai_numero_lezione(dispensa: str, fallback: int = 1) -> int:
    m = re.search(r"\d+", dispensa or "")
    if not m:
        return fallback
    try:
        return int(m.group(0))
    except Exception:
        return fallback


def cartella_estrazione(root: Path, libro: str,
                        dispensa: str) -> Path:
    return (Path(root) / "libri" / libro / "slide_estratte"
            / _slug(dispensa))


# ======================================================================
# Estrazione
# ======================================================================

def estrai_pdf(root: Path, pdf: Path, libro: str,
               dispensa: str, qualita: str = "media",
               sovrascrivi: bool = False,
               pagine_selezionate: list[int] | None = None) -> dict:
    """
    Estrae le pagine del PDF come PNG.
    
    `pagine_selezionate`: lista di interi (1-based). Se None o vuota,
    estrae tutte le pagine.
    """
    risultato = {
        "ok": False,
        "cartella": None,
        "pagine": [],
        "n_pagine": 0,
        "dpi": 0,
        "errori": [],
        "avvisi": [],
    }

    pdf = Path(pdf)
    if not pdf.is_file():
        risultato["errori"].append(f"PDF non trovato: {pdf}")
        return risultato

    if pdf.suffix.lower() != ".pdf":
        risultato["errori"].append(f"Il file non e' un PDF: {pdf.name}")
        return risultato

    try:
        import fitz  # PyMuPDF
    except ImportError:
        risultato["errori"].append("PyMuPDF non installato. Esegui: pip install pymupdf")
        return risultato

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        risultato["errori"].append("Pillow non installato. Esegui: pip install pillow")
        return risultato

    cartella = cartella_estrazione(root, libro, dispensa)
    risultato["cartella"] = cartella

    if cartella.exists() and not sovrascrivi:
        esistenti = sorted(cartella.glob("pagina_*.png"))
        if esistenti:
            risultato["errori"].append(
                f"La cartella esiste gia' con {len(esistenti)} pagine:\n"
                f"{cartella}\n\nSpunta «Sovrascrivi se esiste» per rigenerare."
            )
            return risultato

    try:
        cartella.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        risultato["errori"].append(f"Errore creando {cartella}: {e}")
        return risultato

    if sovrascrivi:
        for p in cartella.glob("pagina_*.png"):
            try:
                p.unlink()
            except Exception:
                pass

    dpi = _dpi_da_qualita(qualita)
    risultato["dpi"] = dpi

    try:
        doc = fitz.open(str(pdf))
    except Exception as e:
        risultato["errori"].append(f"Errore aprendo il PDF: {e}")
        return risultato

    mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
    pagine_salvate: list[Path] = []
    
    # Se pagine_selezionate è None o vuota, estrai tutto
    estrai_tutte = not pagine_selezionate
    set_selezionate = set(pagine_selezionate) if pagine_selezionate else set()
    
    # Determina la larghezza del padding per i nomi file (es. pagina_001)
    num_pagine_totali = len(doc)
    larghezza = max(3, len(str(num_pagine_totali)))

    for i, page in enumerate(doc, start=1):
        if not estrai_tutte and i not in set_selezionate:
            continue

        out_path = cartella / f"pagina_{i:0{larghezza}d}.png"
        try:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            pix.save(str(out_path))
            pagine_salvate.append(out_path)
        except Exception as e:
            risultato["avvisi"].append(f"Errore pagina {i}: {e}")

    try:
        doc.close()
    except Exception:
        pass

    risultato["pagine"] = pagine_salvate
    risultato["n_pagine"] = len(pagine_salvate)

    meta = {
        "pdf_originale": str(pdf.resolve()),
        "nome_pdf": pdf.name,
        "libro": libro,
        "dispensa": dispensa,
        "qualita": qualita,
        "dpi": dpi,
        "n_pagine_estratte": len(pagine_salvate),
        "pagine_selezionate": pagine_selezionate,
        "data_estrazione": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        scrivi_testo(
            cartella / "_meta.json",
            json.dumps(meta, ensure_ascii=False, indent=2),
        )
    except Exception:
        pass

    risultato["ok"] = len(pagine_salvate) > 0
    if not risultato["ok"]:
        risultato["errori"].append("Nessuna pagina estratta.")
    return risultato


# ======================================================================
# Elenco estrazioni esistenti
# ======================================================================

def elenca_estratti(root: Path, libro: str) -> list[dict]:
    libro_dir = Path(root) / "libri" / libro
    base = libro_dir / "slide_estratte"
    if not base.is_dir():
        return []

    cartelle = []
    for disp_dir in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if not disp_dir.is_dir() or disp_dir.name.startswith("_"):
            continue
        pagine = sorted(disp_dir.glob("pagina_*.png"))
        if not pagine:
            continue
        cartelle.append(disp_dir)

    mappa_lezioni = _mappa_lezioni(libro_dir, cartelle)
    out = []
    for disp_dir in cartelle:
        pagine = sorted(disp_dir.glob("pagina_*.png"))
        meta_path = disp_dir / "_meta.json"
        data = ""
        if meta_path.is_file():
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
                data = m.get("data_estrazione", "")
            except Exception:
                pass
        out.append({
            "dispensa": disp_dir.name,
            "id_lezione": mappa_lezioni[disp_dir.name],
            "cartella": disp_dir,
            "n_pagine": len(pagine),
            "data": data,
        })
    return out


def carica_pagine(cartella: Path) -> list[Path]:
    return sorted(Path(cartella).glob("pagina_*.png"))


# ======================================================================
# Catture manuali
# ======================================================================

def cartella_catture(root: Path, libro: str, dispensa: str) -> Path:
    return (Path(root) / "libri" / libro / "immagini" / _slug(dispensa))


def elenca_catture(root: Path, libro: str, dispensa: str) -> list[Path]:
    c = cartella_catture(root, libro, dispensa)
    if not c.is_dir():
        return []
    return sorted(
        p for p in c.glob("*.png")
        if not p.name.startswith("_")
    )


def prossimo_numero_cattura(root: Path, libro: str, dispensa: str) -> int:
    c = cartella_catture(root, libro, dispensa)
    if not c.is_dir():
        return 1
    max_n = 0
    for p in c.glob("cattura_*.png"):
        try:
            n = int(p.stem.split("_", 1)[1])
            max_n = max(max_n, n)
        except Exception:
            continue
    return max_n + 1


def salva_cattura_con_nome(root: Path, libro: str, dispensa: str,
                           image_pil, nome: str) -> Path:
    c = cartella_catture(root, libro, dispensa)
    c.mkdir(parents=True, exist_ok=True)

    nome_pulito = _slug(nome)
    if not nome_pulito:
        nome_pulito = "cattura"

    path = c / f"{nome_pulito}.png"
    n = 2
    while path.exists():
        path = c / f"{nome_pulito}_{n}.png"
        n += 1

    try:
        if image_pil.mode not in ("RGB", "RGBA"):
            image_pil = image_pil.convert("RGB")
    except Exception:
        pass

    image_pil.save(str(path), "PNG")
    return path


def salva_cattura(root: Path, libro: str, dispensa: str,
                  image_pil) -> Path:
    c = cartella_catture(root, libro, dispensa)
    c.mkdir(parents=True, exist_ok=True)
    n = prossimo_numero_cattura(root, libro, dispensa)
    path = c / f"cattura_{n:03d}.png"
    try:
        if image_pil.mode not in ("RGB", "RGBA"):
            image_pil = image_pil.convert("RGB")
    except Exception:
        pass
    image_pil.save(str(path), "PNG")
    return path


def conta_catture_libro(root: Path, libro: str) -> int:
    base = Path(root) / "libri" / libro / "immagini"
    if not base.is_dir():
        return 0
    return sum(
        1 for p in base.rglob("*.png")
        if not p.name.startswith("_")
    )


# ======================================================================
# Copia immagine negli appunti (Windows)
# ======================================================================

def copia_immagine_negli_appunti(path_img: Path) -> tuple[bool, str]:
    if not sys.platform.startswith("win"):
        return False, "Copia negli appunti supportata solo su Windows."

    try:
        from io import BytesIO
        from PIL import Image
        import win32clipboard  # type: ignore
    except ImportError as e:
        return False, (
            f"Per copiare immagini negli appunti serve pywin32.\n"
            f"Esegui:  pip install pywin32\n\n"
            f"({e})"
        )

    try:
        img = Image.open(str(path_img))
        if img.mode != "RGB":
            img = img.convert("RGB")

        output = BytesIO()
        img.save(output, "BMP")
        data = output.getvalue()[14:]   # rimuove header BMP
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        return True, "Immagine copiata negli appunti."
    except Exception as e:
        return False, f"Errore copia: {e}"