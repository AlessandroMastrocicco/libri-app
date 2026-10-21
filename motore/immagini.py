# -*- coding: utf-8 -*-
"""
motore/immagini.py

Gestione immagini da URL per i libri didattici.

Scarica un'immagine da un URL pubblico, la salva in cache locale
dentro ``libri/<NOME_LIBRO>/immagini/`` e la incorpora nel PDF.

Include uno User-Agent esplicito (necessario per Wikimedia Commons,
che risponde 403 Forbidden alle richieste anonime).
"""
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, Spacer

from motore.stili import STILI
from motore.fonts import nome_font


# ---------------------------------------------------------------
# Stato del libro corrente (impostato da builder.py)
# ---------------------------------------------------------------

_RADICE_PROGETTO = Path(__file__).parent.parent
_libro_corrente = None


def set_libro_corrente(nome_libro):
    global _libro_corrente
    _libro_corrente = nome_libro


def _cartella_cache():
    if _libro_corrente is None:
        raise RuntimeError(
            "motore.immagini: nessun libro corrente impostato. "
            "Chiamare set_libro_corrente(nome) prima di usare immagine()."
        )
    cartella = _RADICE_PROGETTO / "libri" / _libro_corrente / "immagini"
    cartella.mkdir(parents=True, exist_ok=True)
    return cartella


# ---------------------------------------------------------------
# Download
# ---------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


def _nome_cache(url):
    """Determina un nome file univoco per l'URL, preservando l'estensione."""
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    percorso = url.split("?")[0]
    ext = ".img"
    for e in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        if percorso.lower().endswith(e):
            ext = e
            break
    return f"{h}{ext}"


def _scarica(url, percorso_dest):
    req = Request(url, headers=_HEADERS)
    with urlopen(req, timeout=30) as risposta:
        dati = risposta.read()
    if not dati or len(dati) < 100:
        raise ValueError(f"risposta vuota o troppo piccola ({len(dati)} byte)")
    percorso_dest.write_bytes(dati)
    return len(dati)


def _recupera_immagine(url):
    """Ritorna il Path locale dell'immagine, scaricandola se necessario."""
    percorso = _cartella_cache() / _nome_cache(url)
    if percorso.exists() and percorso.stat().st_size > 100:
        return percorso
    try:
        n = _scarica(url, percorso)
        print(f"[immagine] scaricata: {percorso.name} ({n} byte)")
        return percorso
    except (URLError, HTTPError, TimeoutError, OSError, ValueError) as e:
        print(f"[immagine] download fallito ({url}): {e}")
        return None


# ---------------------------------------------------------------
# Costruzione flowables
# ---------------------------------------------------------------

def _placeholder(url, larghezza):
    """Riquadro grigio con messaggio + URL quando l'immagine non è disponibile."""
    larghezza = larghezza or (A4[0] - 4 * cm)
    testo = (
        f'<i>Immagine non disponibile</i><br/>'
        f'<font size="7" color="#888888">{url}</font>'
    )
    par = Paragraph(testo, STILI["Testo"])
    from reportlab.platypus import Table, TableStyle
    tab = Table([[par]], colWidths=[larghezza])
    tab.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#EEEEEE")),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#BBBBBB")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    return [Spacer(1, 0.3 * cm), tab, Spacer(1, 0.3 * cm)]


def immagine(url, didascalia=None, larghezza=None, allineamento="CENTER"):
    """
    Scarica (o recupera dalla cache) un'immagine e restituisce una
    lista di flowables ReportLab: [Spacer, Image, Paragraph(didascalia), Spacer].
    """
    larghezza_max = larghezza or (A4[0] - 4 * cm)

    percorso = _recupera_immagine(url)
    if percorso is None:
        return _placeholder(url, larghezza_max)

    try:
        img_reader = ImageReader(str(percorso))
        iw, ih = img_reader.getSize()
    except Exception as e:
        print(f"[immagine] lettura fallita ({percorso}): {e}")
        return _placeholder(url, larghezza_max)

    rapporto = ih / iw
    larghezza_finale = larghezza_max
    altezza_finale = larghezza_finale * rapporto

    altezza_max = A4[1] * 0.5
    if altezza_finale > altezza_max:
        altezza_finale = altezza_max
        larghezza_finale = altezza_finale / rapporto

    img = Image(str(percorso), width=larghezza_finale, height=altezza_finale)
    img.hAlign = allineamento

    flowables = [Spacer(1, 0.3 * cm), img]

    if didascalia:
        did = Paragraph(
            f'<font size="9" color="#555555"><i>{didascalia}</i></font>',
            STILI["Testo"],
        )
        did.hAlign = allineamento
        flowables.append(Spacer(1, 0.15 * cm))
        flowables.append(did)

    flowables.append(Spacer(1, 0.4 * cm))
    return flowables