# -*- coding: utf-8 -*-
"""
motore/fonts.py

Registrazione font Unicode + fix automatico di pedici, apici e simboli
non presenti nei font base di ReportLab.

Copre:
  - Pedici e apici Unicode (D1, V2, Dk, x2)     -> tag <sub>/<super>
  - Simboli matematici (Z R in subsetto freccia) -> font LibroSimboli
  - Simboli tipografici (check, cross, bullet)   -> font LibroSimboli

L'utente scrive i simboli in forma naturale nei paragrafi. La funzione
fix_simboli() e' invocata automaticamente da P(...), codice(...) e dai
riquadri didattici in motore/componenti.py.

NOTA: i caratteri speciali sono scritti come escape \\uXXXX in modo che
il file sia interamente in ASCII e non si corrompa mai per problemi di
encoding quando viene copiato, incollato o salvato con editor diversi.
"""
import sys
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    FONTS_DIR = Path("C:/Windows/Fonts")
else:
    FONTS_DIR = None


_FONTS = [
    ("LibroRegular",    ["arial.ttf"]),
    ("LibroBold",       ["arialbd.ttf"]),
    ("LibroItalic",     ["ariali.ttf"]),
    ("LibroBoldItalic", ["arialbi.ttf"]),
    ("LibroMono",       ["cour.ttf"]),
    ("LibroMonoBold",   ["courbd.ttf"]),
    # Font con copertura estesa di simboli matematici e tipografici.
    # Segoe UI Symbol e' presente su Windows 7+.
    ("LibroSimboli",    ["seguisym.ttf", "segoeui.ttf"]),
]

_FALLBACK = {
    "LibroRegular":    "Helvetica",
    "LibroBold":       "Helvetica-Bold",
    "LibroItalic":     "Helvetica-Oblique",
    "LibroBoldItalic": "Helvetica-BoldOblique",
    "LibroMono":       "Courier",
    "LibroMonoBold":   "Courier-Bold",
    "LibroSimboli":    "Helvetica",
}

_registrati_ok = False
_simboli_disponibili = False
_eseguito = False


def registra_font() -> bool:
    """
    Registra i font una sola volta (idempotente).
    Ritorna True se i font Unicode principali sono stati registrati.
    """
    global _registrati_ok, _simboli_disponibili, _eseguito
    if _eseguito:
        return _registrati_ok
    _eseguito = True

    if FONTS_DIR is None or not FONTS_DIR.exists():
        print("[INFO] Font Unicode non disponibili: uso fallback Helvetica.")
        return False

    registrati = set()
    for nome, candidati in _FONTS:
        for filename in candidati:
            path = FONTS_DIR / filename
            if not path.exists():
                continue
            try:
                pdfmetrics.registerFont(TTFont(nome, str(path)))
                registrati.add(nome)
                break
            except Exception as e:
                print(f"[WARN] Impossibile registrare {nome} da {filename}: {e}")

    # Famiglie (per far funzionare <b> e <i> nei Paragraph)
    if {"LibroRegular", "LibroBold", "LibroItalic", "LibroBoldItalic"} <= registrati:
        registerFontFamily(
            "LibroRegular",
            normal="LibroRegular", bold="LibroBold",
            italic="LibroItalic", boldItalic="LibroBoldItalic",
        )
    if {"LibroMono", "LibroMonoBold"} <= registrati:
        registerFontFamily(
            "LibroMono",
            normal="LibroMono", bold="LibroMonoBold",
            italic="LibroMono", boldItalic="LibroMonoBold",
        )

    _simboli_disponibili = "LibroSimboli" in registrati
    _registrati_ok = {"LibroRegular", "LibroBold", "LibroItalic",
                      "LibroBoldItalic", "LibroMono", "LibroMonoBold"} <= registrati

    if _registrati_ok:
        print("[ok] Font Unicode registrati (Arial + Courier New).")
    else:
        print(f"[WARN] Solo {len(registrati)}/{len(_FONTS)} font registrati.")
    if _simboli_disponibili:
        print("[ok] Font simbolo (Segoe UI Symbol) registrato.")
    else:
        print("[WARN] Font simbolo non trovato: simboli matematici appariranno come quadrati.")

    return _registrati_ok


def nome_font(logico: str) -> str:
    """
    Restituisce il nome del font logico se registrato, altrimenti il fallback.
    Da usare in tutti i fontName degli stili e nelle chiamate canvas.setFont().
    """
    if _registrati_ok:
        return logico
    return _FALLBACK.get(logico, "Helvetica")


