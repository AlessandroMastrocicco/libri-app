# -*- coding: utf-8 -*-
"""
libro.py - Creazione della struttura di un nuovo libro sul filesystem.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.core.io_sicuro import scrivi_testo


# ======================================================================
# Sottocartelle standard
# ======================================================================

SOTTOCARTELLE = [
    "capitoli",
    "immagini",
    "formule",
    "grafici",
    "diagrammi",
    "uml",
]


# ======================================================================
# Validazione slug
# ======================================================================

_SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")


def slugifica(testo: str) -> str:
    s = (testo or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_]", "", s)
    s = re.sub(r"^[^A-Za-z]+", "", s)
    return s


def slug_valido(slug: str) -> tuple[bool, str]:
    s = (slug or "").strip()
    if not s:
        return False, "Il nome cartella e' obbligatorio."
    if not _SLUG_RE.match(s):
        return False, (
            "Il nome cartella deve iniziare con una lettera e contenere "
            "solo lettere, numeri e underscore (max 64 caratteri)."
        )
    if s.lower() in {"libri", "app", "motore"}:
        return False, f"'{s}' e' un nome riservato."
    return True, ""


# ======================================================================
# Contenuto dei file di config
# ======================================================================

def _contenuto_config_libro(dati: dict) -> str:
    soggetto = dati.get("soggetto", "")
    dominio = dati.get("dominio", "")
    oggi = datetime.now().strftime("%Y-%m-%d")

    return (
        '"""\n'
        '_config.py - Configurazione del libro.\n'
        '"""\n'
        "\n"
        "METADATI = {\n"
        f"    'soggetto': {soggetto!r},\n"
        f"    'dominio': {dominio!r},\n"
        f"    'ultimo_aggiornamento': {oggi!r},\n"
        "}\n"
    )


def _contenuto_config_motore(dati: dict) -> str:
    titolo = dati.get("titolo", "")
    autore = dati.get("autore", "")
    anno = datetime.now().strftime("%Y")

    return (
        '"""\n'
        'config.py - Parametri di presentazione per il motore di render.\n'
        '"""\n'
        "\n"
        f"TITOLO = {titolo!r}\n"
        "SOTTOTITOLO = ''\n"
        f"AUTORE = {autore!r}\n"
        f"ANNO = {anno!r}\n"
        "\n"
        "COLORE_PRIMARIO = '#1f6feb'\n"
        "COLORE_ACCENTO = '#3fa34d'\n"
        "\n"
        "LOGO = None\n"
        "IMMAGINE_COPERTINA = None\n"
    )


# ======================================================================
# Creazione libro
# ======================================================================

def percorso_libro(root: Path, slug: str) -> Path:
    return Path(root) / "libri" / slug


def libro_esiste(root: Path, slug: str) -> bool:
    return percorso_libro(root, slug).is_dir()


def crea_libro(root: Path, dati: dict,
               sovrascrivi: bool = False) -> dict:
    risultato = {
        "ok": False,
        "path": None,
        "creati": [],
        "errori": [],
    }

    slug = (dati.get("slug") or "").strip()
    ok, motivo = slug_valido(slug)
    if not ok:
        risultato["errori"].append(motivo)
        return risultato

    libro_dir = percorso_libro(root, slug)

    if libro_dir.exists() and not sovrascrivi:
        risultato["errori"].append(
            f"La cartella esiste gia': {libro_dir}"
        )
        return risultato

    try:
        libro_dir.mkdir(parents=True, exist_ok=True)
        risultato["creati"].append(str(libro_dir.relative_to(root)))
    except Exception as e:
        risultato["errori"].append(f"Errore creando {libro_dir}: {e}")
        return risultato

    for nome in SOTTOCARTELLE:
        sub = libro_dir / nome
        try:
            sub.mkdir(exist_ok=True)
            risultato["creati"].append(str(sub.relative_to(root)))
        except Exception as e:
            risultato["errori"].append(f"Errore creando {sub}: {e}")

    path_config_libro = libro_dir / "_config.py"
    if not path_config_libro.exists() or sovrascrivi:
        try:
            scrivi_testo(path_config_libro, _contenuto_config_libro(dati))
            risultato["creati"].append(
                str(path_config_libro.relative_to(root))
            )
        except Exception as e:
            risultato["errori"].append(f"Errore scrivendo _config.py: {e}")

    path_config_motore = libro_dir / "config.py"
    if not path_config_motore.exists() or sovrascrivi:
        try:
            scrivi_testo(path_config_motore, _contenuto_config_motore(dati))
            risultato["creati"].append(
                str(path_config_motore.relative_to(root))
            )
        except Exception as e:
            risultato["errori"].append(f"Errore scrivendo config.py: {e}")

    risultato["path"] = libro_dir
    risultato["ok"] = len(risultato["errori"]) == 0
    return risultato


