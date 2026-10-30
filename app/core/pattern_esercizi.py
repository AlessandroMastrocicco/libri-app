# -*- coding: utf-8 -*-
"""
pattern_esercizi.py - Regole strutturali per la generazione di un
eserciziario (domande teoriche ed esercizi).
"""

PATTERN_ESERCIZI = """\
REGOLE STRUTTURALI PER UN ESERCIZIARIO
======================================

REQUISITO FONDAMENTALE
----------------------
Non puoi scrivere l'eserciziario finché l'utente non ha caricato in chat:
1. Le immagini (PNG) delle slide di riferimento.
2. Il testo o il codice del paragrafo di teoria corrispondente (se disponibile).

OUTPUT
------
Produci un SOLO file Python completo, eseguibile e importabile.
Il contenuto deve essere ESCLUSIVAMENTE composto da domande teoriche aperte, 
quesiti ed esercizi basati sui concetti delle slide.
NON introdurre nuovi concetti teorici. Fai solo domande su ciò che è già 
stato spiegato nella teoria. Nelle tracce e nelle soluzioni NON compare
mai alcun riferimento alle slide ("come a lezione", "vedi dispensa"):
gli esercizi si leggono come parte autonoma del libro (guida autore,
sez. 2).

STRUTTURA DEL FILE (obbligatoria, nell'ordine)
----------------------------------------------

1) Docstring del modulo, con id e titolo dell'eserciziario sulla prima riga.

2) Variabile di collegamento (FONDAMENTALE):
    _TEORIA_ORIGINE = "{teoria_origine}"

3) Import dal motore:
    from motore.stili import STILI
    from motore.componenti import (
        P, regola, definizione, esempio, attenzione, errore,
        collegamento, ppt, dritta, recap, separatore, spazio,
        codice, tabella,
    )

4) def story() a livello di modulo:
    def story():
        return [
            P("1.4 Esercizi - Dentro il Sistema Operativo", STILI["Paragrafo"]),
            ...
        ]

STILE E FORMATO
---------------
- Usa P("Domanda 1: ...", STILI["Testo"]) per le domande.
- Lascia dello spazio bianco (spazio(2.0)) sotto ogni domanda per far 
  scrivere le risposte a mano o a computer.
- Raggruppa gli esercizi in base agli argomenti delle slide.
- Puoi usare il riquadro `esempio` per mostrare la risoluzione di un 
  esercizio pratico, se previsto dalle slide.

VINCOLI
-------
- Non alterare i nomi delle chiavi di STILI.
- Non usare HTML non supportato.
- Non rimuovere la funzione story().
"""