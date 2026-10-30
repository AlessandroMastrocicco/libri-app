# LIBRI — Bozza del sistema AI automatizzato (v0, non ancora integrato a runtime)

> Documento di progettazione dell'infrastruttura "Generazione Assistita".
> Il codice di riferimento (bozza) vive in `app/core/ai/`. Nessuna release
> GitHub è stata creata: questa è la fase di bozza richiesta.

---

## 1. Obiettivo

Oggi l'utente deve:
1. copiare le regole (pattern) negli appunti;
2. aprire una chat esterna (DeepSeek), caricare le slide PNG a mano;
3. incollare il prompt;
4. attendere, copiare il codice generato e incollarlo in LIBRI;
5. validare.

Obiettivo: in **modalità automatizzata** l'app fa tutto questo da sola:
analizza le slide, progetta la struttura del capitolo, genera il codice di
ogni paragrafo con contestuale estrazione delle figure, lo valida e — in
caso di errore — si auto-corregge, senza mai chiedere all'utente di
incollare qualcosa. La **modalità manuale** attuale resta intatta.

Principio guida: *l'AI non tocca mai i file dell'utente direttamente*.
Produce solo testo; la scrittura avviene esclusivamente tramite i canali
esistenti (`crea_paragrafo` / `aggiorna_paragrafo`), che già validano.

---

## 2. Architettura a livelli

```
┌───────────────────────────────────────────────────────────────┐
│ UI (customtkinter)                                            │
│  SchermataCreaParagrafo: selettore Manuale | Assistita        │
│  Pannello "Pipeline": coda task, modello attivo, token oggi   │
├───────────────────────────────────────────────────────────────┤
│ Orchestratore (pipeline.py)                                   │
│  DAG dei task: Analysis → Outline → Draft → Validate          │
│                → AutoRepair → Commit                          │
│  Ogni task dichiara: costo stimato, classe di capacità        │
├───────────────────────────────────────────────────────────────┤
│ Router modelli (router.py)                                    │
│  choice = provider+model per CLASSE di compito, non per        │
│  capriccio: visione pesante/leggera, ragionamento,             │
│  riscrittura economica                                         │
│  Quota giornaliera per provider + rotazione automatica         │
├───────────────────────────────────────────────────────────────┤
│ Provider adapter (providers.py)                               │
│  Interfaccia unica OpenAI-compatible: Groq, Google Gemini      │
│  Free Tier, Mistral La Plateforme, OpenRouter (aggregatore),   │
│  Cerebras, SambaNova, GitHub Models, DeepSeek API,             │
│  locale via Ollama (fallback offline illimitato)               │
├───────────────────────────────────────────────────────────────┤
│ Ottimizzazione token (tokeni.py)                              │
│  Stima euristica CJK-safe, budget assembler, cache prompt,     │
│  compressione pattern, sliding window + digest                 │
├───────────────────────────────────────────────────────────────┤
│ Memoria/Contesto (contesto.py)                                 │
│  Libro → Capitolo → Paragrafo: gerarchia di riassunti,         │
│  indice delle figure, glossario, stato "cosa è già detto"      │
└───────────────────────────────────────────────────────────────┘
```

### Moduli della bozza

| File | Ruolo |
|---|---|
| `app/core/ai/__init__.py` | Facciata del pacchetto |
| `app/core/ai/catalogo.py` | Catalogo modelli gratuiti, classi, quote/giorno |
| `app/core/ai/tokeni.py` | Stima token, troncamento sicuro, budget assembler |
| `app/core/ai/router.py` | Scelta modello per classe + switch su quota esaurita |
| `app/core/ai/prompt.py` | Compressione dei PATTERN, cache statica/dinamica |
| `app/core/ai/contesto.py` | Costruzione del contesto (slide, capitoli, glossario) |
| `app/core/ai/pipeline.py` | Orchestrazione, auto-riparazione, commit sicuro |

---

## 3. Classi di compito e assegnazione modelli

L'idea di partenza ("modelli potenti per operazioni complesse, leggeri per
la scrittura") è formalizzata in 5 classi:

