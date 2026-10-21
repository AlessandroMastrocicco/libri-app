# -*- coding: utf-8 -*-
"""
capitolo.py - Creazione e gestione di un capitolo dentro un libro.
"""

from __future__ import annotations

import ast
import shutil
from datetime import datetime
from pathlib import Path

from app.core.libro import percorso_libro
from app.core.io_sicuro import scrivi_testo


# ======================================================================
# Validazione
# ======================================================================

def numero_valido(n: int) -> tuple[bool, str]:
    if not isinstance(n, int):
        return False, "Il numero del capitolo deve essere un intero."
    if n < 1:
        return False, "Il numero del capitolo deve essere >= 1."
    if n > 999:
        return False, "Il numero del capitolo e' troppo grande (max 999)."
    return True, ""


# ======================================================================
# Percorsi
# ======================================================================

def percorso_capitolo(root: Path, slug: str, n: int) -> Path:
    return (percorso_libro(root, slug) / "capitoli" / f"capitolo_{n:02d}")

def capitolo_esiste(root: Path, slug: str, n: int) -> bool:
    return percorso_capitolo(root, slug, n).is_dir()

def prossimo_numero(root: Path, slug: str) -> int:
    base = percorso_libro(root, slug) / "capitoli"
    if not base.is_dir():
        return 1
    max_n = 0
    for d in base.iterdir():
        if not d.is_dir():
            continue
        nome = d.name
        if not nome.startswith("capitolo_"):
            continue
        try:
            n = int(nome.split("_", 1)[1])
            max_n = max(max_n, n)
        except (ValueError, IndexError):
            continue
    return max_n + 1

def elenca_capitoli(root: Path, slug: str) -> list[int]:
    base = percorso_libro(root, slug) / "capitoli"
    if not base.is_dir():
        return []
    numeri = []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        if not d.name.startswith("capitolo_"):
            continue
        try:
            numeri.append(int(d.name.split("_", 1)[1]))
        except (ValueError, IndexError):
            continue
    return sorted(numeri)


# ======================================================================
# Lettura titolo
# ======================================================================

def leggi_titolo_capitolo(root: Path, slug: str, n: int) -> str:
    cap_py = percorso_capitolo(root, slug, n) / "capitolo.py"
    if not cap_py.is_file():
        return ""
    try:
        sorgente = cap_py.read_text(encoding="utf-8")
        tree = ast.parse(sorgente)
    except Exception:
        return ""

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "_TITOLO":
                try:
                    valore = ast.literal_eval(node.value)
                    if isinstance(valore, str) and valore.strip():
                        return valore.strip()
                except Exception:
                    pass

    doc = ast.get_docstring(tree)
    if doc:
        for riga in doc.splitlines():
            r = riga.strip()
            if r:
                if " - " in r:
                    return r.split(" - ", 1)[1].strip()
                return r
    return ""


def trova_capitolo_con_titolo(root: Path, slug: str, titolo: str,
                              ignora_numero: int | None = None) -> int | None:
    chiave = (titolo or "").strip().lower()
    if not chiave:
        return None
    for n in elenca_capitoli(root, slug):
        if ignora_numero is not None and n == ignora_numero:
            continue
        titolo_esistente = leggi_titolo_capitolo(root, slug, n)
        if titolo_esistente.strip().lower() == chiave:
            return n
    return None


# ======================================================================
# Contenuto di capitolo.py
# ======================================================================