# ======================================================================
# Elenco libri esistenti
# ======================================================================

def elenca_libri(root: Path) -> list[str]:
    base = Path(root) / "libri"
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir()
        and not d.name.startswith("_")
        and not d.name.startswith(".")
    )


# ======================================================================
# Rinomina libro
# ======================================================================

def rinomina_libro(root: Path, slug_old: str, slug_new: str) -> dict:
    import shutil

    risultato = {"ok": False, "path_old": None, "path_new": None, "errori": []}
    slug_old = (slug_old or "").strip()
    slug_new = (slug_new or "").strip()

    ok, motivo = slug_valido(slug_old)
    if not ok:
        risultato["errori"].append(f"Slug attuale non valido: {motivo}")
        return risultato

    ok, motivo = slug_valido(slug_new)
    if not ok:
        risultato["errori"].append(f"Nuovo slug non valido: {motivo}")
        return risultato

    if slug_old == slug_new:
        risultato["errori"].append("Il nuovo nome e' identico a quello attuale.")
        return risultato

    dir_old = percorso_libro(root, slug_old)
    dir_new = percorso_libro(root, slug_new)

    if not dir_old.is_dir():
        risultato["errori"].append(f"Il libro '{slug_old}' non esiste in libri/.")
        return risultato

    if dir_new.exists():
        risultato["errori"].append(f"Esiste gia' un libro con il nome '{slug_new}'.")
        return risultato

    base_libri = (Path(root) / "libri").resolve()
    try:
        dir_old.resolve().relative_to(base_libri)
    except Exception:
        risultato["errori"].append("Percorso attuale non valido (fuori da libri/).")
        return risultato

    try:
        shutil.move(str(dir_old), str(dir_new))
    except Exception as e:
        risultato["errori"].append(f"Errore rinominando: {e}")
        return risultato

    risultato["path_old"] = dir_old
    risultato["path_new"] = dir_new
    risultato["ok"] = True
    return risultato


# ======================================================================
# Eliminazione libro
# ======================================================================

def informazioni_eliminazione(root: Path, slug: str) -> dict:
    from app.core.capitolo import elenca_capitoli

    libro_dir = percorso_libro(root, slug)
    info = {
        "esiste": libro_dir.is_dir(),
        "path": libro_dir if libro_dir.is_dir() else None,
        "n_capitoli": 0,
        "n_paragrafi": 0,
        "dimensione_byte": 0,
    }
    if not info["esiste"]:
        return info

    try:
        info["n_capitoli"] = len(elenca_capitoli(root, slug))
    except Exception:
        pass

    cap_base = libro_dir / "capitoli"
    if cap_base.is_dir():
        for d in cap_base.iterdir():
            if not d.is_dir() or not d.name.startswith("capitolo_"):
                continue
            par_dir = d / "paragrafi"
            if par_dir.is_dir():
                info["n_paragrafi"] += sum(1 for f in par_dir.glob("paragrafo_*.py"))

    totale = 0
    try:
        for p in libro_dir.rglob("*"):
            if p.is_file():
                try:
                    totale += p.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    info["dimensione_byte"] = totale
    return info


def formatta_dimensione(n_byte: int) -> str:
    if n_byte < 1024:
        return f"{n_byte} B"
    if n_byte < 1024 * 1024:
        return f"{n_byte / 1024:.1f} KB"
    if n_byte < 1024 * 1024 * 1024:
        return f"{n_byte / (1024 * 1024):.1f} MB"
    return f"{n_byte / (1024 * 1024 * 1024):.2f} GB"