# ---------------------------------------------------------------------------
# Mappa pedici/apici Unicode -> tag <sub>/<super> di ReportLab
# ---------------------------------------------------------------------------
# I tag <sub>/<super> funzionano con qualsiasi font (anche Courier New):
# ReportLab riduce il carattere e lo abbassa/alza. Non serve che il font
# contenga il glifo del pedice.
_SUB_MAP = {
    # --- Pedici numerici ---
    "\u2080": ("0", "sub"), "\u2081": ("1", "sub"), "\u2082": ("2", "sub"),
    "\u2083": ("3", "sub"), "\u2084": ("4", "sub"), "\u2085": ("5", "sub"),
    "\u2086": ("6", "sub"), "\u2087": ("7", "sub"), "\u2088": ("8", "sub"),
    "\u2089": ("9", "sub"),
    "\u208A": ("+", "sub"), "\u208B": ("-", "sub"), "\u208C": ("=", "sub"),
    "\u208D": ("(", "sub"), "\u208E": (")", "sub"),
    # --- Pedici alfabetici ---
    "\u2090": ("a", "sub"), "\u2091": ("e", "sub"), "\u2095": ("h", "sub"),
    "\u1D62": ("i", "sub"), "\u2C7C": ("j", "sub"), "\u2096": ("k", "sub"),
    "\u2097": ("l", "sub"), "\u2098": ("m", "sub"), "\u2099": ("n", "sub"),
    "\u2092": ("o", "sub"), "\u209A": ("p", "sub"), "\u1D63": ("r", "sub"),
    "\u209B": ("s", "sub"), "\u209C": ("t", "sub"), "\u1D64": ("u", "sub"),
    "\u1D65": ("v", "sub"), "\u2093": ("x", "sub"),
    # --- Apici numerici ---
    "\u2070": ("0", "super"), "\u00B9": ("1", "super"), "\u00B2": ("2", "super"),
    "\u00B3": ("3", "super"), "\u2074": ("4", "super"), "\u2075": ("5", "super"),
    "\u2076": ("6", "super"), "\u2077": ("7", "super"), "\u2078": ("8", "super"),
    "\u2079": ("9", "super"),
    "\u207A": ("+", "super"), "\u207B": ("-", "super"), "\u207C": ("=", "super"),
    "\u207D": ("(", "super"), "\u207E": (")", "super"),
    "\u207F": ("n", "super"),
}


# ---------------------------------------------------------------------------
# Simboli che NON sono decomponibili e richiedono LibroSimboli
# ---------------------------------------------------------------------------
_SIMBOLI_PROBLEMATICI = set(
    # --- Letterlike Symbols (insiemi numerici) ---
    "\u2124\u211D\u2115\u211A\u2102\u2119\u210D"

    # --- Insiemistica e appartenenza ---
    "\u2286\u2287\u2282\u2283\u2284\u2285\u2229\u222A\u2216"
    "\u2208\u2209\u220B\u220C\u2205"

    # --- Logica ---
    "\u2200\u2203\u2204\u00AC\u2227\u2228"

    # --- Frecce ---
    "\u2192\u2190\u2194\u21D2\u21D0\u21D4\u21A6\u2191\u2193"

    # --- Disuguaglianze e uguaglianze ---
    "\u2260\u2248\u2261\u2262\u2264\u2265\u226A\u226B"

    # --- Operatori matematici ---
    "\u2211\u220F\u222B\u222E\u221A\u221E\u221D\u2295\u2297\u22A5\u22A4\u22A2\u22A8"
    "\u2212"   # MINUS SIGN (segno meno tipografico)

    # --- Greco minuscolo ---
    "\u03B1\u03B2\u03B3\u03B4\u03B5\u03B6\u03B7\u03B8\u03B9\u03BA\u03BB\u03BC"
    "\u03BD\u03BE\u03C0\u03C1\u03C3\u03C4\u03C5\u03C6\u03C7\u03C8\u03C9"

    # --- Greco maiuscolo ---
    "\u0393\u0394\u0398\u039B\u039E\u03A0\u03A3\u03A6\u03A8\u03A9"

    # --- Operatori di join e outer join (bowtie e derivati) ---
    "\u22C8\u22C9\u22CA\u27D5\u27D6\u27D7"

    # --- Dingbats: check, cross, ballot box ---
    "\u2713\u2714\u2717\u2718\u2611\u2612\u2610"

    # --- Stelle e decorazioni ---
    "\u2605\u2606\u2726\u2727\u2756\u2731\u2732\u2733\u2734\u2735"

    # --- Avvisi e simboli ---
    "\u26A0\u26A1\u2600\u2601\u2744"

    # --- Bullet e marker di elenco ---
    "\u2022\u2023\u25E6\u2043\u2219"

    # --- Paragrafi, note, dagger ---
    "\u00A7\u00B6\u2020\u2021"

    # --- Punteggiatura tipografica ---
    "\u2014\u2013\u2026\u201C\u201D\u2018\u2019"

    # --- Simboli vari utili ---
    "\u20AC\u00A3\u00A5\u00A9\u00AE\u2122\u00B0\u00B1\u00D7\u00F7"
)


def fix_simboli(testo: str) -> str:
    """
    Converte:
      - pedici/apici Unicode -> <sub>/<super> (funziona con qualsiasi font)
      - simboli non decomponibili -> <font name='LibroSimboli'>...</font>

    Idempotente e sicuro su stringhe che contengono gia' tag HTML di ReportLab.
    """
    risultato = []
    for ch in testo:
        if ch in _SUB_MAP:
            c, tag = _SUB_MAP[ch]
            risultato.append(f"<{tag}>{c}</{tag}>")
        elif ch in _SIMBOLI_PROBLEMATICI and _simboli_disponibili:
            risultato.append(f'<font name="LibroSimboli">{ch}</font>')
        else:
            risultato.append(ch)
    return "".join(risultato)