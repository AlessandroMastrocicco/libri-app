# -*- coding: utf-8 -*-
"""
prompt.py - Costruzione dei prompt ottimizzati per costo (bozza).

Tecniche implementate:
  * separazione blocco statico (PATTERN compressi) / dinamico, con chiave di
    cache per i provider che supportano il cached input;
  * compressione dei pattern di scrittura: la versione compatta conserva il
    solo contratto strutturale (API motore + regole dure), per riparazioni e
    modelli leggeri;
  * innesto locale del boilerplate: il modello scrive solo il corpo, gli
    import e l'helper figura() li aggiungiamo noi (meno token in output).
"""

from __future__ import annotations

import hashlib

from app.core.ai.guida_autore import blocchi_guida, vincoli_operativi
from app.core.ai.tokeni import stima_token


# ======================================================================
# Compressione dei pattern
# ======================================================================

# Sezioni del PATTERN_PARAGRAFO indispensabili anche per i task minimi.
_CONTRATTO_PARAGRAFO = """\
CONTRATTO STRUTTURALE (versione compatta delle regole LIBRI):
- File Python unico, eseguibile, senza blocchi markdown.
- Definizioni obbligatorie a livello di modulo: METADATI = {'titolo': ...}
  e def story() -> list di flowable ReportLab.
- Import ammessi: da motore.stili (STILI) e motore.componenti con le sole
  funzioni: P, regola, definizione, esempio, attenzione, errore,
  collegamento, ppt, dritta, recap, separatore, spazio, codice, tabella.
- Chiavi STILI note: Capitolo, Paragrafo, Sottoparagrafo, Testo,
  TestoPiccolo, ElencoPuntato, ElencoNumerato, Codice, CodiceInline,
  TitoloSezione.
- Figure: helper figura("L1_S003_nome.png") definito una sola volta prima
  di story(); ogni figura(...) e' un flowable separato nella lista di
  story(), mai annidato in P(). Nome = lezione Lx + slide Sxxx (3 cifre).
- Tono "noi didattico", prosa continua; niente elenchi come corpo del
  testo; riquadri didattici dove chiariscono (max ~2 per sottoparagrafo).
- In coda a OGNI sottoparagrafo il blocco Fonti/Tratto da/Elaborazione
  dell'autore (guida autore); niente riferimenti alle slide nel corpo.
- Non accorciare il contenuto per limiti di risposta: chiudi il blocco al
  punto naturale e dichiara la continuazione.
"""

_CONTRATTO_ESERCIZI = """\
CONTRATTO STRUTTURALE ESERCIZIARIO (compatto):
- Stesso contratto del paragrafo di teoria (file Python, story(), stili).
- Solo esercizi/domande risolvibili, con soluzioni commentate alla fine.
- Collegamento al paragrafo di teoria indicato dall'utente.
"""


def pattern_compresso(kind: str = "paragrafo") -> str:
    if kind == "esercizi":
        return _CONTRATTO_ESERCIZI
    return _CONTRATTO_PARAGRAFO


def comprimi_pattern(pattern_completo: str, kind: str = "paragrafo") -> str:
    """Restituisce la versione compatta. Il pattern completo resta in uso
    solo per il primo draft della classe SCRITTURA/RAGIONAMENTO."""
    return pattern_compresso(kind)


def risparmio_stimato(pattern_completo: str, kind: str = "paragrafo") -> dict:
    """Metrica per il pannello debug: quanto fa risparmiare la compressione."""
    pieno = stima_token(pattern_completo)
    compatto = stima_token(pattern_compresso(kind))
    return {"pattern_pieno_tok": pieno, "pattern_compatto_tok": compatto,
            "risparmio_tok": pieno - compatto,
            "risparmio_pct": round(100 * (pieno - compatto) / max(pieno, 1))}


# ======================================================================
# Cache statica/dinamica
# ======================================================================