def elimina_libro(root: Path, slug: str) -> dict:
    import shutil

    risultato = {"ok": False, "path": None, "errori": []}
    slug = (slug or "").strip()
    ok, motivo = slug_valido(slug)
    if not ok:
        risultato["errori"].append(motivo)
        return risultato

    libro_dir = percorso_libro(root, slug)
    if not libro_dir.is_dir():
        risultato["errori"].append(f"Il libro '{slug}' non esiste in libri/.")
        return risultato

    try:
        libro_dir.resolve().relative_to((Path(root) / "libri").resolve())
    except Exception:
        risultato["errori"].append("Percorso non valido: il libro non e' dentro libri/.")
        return risultato

    try:
        shutil.rmtree(libro_dir)
        risultato["path"] = libro_dir
        risultato["ok"] = True
    except Exception as e:
        risultato["errori"].append(f"Errore eliminando {libro_dir}: {e}")

    return risultato


# ======================================================================
# Dashboard: accesso e statistiche
# ======================================================================

_FILE_ACCESSO = "_accesso.json"


def registra_accesso(root: Path, slug: str) -> None:
    import json
    libro_dir = percorso_libro(root, slug)
    if not libro_dir.is_dir():
        return
    try:
        path = libro_dir / _FILE_ACCESSO
        scrivi_testo(
            path,
            json.dumps(
                {"ultimo_accesso": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
                ensure_ascii=False, indent=2
            ),
        )
    except Exception:
        pass


def leggi_ultimo_accesso(root: Path, slug: str) -> datetime | None:
    import json
    path = percorso_libro(root, slug) / _FILE_ACCESSO
    if not path.is_file():
        return None
    try:
        dati = json.loads(path.read_text(encoding="utf-8"))
        s = dati.get("ultimo_accesso", "")
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def informazioni_dashboard(root: Path, slug: str) -> dict:
    libro_dir = percorso_libro(root, slug)
    info = {
        "esiste": libro_dir.is_dir(),
        "n_pagine": 0,
        "n_capitoli": 0,
        "n_paragrafi": 0,
        "ultimo_accesso": leggi_ultimo_accesso(root, slug),
        "dimensione_byte": 0,
        "dimensione_str": "0 B",
        "data_creazione": "",
        "titolo_visualizzato": "",
        "autore": "",
    }
    if not info["esiste"]:
        return info

    try:
        from app.core.capitolo import elenca_capitoli
        from app.core.paragrafo import elenca_paragrafi
        capitoli = elenca_capitoli(root, slug)
        info["n_capitoli"] = len(capitoli)
        for cap in capitoli:
            info["n_paragrafi"] += len(elenca_paragrafi(root, slug, cap))
    except Exception:
        pass

    info["n_pagine"] = info["n_paragrafi"]

    totale = 0
    try:
        for p in libro_dir.rglob("*"):
            if p.is_file():
                try:
                    totale += p.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    info["dimensione_byte"] = totale
    info["dimensione_str"] = formatta_dimensione(totale)

    try:
        import ast
        config_path = libro_dir / "config.py"
        if config_path.is_file():
            tree = ast.parse(config_path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    try:
                        valore = ast.literal_eval(node.value)
                    except Exception:
                        continue
                    if target.id == "TITOLO":
                        info["titolo_visualizzato"] = str(valore)
                    elif target.id == "AUTORE":
                        info["autore"] = str(valore)
    except Exception:
        pass

    try:
        config_libro = libro_dir / "_config.py"
        if config_libro.is_file():
            import ast as _ast
            tree = _ast.parse(config_libro.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (isinstance(target, ast.Name) and target.id == "METADATI"):
                        try:
                            meta = _ast.literal_eval(node.value)
                            info["data_creazione"] = meta.get("ultimo_aggiornamento", "")
                        except Exception:
                            pass
    except Exception:
        pass

    if not info["data_creazione"]:
        try:
            ts = libro_dir.stat().st_ctime
            info["data_creazione"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            pass

    return info