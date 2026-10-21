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

Al primo avvio l'app crea la cartella `libri` nella directory del progetto. I
contenuti aggiunti dall'utente restano locali e non sono inclusi in questo
repository.

## Struttura

- `app/`: interfaccia e logica dell'applicazione.
- `motore/`: componenti per la generazione e il rendering dei contenuti.
- `main.py`: punto di ingresso.

## Dati esclusi

Il repository non contiene i libri, i materiali estratti, le risposte, le cache
di rendering o i file generati durante la compilazione. Questi dati possono
avere contenuti personali o soggetti a diritti d'autore; restano nella copia
locale dell'applicazione.
