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
import re
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

MATH_FONT_PATH = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "fonts"
    / "NotoSansMath-Regular.ttf"
)

_FONTS = [
    ("LibroRegular",    ["arial.ttf"]),
    ("LibroBold",       ["arialbd.ttf"]),
    ("LibroItalic",     ["ariali.ttf"]),
    ("LibroBoldItalic", ["arialbi.ttf"]),
    ("LibroMono",       ["cour.ttf"]),
    ("LibroMonoBold",   ["courbd.ttf"]),
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
_font_registrati = set()


def registra_font() -> bool:
    """
    Registra i font una sola volta (idempotente).
    Ritorna True se i font Unicode principali sono stati registrati.
    """
    global _registrati_ok, _simboli_disponibili, _eseguito
    global _font_registrati
    if _eseguito:
        return _registrati_ok
    _eseguito = True

    registrati = set()
    if FONTS_DIR is not None and FONTS_DIR.exists():
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

    if MATH_FONT_PATH.is_file():
        try:
            pdfmetrics.registerFont(
                TTFont("LibroSimboli", str(MATH_FONT_PATH))
            )
            registrati.add("LibroSimboli")
        except Exception as e:
            print(f"[WARN] Impossibile registrare il font matematico: {e}")
    elif FONTS_DIR is not None and FONTS_DIR.exists():
        for filename in ("seguisym.ttf", "segoeui.ttf"):
            path = FONTS_DIR / filename
            if not path.is_file():
                continue
            try:
                pdfmetrics.registerFont(TTFont("LibroSimboli", str(path)))
                registrati.add("LibroSimboli")
                break
            except Exception as e:
                print(f"[WARN] Impossibile registrare LibroSimboli da {filename}: {e}")

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
    _font_registrati = registrati
    _registrati_ok = {"LibroRegular", "LibroBold", "LibroItalic",
                      "LibroBoldItalic", "LibroMono", "LibroMonoBold"} <= registrati

    if _registrati_ok:
        print("[ok] Font Unicode registrati (Arial + Courier New).")
    else:
        print(f"[WARN] Solo {len(registrati)}/{len(_FONTS)} font registrati.")
    if _simboli_disponibili:
        print("[ok] Font matematico Unicode registrato.")
    else:
        print("[WARN] Font matematico non trovato: simboli estesi potrebbero mancare.")

    return _registrati_ok


def nome_font(logico: str) -> str:
    """
    Restituisce il nome del font logico se registrato, altrimenti il fallback.
    Da usare in tutti i fontName degli stili e nelle chiamate canvas.setFont().
    """
    if logico in _font_registrati:
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
# Blocchi Unicode con simboli matematici, logici e formali.
# ---------------------------------------------------------------------------
_MATH_RANGES = (
    (0x0370, 0x03FF),  # Greek and Coptic
    (0x1F00, 0x1FFF),  # Greek Extended
    (0x2000, 0x206F),  # General Punctuation and mathematical primes
    (0x2070, 0x209F),  # Superscripts and Subscripts
    (0x20D0, 0x20FF),  # Combining Diacritical Marks for Symbols
    (0x2100, 0x214F),  # Letterlike Symbols
    (0x2190, 0x21FF),  # Arrows
    (0x2200, 0x22FF),  # Mathematical Operators
    (0x27C0, 0x27EF),  # Miscellaneous Mathematical Symbols-A
    (0x27F0, 0x27FF),  # Supplemental Arrows-A
    (0x2900, 0x297F),  # Supplemental Arrows-B
    (0x2980, 0x29FF),  # Miscellaneous Mathematical Symbols-B
    (0x2A00, 0x2AFF),  # Supplemental Mathematical Operators
    (0x2B00, 0x2BFF),  # Miscellaneous Symbols and Arrows
    (0x1D400, 0x1D7FF),  # Mathematical Alphanumeric Symbols
)

_REPORTLAB_MARKUP_RE = re.compile(
    r'</?(?:b|i|u|strike|super|sub|font|span|link|a|br|para|bullet|'
    r'greek|unichar|onDraw|index|setLink|seq|seqdefault|seqreset)'
    r'(?:\s+[^<>]*?)?\s*/?>|&(?:#[0-9]+|#x[0-9A-Fa-f]+|'
    r'[A-Za-z][A-Za-z0-9]+);'
)


def fix_simboli(testo: str) -> str:
    """
    Converte:
      - pedici/apici Unicode -> <sub>/<super> (funziona con qualsiasi font)
      - simboli non decomponibili -> <font name='LibroSimboli'>...</font>

    Idempotente e sicuro su stringhe che contengono gia' tag HTML di ReportLab.
    """
    risultato = []
    simboli = (
        pdfmetrics.getFont("LibroSimboli").face.charWidths
        if _simboli_disponibili
        else {}
    )
    indice = 0
    font_simboli_attivi = []
    while indice < len(testo):
        ch = testo[indice]
        if ch == "<" or ch == "&":
            markup = _REPORTLAB_MARKUP_RE.match(testo, indice)
            if markup:
                token = markup.group(0)
                risultato.append(token)
                if token.lower().startswith("<font"):
                    font_simboli_attivi.append(
                        bool(re.search(
                            r'\bname\s*=\s*["\']LibroSimboli["\']',
                            token,
                            re.IGNORECASE,
                        ))
                    )
                elif token.lower() == "</font>" and font_simboli_attivi:
                    font_simboli_attivi.pop()
                indice = markup.end()
                continue
            if ch == "<":
                risultato.append("&lt;")
                indice += 1
                continue
            if ch == "&":
                risultato.append("&amp;")
                indice += 1
                continue

        if ch in _SUB_MAP:
            c, tag = _SUB_MAP[ch]
            risultato.append(f"<{tag}>{c}</{tag}>")
        elif (
            _simboli_disponibili
            and not any(font_simboli_attivi)
            and ord(ch) in simboli
            and any(start <= ord(ch) <= end for start, end in _MATH_RANGES)
        ):
            risultato.append(f'<font name="LibroSimboli">{ch}</font>')
        else:
            risultato.append(ch)
        indice += 1
    return "".join(risultato)