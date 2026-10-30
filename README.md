# LIBRI

Applicazione desktop per creare, organizzare e consultare libri e materiali di studio.

## Avvio da sorgente

Requisiti: Python e Windows.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Installazione Windows

Scarica `LIBRI-Setup-0.4.2.exe` dalla [release più recente](https://github.com/AlessandroMastrocicco/libri-app/releases/latest)
ed eseguilo. L'installer aggiunge LIBRI al menu Start e, se selezionato,
al desktop; i collegamenti mostrano il nome e l'icona dell'app, senza
l'estensione `.exe`.

LIBRI controlla all'avvio se GitHub segnala una versione più recente. Il
controllo richiede una connessione Internet; se non è disponibile, l'app
continua ad avviarsi normalmente.

Il tour guidato attraversa le schermate dell'app usando un libro
dimostrativo temporaneo, senza modificare i dati personali. Si apre al centro
dello schermo e può essere spostato.

Durante la validazione del codice dei paragrafi, i nomi delle figure nel
formato `L1_S003_nome.png` preselezionano la lezione e la slide di origine.
Le estrazioni esistenti ricevono automaticamente identificatori `L1`, `L2`,
ecc.; se l'associazione automatica non è corretta, la lezione e la slide
possono essere selezionate manualmente. La sorgente del ritaglio viene
registrata con l'immagine del capitolo.

Al primo avvio da sorgente l'app crea la cartella `libri` nella directory
del progetto. I contenuti aggiunti dall'utente restano locali e non sono
inclusi in questo repository.

Il motore PDF include Noto Sans Math per rappresentare un'ampia gamma di
simboli matematici e logici Unicode, compresi operatori, frecce, relazioni e
alfabeti matematici. Il font è distribuito secondo la licenza SIL Open Font
License 1.1, inclusa in `assets/fonts/OFL-NotoSansMath.txt`.

## Generazione assistita con AI (modalità automatica)

Oltre alla modalità manuale (incolla il codice del paragrafo), l'app offre una
**modalità automatica**: dalla schermata «Crea paragrafo» basta spuntare
*«Genera automaticamente con l'AI»* e premere «Genera». L'app analizza le slide
estratte, assembla il contesto pertinente e produce il codice del paragrafo come
**bozza da validare** (l'output non viene mai committato senza approvazione).

Configurazione minima:

1. copia `.env.example` in `.env` e inserisci la chiave di almeno un provider
   gratuito (Groq, Gemini, OpenRouter, Cerebras, Mistral, SambaNova, GitHub,
   DeepSeek); in alternativa installa [Ollama](https://ollama.com) per il
   fallback locale gratuito e illimitato;
2. all'avvio l'infrastruttura (`app/core/ai/`) ruota automaticamente tra i
   modelli disponibili: quando un modello esaurisce la quota giornaliera il
   router passa al successivo, con escalation ai modelli più potenti per i
   task complessi (analisi slide) e modelli leggeri per la scrittura.

Nota: richiavi nel file `.env` restano locali ed escluse dal repository.

## Struttura

- `app/`: interfaccia e logica dell'applicazione.
  - `app/core/ai/`: infrastruttura AI (catalogo modelli, router quote,
    ottimizzazione token, contesto ampio, scelta strategica, orchestratore).
  - `app/core/ai/providers/`: adapter di trasporto (OpenAI-compat, Gemini, Ollama).
- `motore/`: componenti per la generazione e il rendering dei contenuti.
- `main.py`: punto di ingresso.

## Dati esclusi

Il repository non contiene i libri, i materiali estratti, le risposte, le cache
di rendering o i file generati durante la compilazione. Questi dati possono
avere contenuti personali o soggetti a diritti d'autore; restano nella copia
locale dell'applicazione.
