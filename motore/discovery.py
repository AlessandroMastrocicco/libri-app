# -*- coding: utf-8 -*-
"""
motore/discovery.py

Auto-discovery di capitoli e paragrafi.

Regole:
- Un CAPITOLO è una cartella dentro struttura/capitoli/ chiamata "capitolo_XX"
  e deve contenere un file "capitolo.py" con una classe "Capitolo".
- Un PARAGRAFO è un file dentro <capitolo>/paragrafi/ chiamato "paragrafo_XX.py"
  e deve esporre una funzione "story()".

L'ordinamento è numerico (capitolo_2 prima di capitolo_10).
Qualsiasi errore in un singolo file viene isolato con un WARN: il resto
del libro continua a generarsi.
"""
import importlib
import re
import traceback
from pathlib import Path


def _chiave_numerica(nome: str) -> int:
    """Estrae il numero dal nome (es. 'capitolo_03' -> 3) per l'ordinamento."""
    m = re.search(r"(\d+)", nome)
    return int(m.group(1)) if m else 0


def scopri_capitoli(package_name: str, cartella: Path):
    """Importa tutti i moduli <package>.capitolo_XX.capitolo in ordine."""
    capitoli = []
    if not cartella.exists():
        return capitoli

    sottocartelle = sorted(
        [c for c in cartella.iterdir()
         if c.is_dir()
         and c.name.startswith("capitolo_")
         and (c / "capitolo.py").exists()],
        key=lambda p: _chiave_numerica(p.name),
    )

    for sub in sottocartelle:
        nome = sub.name
        try:
            mod = importlib.import_module(f"{package_name}.{nome}.capitolo")
            capitoli.append(mod.Capitolo())
        except Exception as e:
            print(f"[WARN] Capitolo '{nome}' non caricato: {e}")
            traceback.print_exc()

    return capitoli


def scopri_paragrafi(package_name: str, cartella: Path):
    """Importa tutti i moduli <package>.paragrafo_XX in ordine."""
    paragrafi = []
    if not cartella.exists():
        return paragrafi

    files = sorted(
        [f for f in cartella.iterdir()
         if f.is_file()
         and f.name.startswith("paragrafo_")
         and f.suffix == ".py"],
        key=lambda p: _chiave_numerica(p.stem),
    )

    for f in files:
        nome = f.stem
        try:
            mod = importlib.import_module(f"{package_name}.{nome}")
            paragrafi.append(mod)
        except Exception as e:
            print(f"[WARN] Paragrafo '{nome}' non caricato: {e}")
            traceback.print_exc()

    return paragrafi