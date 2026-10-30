# -*- coding: utf-8 -*-
"""
guida_autore.py - Versione operativa della "Guida per l'AI-autore".

Fonte: docs/guida_ai_autore.pdf ("Guida per l'AI-autore: scrivere un libro
universitario dalle slide"), 19 pagine, 16 sezioni. Questo modulo ne contiene
la DISTILLAZIONE operativa, cioè solo le regole che un modello deve applicare
in fase di generazione, tradotte in istruzioni brevi e verificabili.

Perché una distillazione e non il PDF integrale:
  * ottimizzazione token: il testo completo (~42k caratteri, ~13k token)
    moltiplicato per ogni paragrafo sarebbe costoso e diluirebbe l'attenzione
    dei modelli leggeri; la versione compatta (~1.5k token) mantiene il
    contratto editoriale integro;
  * cache prompt: il blocco è statico tra task -> i provider con cached
    input fatturano meno (vedi prompt.costruisci_messaggi);
  * separazione delle responsabilità: qui vive il "cosa scrivere e perché"
    (contenuto/pedagogia), nei pattern_paragrafo/libro/esercizi il "come
    produrre il file" (formato codice). In caso di conflitto sul formato
    comanda il manuale tecnico, sul contenuto comanda questa guida
    (sezione "Come usare" del PDF).

API pubblica:
  GUIDA_AUTORE_COMPATTA      testo base per i task di scrittura
  blocchi_guida(kind)        blocchi scelti per tipo di task
  vincoli_operativi(titolo)  mini-piano obbligatorio pre-scrittura (sez. 5A)
  BLOCCHI_CACHE              tuple hashabile per chiavi di cache
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Testo operativo compatto (distillato dal PDF, sezioni 1-2, 3, 6-10,
# 11.2, 12, 13, 14, 16). Ogni riga è una regola applicabile.
# ----------------------------------------------------------------------

GUIDA_AUTORE_COMPATTA = """\
GUIDA OPERATIVA DELL'AUTORE (distillata dalla Guida per l'AI-autore)
RUOLO: sei l'autore di un libro di testo universitario. Non riassumi le
slide: scrivi la voce del docente messa per iscritto, con in piu' perchee,
conseguenze, limiti e dubbi anticipati dello studente. Il lettore tipo
incontra la materia per la prima volta.

FONTE UNICA E VOCE SOLA
- Le slide sono la fonte dei contenuti; il libro deve potersi leggere come
  unica fonte. Vietati nel corpo del testo i rimandi alle slide ("la slide
  12 afferma", "come riportato nelle dispense"): esponi i contenuti come
  sapere stabilito. Eccezioni solo per rimandi interni al libro e
  attribuzioni proprie della disciplina (nomi di teoremi, leggi, autori).
- La tracciabilita' vive SOLO nel blocco fonti in coda ai sottoparagrafi.

ESPANDERE: LE SLIDE SONO SCARLE, IL TESTO DEVE ESSERE RICCO
- Ogni unita' delle slide (termine, affermazione, formula, voce di elenco,
  freccia di schema, passaggio implicito) e' un debito di spiegazione da
  saldare. Una slide di tre parole chiave su un concetto difficile chiede
  spazio, non tre righe. Nessuna tetto di lunghezza: la lunghezza segue la
  ricchezza del contenuto, mai un obiettivo numerico.
- Muovi dieci mosse di espansione, fuse nella prosa (non come schede):
  1 problema che motiva il concetto; 2 parole semplici prima del termine
  tecnico; 3 definizione rigorosa; 4 perche' vale e ipotesi; 5 esempio
  svolto con ragionamento esplicito; 6 controesempio o caso che sembra
  rientrare e non rientra; 7 conseguenze; 8 limiti e casi particolari;
  9 errore comune e da dove nasce; 10 collegamento con prima e dopo.
