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

Scarica `LIBRI-Setup-0.3.0.exe` dalla [release più recente](https://github.com/AlessandroMastrocicco/libri-app/releases/latest)
ed eseguilo. L'installer aggiunge LIBRI al menu Start e, se selezionato,
al desktop; i collegamenti mostrano il nome e l'icona dell'app, senza
l'estensione `.exe`.

LIBRI controlla all'avvio se GitHub segnala una versione più recente. Il
controllo richiede una connessione Internet; se non è disponibile, l'app
continua ad avviarsi normalmente.

Il tour guidato attraversa le schermate dell'app usando un libro
dimostrativo temporaneo, senza modificare i dati personali.

Al primo avvio da sorgente l'app crea la cartella `libri` nella directory
del progetto. I contenuti aggiunti dall'utente restano locali e non sono
inclusi in questo repository.

## Struttura

- `app/`: interfaccia e logica dell'applicazione.
- `motore/`: componenti per la generazione e il rendering dei contenuti.
- `main.py`: punto di ingresso.

## Dati esclusi

Il repository non contiene i libri, i materiali estratti, le risposte, le cache
di rendering o i file generati durante la compilazione. Questi dati possono
avere contenuti personali o soggetti a diritti d'autore; restano nella copia
locale dell'applicazione.