def hash_blocco(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()[:16]


def costruisci_messaggi(blocco_statico: str, blocchi_dynamici: list[str],
                        istruzione_task: str,
                        immagini: list[str] | None = None) -> tuple[list[dict], str]:
    """Costruisce i messaggi in ordine cache-friendly:

      [system: statico (PATTERN)]   <- identico tra task, cacheabile
      [user: contesto dinamico]     <- varia per paragrafo
      [user: istruzione del task]   <- breve, sempre ultima

    Restituisce (messaggi, prompt_cache_key) dove la chiave e' derivata dal
    contenuto statico: i provider con cached input (Gemini context caching,
    OpenRouter/DeepSeek prompt cache) la usano per fatturare meno il system.
    """
    messaggi: list[dict] = []
    if blocco_statico:
        messaggi.append({"role": "system", "content": blocco_statico})
    if blocchi_dynamici:
        contesto = "\n\n---\n\n".join(blocchi_dynamici)
        if immagini:
            # Bozza: in Fase B le PNG diventeranno data-URL base64 nel campo
            # image_url; qui registriamo solo i percorsi per la stima costi.
            parti: list[dict] = [{"type": "text", "text": contesto}]
            for path_img in immagini:
                parti.append({"type": "image_ref", "path": str(path_img)})
            messaggi.append({"role": "user", "content": parti})
        else:
            messaggi.append({"role": "user", "content": contesto})
    messaggi.append({"role": "user", "content": istruzione_task})
    return messaggi, f"libri-{hash_blocco(blocco_statico)}"


# ======================================================================
# Assemblaggio allineato alla Guida per l'AI-autore
# ======================================================================

def statico_per_scrittura(pattern_manuale: str, kind: str = "paragrafo") -> str:
    """Blocco system per i task di scrittura: contratto editoriale della
    Guida autore (cosa scrivere e perche') + manuale tecnico del formato
    (come produrre il file). L'ordine e' fisso => prefix cache stabile.

    In caso di conflitto: sul contenuto/pedagogia comanda la guida, sul
    formato del codice comanda il manuale (sezione 'Come usare' del PDF).
    """
    return ("\n\n".join(blocchi_guida(kind)).strip()
            + "\n\n=== MANUALE TECNICO DEL FORMATO (premiere su conflitti "
              "di formattazione) ===\n\n"
            + pattern_manuale.strip())


def messaggi_per_paragrafo(*, pattern_manuale: str, contesto_blocchi: list[str],
                           titolo_paragrafo: str, kind: str = "paragrafo",
                           immagini: list[str] | None = None):
    """Scatola i messaggi per un paragrafo allineati alla guida:
    system = guida+manuale; user = contesto; istruzione = mini-piano."""
    statico = statico_per_scrittura(pattern_manuale, kind)
    istruzione = vincoli_operativi(titolo_paragrafo)
    return costruisci_messaggi(statico, contesto_blocchi, istruzione, immagini)


# ======================================================================
# Output parsimonioso: innesto locale del boilerplate
# ======================================================================

_BOILERPLATE_FIGURA = """\
from pathlib import Path
from reportlab.lib.units import cm
from reportlab.platypus import Image


def figura(nome_file):
    percorso = Path(__file__).resolve().parents[1] / "immagini" / nome_file
    return Image(str(percorso), width=15*cm, height=10*cm,
                 kind="proportional")
"""

ISTRUZIONE_SOLO_CORPO = (
    "Rispondi SOLO con il corpo del modulo Python (METADATI, definizioni e "
    "story()). Non ripetere gli import standard ne' l'helper figura(): "
    "vengono innestati dall'app. Nessun testo fuori dal codice."
)


def innesta_boilerplate(corpo: str, usa_figure: bool = True) -> str:
    """Aggiunge localmente cio' che avrebbe sprecato token in output."""
    testa = _BOILERPLATE_FIGURA if usa_figure else ""
    return (testa + corpo).strip() + "\n"