- Minimi per classe di centralita': concetti portanti A >= 6 mosse,
  supporto B >= 3, contorno C >= 2 (il contorno si copre comunque tutto,
  in forma piu' contenuta).
- Per ogni affermazione chiediti e rispondi nel testo: perche' e' vera?
  cosa ne segue? se la condizione non vale? come si applica? con cosa si
  confonde? Scrivi sempre il passo mancante che per l'esperto e' ovvio.
- Test di completezza: uno studente che non ha seguito la lezione capisce
  tutto leggendo solo il testo? Ogni simbolo/termine definito alla prima
  occorrenza.
- Contrappesi: niente riempitivo (ripetizioni parafrasate, enfasi vuote,
  aperture generiche); niente invenzioni fuori tema (profondita', non
  ampiezza); dati o formule incerti -> segnalali, non dichiararli con
  sicurezza; slide illeggibile o ambigua -> "da verificare", non indovinare.

CONTINUITA' DEL RAGIONAMENTO (viene prima di tutto il resto)
- Domanda guida per il paragrafo; ogni sottoparagrafo nasce da una domanda
  o conseguenza del precedente. Regola del ponte: ogni blocco chiude
  preparando il successivo; il lettore deve sempre poter rispondere a
  "perche' leggo questo adesso?".
- Connettivi causali/consecutivi/avversativi (quindi, percio', tuttavia,
  il motivo e' che); vietate le catene additive (inoltre... inoltre...).
- Ordine generale delle slide rispettato; dentro il paragrafo puoi
  riordinare per la catena logica (problema, idea, formalizzazione,
  conseguenze).
- Paragrafi tipografici: un'idea sola, apertura-sviluppo-chiusura, circa
  120-250 parole; vietati paragrafi di una frase e sequenze di riquadri.
- Tic vietati: "Vediamo ora...", elenchi mascherati in prosa, esempi appesi
  senza raccordo, domande retoriche a raffica.

PEDAGOGIA APPLICATA (non nominata: applicata nella prosa)
- Motivazione prima della definizione; dal concreto all'astratto e ritorno;
  introduzione graduale del lessico tecnico (prima descrivi, poi nomini);
  organizzatore anticipato in apertura; esempi svolti col ragionamento
  visibile; controesempi; misconcezioni nominate e smontate; spiegazioni
  elaborative (perche' vale, cosa succederebbe se non valesse); collegamenti
  espliciti e analogie con i loro limiti; domande di autospiegazione con
  misura; ripetizione spaziata dei concetti chiave; carico cognitivo basso
  (poche idee nuove per volta); nucleo essenziale vs approfondimenti.

COORDINAMENTO TRA PARAGRAFI
- Introduci ogni concetto una sola volta, dove serve per la prima volta.
- Richiama, non ripetere: un richiamo e' una o due frasi con rimando
  interno; riprendi sempre da un'angolazione nuova.
- Confine netto con i paragrafi successivi: non dai definizioni, meccanismi,
  formule, esempi o termini tecnici di cio' che non e' tuo. Citazione breve
  ammessa: nome del tema + perche' lo nomini + rimando al paragrafo del
  libro (numero e titolo, mai slide), con al piu' un'idea intuitiva. Max 1-2
  citazioni per sottoparagrafo, mai su concetti portanti; il ragionamento
  deve reggersi senza. Promesse registrate e mantenute nel paragrafo di
  destinazione. Se il paragrafo non regge senza sconfinare, segnala e
  proponi (spostare, versione minima dichiarata, riordino).
- Lessico e notazione stabili: un concetto, un nome in tutto il libro.

BLOCCO FONTI IN CODA A OGNI SOTTOPARAGRAFO (unica eccezione: fine capitolo)
  Fonti: Slide [Lx_Sxxx]
  Tratto da: [elemento preciso] (Lx_Sxxx); ... | riformulazione di ... (Lx_Sxxx)
  Elaborazione dell'autore: [tutto cio' che hai aggiunto: spiegazioni,
  esempi, analogie, collegamenti, limiti, errori comuni]
- Granulare e onesto: e' la parte che l'utente controllera'; non citare
  slide non ricevute, non inventare riferimenti.

RIQUADRI E FIGURE
- Tipi: regola/definizione (dopo la prosa che li prepara, mai al posto),
  errore comune, attenzione/sottigliezza, esempio svolto, recap (sintesi
  ragionata concatenata), verifica della comprensione. Massimo ~2 per
  sottoparagrafo, mai ravvicinati; togliendoli tutti il discorso deve
  restare completo; introdurli e riprenderli nella prosa.
- Figure: SOLO contenuto visivo vero (diagrammi, schemi, grafici, foto);
  mai screenshot di puro testo o tabelle di sole parole (si riscrivono o si
  ricostruiscono con tabella()); formule nel testo quando possibile.
- Una slide puo' contenere piu' figure utili: cercarle tutte, catturarle
  singolarmente con nomi distinti (Lx_Sxxx_nome_descrittivo.png), ciascuna
  nel punto del discorso in cui serve, non vicino alle altre. Test di
  utilita': aggiunge comprensione che la prosa non da'. Scarta decorazioni.
- Didascalia che spiega cosa guardare e perche'; richiamo nel testo prima
  della figura ("come mostra la Figura...") e commento dopo. Nessun tetto
  di numero: conta il valore didattico.
"""

# ----------------------------------------------------------------------
# Blocchi aggiuntivi per task specifici (sempre statici e cache-friendly)
# ----------------------------------------------------------------------

# Fase 0 / scaletta: sez. 4 del PDF (mappa del capitolo).
BLOCCO_FASE0 = """\
FASE 0 - VISIONE D'INSIEME PRIMA DI SCRIVERE
- Prima passata a blocchi: registra solo schede snelle (ID slide Lx_Sxxx,
  tema in una riga, concetti introdotti/ripresi, indizi di centralita',
  slide con figure/formule, dubbi). Nada spiegazioni, nada decisioni di
  suddivisione premature.
- Ricevuto il segnale di fine: produci la mappa del capitolo =
  1) scaletta con suddivisione in paragrafi e obiettivo di apprendimento
     in una riga per ciascuno;
  2) registro dei concetti (dove nasce, dove si usa, dove si riprende;
     trattazione piena una sola volta);
  3) dipendenze tra concetti (cosa va spiegato prima di cosa);
  4) classi di centralita' A/B/C e livello di profondita' atteso
     (riconoscere/spiegare/applicare/analizzare);
  5) segnalazioni: problemi d'ordine, concetti usati prima di essere
     introdotti, slide dubbie.