def _contenuto_capitolo(n: int, titolo: str) -> str:
    titolo = " ".join((titolo or "").split()) or f"Capitolo {n}"
    oggi = datetime.now().strftime("%Y-%m-%d")
    titolo_doc = titolo.replace("\\", "\\\\").replace('"', '\\"')

    return (
        '"""\n'
        f'capitolo_{n:02d}.py - {titolo_doc}\n'
        f'Creato il {oggi}.\n'
        '"""\n'
        "from __future__ import annotations\n"
        "\n"
        "import importlib\n"
        "import traceback\n"
        "from pathlib import Path\n"
        "\n"
        "from motore.stili import STILI\n"
        "from motore.componenti import P\n"
        "from xml.sax.saxutils import escape\n"
        "\n"
        "\n"
        f'_TITOLO = {titolo!r}\n'
        f'_NUMERO = {n}\n'
        "\n"
        "\n"
        "class Capitolo:\n"
        "    def story(self):\n"
        "        flowables = [\n"
        '            P(f"{_NUMERO:02d} {escape(_TITOLO)}", STILI["Capitolo"]),\n'
        "        ]\n"
        "\n"
        "        cartella_par = Path(__file__).parent / \"paragrafi\"\n"
        "        if not cartella_par.is_dir():\n"
        "            return flowables\n"
        "\n"
        "        files = sorted(cartella_par.glob(\"paragrafo_*.py\"))\n"
        "        for f in files:\n"
        "            nome = f.stem\n"
        "            if nome.startswith(\"_\"):\n"
        "                continue\n"
        "            try:\n"
        "                mod = importlib.import_module(\n"
        "                    f\".paragrafi.{nome}\", package=__package__\n"
        "                )\n"
        "                if not hasattr(mod, \"story\"):\n"
        "                    raise AttributeError(\n"
        "                        f\"{nome} non espone una funzione story()\"\n"
        "                    )\n"
        "                flowables += mod.story()\n"
        "            except Exception as e:\n"
        "                tb = traceback.format_exc()\n"
        "                flowables += _placeholder_errore(nome, e, tb)\n"
        "\n"
        "        return flowables\n"
        "\n"
        "\n"
        "def _placeholder_errore(nome_par, eccezione, tb):\n"
        "    from reportlab.lib.colors import HexColor\n"
        "    from reportlab.lib.styles import ParagraphStyle\n"
        "    from reportlab.lib.units import cm\n"
        "    from reportlab.platypus import (\n"
        "        Paragraph, Spacer, Table, TableStyle,\n"
        "    )\n"
        "    from motore.fonts import nome_font\n"
        "    from xml.sax.saxutils import escape\n"
        "\n"
        "    stile = ParagraphStyle(\n"
        "        name=\"ErroreParagrafo\",\n"
        "        fontName=nome_font(\"LibroMono\"), fontSize=8.5, leading=11,\n"
        "        textColor=HexColor(\"#7B241C\"),\n"
        "    )\n"
        "    testo = (\n"
        "        f\"<b>Errore in {escape(nome_par)}</b><br/>\"\n"
        "        f\"{escape(str(eccezione))}<br/><br/>\"\n"
        "        f'<font size=\"7\" color=\"#888888\">{escape(tb[:400])}</font>'\n"
        "    )\n"
        "    par = Paragraph(testo, stile)\n"
        "    tab = Table([[par]], colWidths=[17 * cm])\n"
        "    tab.setStyle(TableStyle([\n"
        "        (\"BACKGROUND\", (0, 0), (-1, -1), HexColor(\"#FDECEA\")),\n"
        "        (\"BOX\", (0, 0), (-1, -1), 0.8, HexColor(\"#C0392B\")),\n"
        "        (\"LEFTPADDING\", (0, 0), (-1, -1), 10),\n"
        "        (\"RIGHTPADDING\", (0, 0), (-1, -1), 10),\n"
        "        (\"TOPPADDING\", (0, 0), (-1, -1), 8),\n"
        "        (\"BOTTOMPADDING\", (0, 0), (-1, -1), 8),\n"
        "    ]))\n"
        "    return [Spacer(1, 4), tab, Spacer(1, 6)]\n"
    )


def _contenuto_init_paragrafi() -> str:
    return '"""Pacchetto dei paragrafi del capitolo."""\n'


def _contenuto_init_capitolo() -> str:
    return '"""Pacchetto del capitolo."""\n'


# ======================================================================
# Creazione capitolo
# ======================================================================