| Classe | Compito | Requisiti | Candidati gratuiti (esempi) |
|---|---|---|---|
| `VISIONE_PESANTE` | Analisi slide: OCR concettuale, diagrammi, formule | vision, context ≥128k | Gemini 2.5 Flash, Groq llama-4-scout-17b-16e-instruct, Mistral pixtral-122b |
| `VISIONE_LEGGERA` | Slide semplici/testuali, indicizzazione batch | vision, economico | Gemini 2.0 Flash Lite, Moondream3 (Groq) |
| `RAGIONAMENTO` | Struttura capitolo, scaletta, coerenza argomentativa | long-context, reasoning | Groq qwen-qwq / kimi-k2, Gemini 2.5 Pro (finestra free), Mistral magistral |
| `SCRITTURA` | Codice del paragrafo, eserciziari, riformattazioni | output lungo, veloce | Groq llama-3.3-70b, Meta llama (OpenRouter free), Mistral small/medium, Cerebras qwen3 |
| `LOCAL` | Riparazioni minori, fallback offline | nessuna quota | Ollama qwen3 / llama3.2 (capacità minima dichiarata) |

Regola di routing: **mai un modello sotto la soglia di capacità della
classe**, anche se è l'unico con quota disponibile. Se nessuna opzione ha
quota, il task va in pausa con nota chiara ("quote esaurite, riprova alle
00:00 UTC o passa alla modalità manuale"), non un errore generico.

### Rotazione quote

- Quote registrate per provider come budget giornalieri approssimativi
  (richieste/giorno e token/giorno); sono **stimate** e vanno verificate a
  runtime con gli header di risposta quando disponibili (`x-ratelimit-*`).
- Finestra: giorno UTC, rollover automatico a mezzanotte.
- Ordine di preferenza nella classe: `(capacità sufficiente, priorità
  statica, minore usanza odierna relativa)`. Lo switch scatta su:
  - HTTP 429 / 402 con hint "quota";
  - pre-check: `tokeni_stimati(task) > quota_rimanente(modello)` →
    si cambia modello *prima* di consumare una chiamata;
  - tre errori di rete consecutivi → cooldown 15 min sul modello.
- Stato persistito in `libri/_ai_quota.json` (sopravvive ai riavvii).
- Anti-ping-pong: un modello "bruciato" per quota non viene riprovato
  prima del rollover; uno in cooldown viene riprovato dopo la scadenza.

---

## 4. Algoritmi di ottimizzazione token

1. **Stima euristica CJK-safe**: ~4 car/tok latino, ~5 cirillico/CJK,
   ~3 markup; calibrazione opzionale con `tiktoken` se presente.
2. **Prompt cache statica/dinamica**: i PATTERN (regole di scrittura) sono
   invariabili → inviati come blocco stabile in testa, con
   `prompt_cache_key`; i provider con cached-input (Gemini, OpenRouter,
   DeepSeek) applicano sconto 50–90%. Risparmio stimato: ~70% sui token
   di sistema ripetuti tra i task della stessa sessione.
3. **Compressione dei pattern**: il pattern paragrafo (~6k car) viene
   ridotto a versione compatta (~1.5k car) per i task di riparazione e
   riscrittura locale, dove serve solo il contratto strutturale
   (API motore, stili, helper figura). Il pattern completo va solo al
   primo draft della classe SCRITTURA.
4. **Budget assembler**: ordina i blocchi di contesto per utilità
   (contratto > slide corrente > digest capitoli precedenti > glossario)
   e riempie fino al tetto; i blocchi tagliabili vengono compressi in
   bullet, non eliminati silenziosamente.
5. **Map-reduce sulle slide**: le slide non viaggiano intere nel prompt
   del writer. Vengono distillate una sola volta (fase analisi) in schede
   strutturate `{id_lezione, slide, titolo, punti, figure}`; il writer
   riceve solo le 3–8 schede pertinenti al paragrafo. Costo vision pagato
   una volta, riusato per tutti i paragrafi del capitolo (cache su disco).
6. **Output parsimonioso**: il modello scrive SOLO il corpo del modulo
   Python; import boilerplate, helper `figura()` e docstring di metadati
   sono innestati localmente dall'orchestratore (−~400 token/task).
7. **max_tokens profilati**: draft 8k, riparazione 1.5k (patch diff-only
   con marker `@@SOSTITUISCI:`), analisi slide 600/scheda.
8. **Riparazione a patch**: invece di rigenerare 3000 parole, si invia
   frammento incriminato ± 5 righe + messaggio d'errore e si riceve la
   sola funzione/flowable corretto. Costo tipico: 3–5% del re-draft.

---

## 5. Algoritmi di contesto (memoria)

- **Digest incrementale**: a ogni paragrafo salvato si genera (classe
  SCRITTURA leggera) un riassunto di ≤120 token: concetti introdotti,
  definizioni date, esempi usati, figure citate. Persistito in
  `capitolo_XX/_ai_digest.json`. Il contesto del paragrafo N contiene:
  digest dei paragrafi 1..N−1 + ultimo paragrafo quasi-per-integro
  (transizione stilistica).
- **Indice figure globale**: mappa `nome_file → (lezione, slide, dida)`
  costruita dai nomi `L1_S003_*` e dalle mappature esistenti
  (`_mappatura_slide.json`, `_mappatura_lezioni.json`). Evita figure
  duplicate e nomi riusati (vincolo già presente nei pattern).
- **Glossario e stile**: termini tecnici definiti, tono "noi didattico",
  lunghezza obiettivo — un blocco unico <300 token riusato in ogni task.
- **Anti-ripetizione**: il writer riceve l'elenco dei concetti già
  spiegati (dal digest) con istruzione di richiamarli per collegamento,
  non di rispiegarli.
- **Coerenza cross-capitolo**: per la struttura del capitolo nuovo, il
  router usa un modello long-context con digest di *tutti* i capitoli.

---

## 6. Pipeline del task "paragrafo"

```
AnalisiSlide (visione, cache)      → schede slide
        ↓
PianificaStruttura (ragionamento)  → titoli/scaletta paragrafi capitolo
        ↓ per ogni paragrafo:
Contesto (locale, gratis)          → budget assembler
        ↓
Draft (scrittura)                  → codice python
        ↓
Valida (AST, già esistente)        → ok? → Commit
        ↓ errore
AutoRipara (scrittura leggera)     → patch → Valida (max 3 tentativi)
        ↓ ancora errore
Escalation (ragionamento)          → ultimo tentativo con modello forte
        ↓ fallisce
Fallback manuale                   → codice nel textbox, utente decide
```

Commit sicuro: mai sovrascrittura automatica di paragrafo esistente;
in modifica, l'output va in `paragrafo_XX._bozza.py` e l'utente approva
con "Salva" (passaggio obbligatorio: l'UMANO resta gate finale).

UI: selettore segmentato Manuale/Assistita; in Assistita il pulsante
"Copia regole" diventa "Genera con AI"; barra di avanzamento con modello
attivo, token spesi oggi, ETA; log consultabile dei cambi-modello.

---

## 7. Sicurezza e privacy

- Chiavi API solo in `python-dotenv` (`.env` fuori repo) o variabili
  d'ambiente; mai nei log.
- Le slide contengono materiale didattico: default = nessun provider
  senza chiave attivato finché l'utente non dà esplicito consenso;
  Ollama locale sempre disponibile come opzione zero-cloud.
- Input del modello trattato come inerte: output accettato solo se
  `valida_contenuto()` (AST) passa; nient'altro viene eseguito.
- Rate-limit locale proprio, per non martellare i provider.

---

## 8. Roadmap proposta

| Fase | Contenuto | Dipendenze |
|---|---|---|
| A (ora) | Bozza moduli `app/core/ai/*` + test stima token/router | nessuna |
| B | Provider adapter reali (httpx) + onboarding chiavi nelle impostazioni | httpx (già presente) |
| C | UI Manuale/Assistita + pipeline draft→valida→ripara per 1 paragrafo | B |
| D | Visione: analisi slide con cache su disco | B |
| E | Digest/contesto multi-paragrafo, pianificazione capitolo | C |
| F | Estrazione figure semi-automatica (crop via bounding box dal modello vision) | D |
| G | Bilanciamento quote multi-provider, telemetry locale | B |

---

## 9. Rischi aperti / decisioni da prendersi insieme

1. Le quote gratuite cambiano spesso: il catalogo va tenuto in un JSON
   separato aggiornabile senza rilascio, con valori conservativi.
2. Gemini free tier ha finestre orarie oltre che giornaliere: il router
   deve leggere gli header, non fidarsi solo del budget.
3. Output >3000 parole può troncare: serve continuation automatica
   (riprendi da `finish_reason=length`), da testare per provider.
4. Ollama locale: qualità incerta su questi pattern — valutare se
   tenerlo solo per riparazioni.
5. I nomi dei modelli nel catalogo vanno ricontrollati contro i listini
   live dei provider prima della Fase B.