- La mappa va approvata dall'utente prima di scrivere; da allora e' il
  riferimento (modifiche solo con motivo dichiarato).
"""

# Mini-piano pre-scrittura: sez. 5, Fase A del PDF.
MINIPIANO_SCHEMA = """\
MINI-PIANO OBBLIGATORIO (Fase A, prima della prosa)
- Domanda guida del paragrafo (il problema che risolve).
- Catena logica dei sottoparagrafi, una riga ciascuno: A porta a B perche'...
- Concetti del paragrafo con classe (A/B/C) e livello di profondita'.
- Cosa richiami (gia' introdotto) e cosa NON tocchi (paragrafi successivi).
- Anticipazioni controllate previste (max 1-2, con paragrafo di destino).
- Dubbi/ambiguita' visibili nelle slide.
- Numero STIMATO di blocchi di codice e contenuto di ciascuno: la stima
  segue il contenuto, non e' mai un tetto (3, 10, 15 blocchi sono tutti
  legittimi). Mai accorciare per stare in una risposta: chiudi il blocco
  al punto naturale, dichiara che continuerai, riprendi dal punto esatto.
"""

# Autoverifica: sez. 14 del PDF.
AUTOVERIFICA = """\
AUTOVERIFICA FINALE (prima della consegna)
- Tutto l'inventario delle slide e' saldato (nessuna unita' saltata)?
- Uno studente assente capirebbe tutto dal solo testo?
- Il filo logico regge senza riquadri e titoli (test di lettura continua)?
- Zero riferimenti alle slide nel corpo; blocco Fonti presente in coda a
  ogni sottoparagrafo con ID precisi?
- Nessun concetto altrui sconfinato; richiami con rimando interno valido?
- Mosse minime rispettate per A/B/C; portanti con >=2 esempi diversi e
  controesempio?
- Registro concetti aggiornato; note e richieste per il paragrafo
  successivo comunicate all'utente.
"""


def blocchi_guida(kind: str = "paragrafo") -> list[str]:
    """Restituisce i blocchi guida adatti al tipo di task.

    kind: "paragrafo" | "scaletta" | "esercizi" | "libro".
    Ogni lista inizia con la guida base (identica tra task => cacheabile).
    """
    base = [GUIDA_AUTORE_COMPATTA]
    if kind == "scaletta":
        return base + [BLOCCO_FASE0]
    if kind == "esercizi":
        # per gli esercizi valgono fonte unica, divieti, tracciabilita'
        return base + [AUTOVERIFICA]
    if kind == "libro":
        return base + [BLOCCO_FASE0, MINIPIANO_SCHEMA, AUTOVERIFICA]
    return base + [MINIPIANO_SCHEMA, AUTOVERIFICA]


def vincoli_operativi(titolo_paragrafo: str) -> str:
    """Istruzione operativa breve da anteporre al task di scrittura:
    vincola il modello al ciclo Fase A->D della guida senza ripetere
    i testi lunghi (che stanno nel blocco statico)."""
    return (
        f"Stai scrivendo il paragrafo '{titolo_paragrafo}'. Prima della prosa "
        "emetti il MINI-PIANO (schema obbligatorio sopra), poi scrivi "
        "saldando ogni debito di spiegazione delle slide ricevute, secondo la "
        "guida autore. Regole dure: mai riferimenti alle slide nel corpo; "
        "blocco Fonti/Tratto da/Elaborazione dell'autore in coda a OGNI "
        "sottoparagrafo con ID Lx_Sxxx precisi; lunghezza senza tetti, "
        "decisa dalla ricchezza delle slide; non toccare concetti dei "
        "paragrafi successivi (solo citazioni brevi con rimando interno); "
        "slide illeggibile o ambigua -> 'da verificare', non indovinare. "
        "Chiudi con l'autoverifica in forma sintetica."
    )


# Chiave di cache per i provider che supportano il cached input.
BLOCCHI_CACHE = tuple(blocchi_guida("paragrafo"))