def crea_capitolo(root: Path, slug: str, n: int, titolo: str = "",
                  sovrascrivi: bool = False) -> dict:
    risultato = {
        "ok": False,
        "path": None,
        "creati": [],
        "errori": [],
    }

    ok, motivo = numero_valido(n)
    if not ok:
        risultato["errori"].append(motivo)
        return risultato

    libro_dir = percorso_libro(root, slug)
    if not libro_dir.is_dir():
        risultato["errori"].append(f"Il libro '{slug}' non esiste in libri/.")
        return risultato

    cap_dir = percorso_capitolo(root, slug, n)

    if cap_dir.exists() and not sovrascrivi:
        risultato["errori"].append(f"Il capitolo esiste gia': {cap_dir}")
        return risultato

    try:
        cap_dir.mkdir(parents=True, exist_ok=True)
        risultato["creati"].append(str(cap_dir.relative_to(root)))
    except Exception as e:
        risultato["errori"].append(f"Errore creando {cap_dir}: {e}")
        return risultato

    init_cap = cap_dir / "__init__.py"
    if not init_cap.exists() or sovrascrivi:
        try:
            scrivi_testo(init_cap, _contenuto_init_capitolo())
            risultato["creati"].append(str(init_cap.relative_to(root)))
        except Exception as e:
            risultato["errori"].append(f"Errore scrivendo {init_cap.name}: {e}")

    par_dir = cap_dir / "paragrafi"
    try:
        par_dir.mkdir(exist_ok=True)
        risultato["creati"].append(str(par_dir.relative_to(root)))
    except Exception as e:
        risultato["errori"].append(f"Errore creando {par_dir}: {e}")

    init_par = par_dir / "__init__.py"
    if not init_par.exists() or sovrascrivi:
        try:
            scrivi_testo(init_par, _contenuto_init_paragrafi())
            risultato["creati"].append(str(init_par.relative_to(root)))
        except Exception as e:
            risultato["errori"].append(f"Errore scrivendo {init_par.name}: {e}")

    cap_py = cap_dir / "capitolo.py"
    if not cap_py.exists() or sovrascrivi:
        try:
            scrivi_testo(cap_py, _contenuto_capitolo(n, titolo))
            risultato["creati"].append(str(cap_py.relative_to(root)))
        except Exception as e:
            risultato["errori"].append(f"Errore scrivendo capitolo.py: {e}")

    risultato["path"] = cap_dir
    risultato["ok"] = len(risultato["errori"]) == 0
    return risultato


# ======================================================================
# Eliminazione capitolo
# ======================================================================

def informazioni_eliminazione_capitolo(root: Path, slug: str, n: int) -> dict:
    cap_dir = percorso_capitolo(root, slug, n)

    info = {
        "esiste": cap_dir.is_dir(),
        "path": cap_dir if cap_dir.is_dir() else None,
        "n_paragrafi": 0,
        "dimensione_byte": 0,
    }
    if not info["esiste"]:
        return info

    par_dir = cap_dir / "paragrafi"
    if par_dir.is_dir():
        info["n_paragrafi"] = sum(1 for f in par_dir.glob("paragrafo_*.py"))

    totale = 0
    try:
        for p in cap_dir.rglob("*"):
            if p.is_file():
                try:
                    totale += p.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    info["dimensione_byte"] = totale
    return info


def elimina_capitolo(root: Path, slug: str, n: int) -> dict:
    risultato = {
        "ok": False,
        "path": None,
        "errori": [],
    }

    ok, motivo = numero_valido(n)
    if not ok:
        risultato["errori"].append(motivo)
        return risultato

    cap_dir = percorso_capitolo(root, slug, n)

    if not cap_dir.is_dir():
        risultato["errori"].append(f"Il capitolo {n:02d} non esiste in libri/{slug}/capitoli/.")
        return risultato

    base_libri = (Path(root) / "libri").resolve()
    try:
        cap_dir.resolve().relative_to(base_libri)
    except Exception:
        risultato["errori"].append("Percorso non valido: il capitolo non e' dentro libri/.")
        return risultato

    try:
        shutil.rmtree(cap_dir)
        risultato["path"] = cap_dir
        risultato["ok"] = True
    except Exception as e:
        risultato["errori"].append(f"Errore eliminando {cap_dir}: {e}")

    return risultato