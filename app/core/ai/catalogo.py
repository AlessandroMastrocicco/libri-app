# -*- coding: utf-8 -*-
"""
catalogo.py - Catalogo dei modelli AI gratuiti disponibili, con classi di
capacita' e budget giornalieri conservativi (bozza).

I valori di quota sono STIME conservative basate sui free tier pubblici
(documentati dai provider a ottobre 2026) e vanno verificati a runtime con
gli header x-ratelimit-* quando disponibili. Il catalogo sara' reso
aggiornabile via JSON remoto nella Fase B (vedi docs/BOZZA_SISTEMA_AI.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ======================================================================
# Classi di compito: ogni task della pipeline dichiara la classe minima
# necessaria; il router non scende mai sotto quella soglia.
# ======================================================================

VISIONE_PESANTE = "visione_pesante"   # analisi slide complesse: diagrammi, formule
VISIONE_LEGGERA = "visione_leggera"   # slide testuali, indicizzazione batch
RAGIONAMENTO    = "ragionamento"      # struttura capitoli, coerenza, scalette
SCRITTURA       = "scrittura"         # codice paragrafo, eserciziari
LOCAL           = "locale"            # riparazioni minori, fallback offline

CLASSI = (VISIONE_PESANTE, VISIONE_LEGGERA, RAGIONAMENTO, SCRITTURA, LOCAL)

# Ordine di escalation tra classi per lo stesso tipo di lavoro.
ESCALATION = {
    LOCAL: SCRITTURA,
    SCRITTURA: RAGIONAMENTO,
    VISIONE_LEGGERA: VISIONE_PESANTE,
}


@dataclass(frozen=True)
class Modello:
    """Descrizione statica di un modello gratuito nel catalogo."""
    id: str                 # "provider/modello", es. "groq/llama-3.3-70b"
    provider: str           # groq | gemini | mistral | openrouter | ...
    nome: str               # nome esposto al modello dall'API
    classi: tuple[str, ...] # classi di compito supportate
    contesto: int           # finestra di contesto in token (input+output)
    max_output: int         # max_tokens consigliato
    vision: bool = False    # accetta immagini
    rpmd: int = 0           # richieste/minuto (stima, usata solo come hint)
    tpm: int = 0            # token/minuto (stima)
    quota_giorno_richieste: int = 0     # 0 = nessuna quota nota / illimitato
    quota_giorno_token: int = 0         # 0 = sconosciuta (il router usa allora
                                        # il limite delle richieste)
    priorita: int = 50      # 1 = preferito a parita' di condizioni
    note: str = ""

    @property
    def chiave(self) -> str:
        return self.id


# ======================================================================
# Catalogo (bozza). Nomi e quote da ricontrollare contro i listini live
# prima della Fase B di integrazione.
# ======================================================================

MODELLI: tuple[Modello, ...] = (
    # ---------------- Groq (free tier generoso, velocita' elevata) -----
    Modello("groq/llama-3.3-70b-versatile", "groq", "llama-3.3-70b-versatile",
             (SCRITTURA,), contesto=131_072, max_output=8_192,
             quota_giorno_richieste=280, quota_giorno_token=100_000,
             priorita=10, note="cavallo di battaglia per i draft"),
    Modello("groq/llama-4-scout-17b-16e-instruct", "groq",
             "llama-4-scout-17b-16e-instruct",
             (VISIONE_PESANTE, VISIONE_LEGGERA), contesto=131_072,
             max_output=8_192, vision=True,
             quota_giorno_richieste=350, quota_giorno_token=100_000,
             priorita=20, note="visione veloce su slide dense"),
    Modello("groq/qwen-qwq-32b", "groq", "qwen-qwq",
             (RAGIONAMENTO,), contesto=131_072, max_output=8_192,
             quota_giorno_richieste=180, quota_giorno_token=100_000,
             priorita=20, note="reasoning aperto, scalette capitolo"),
    Modello("groq/moonshotai-kimi-k2-instruct", "groq",
             "moonshotai/kimi-k2-instruct",
             (RAGIONAMENTO, SCRITTURA), contesto=131_072, max_output=8_192,
             quota_giorno_richieste=120, quota_giorno_token=100_000,
             priorita=30),
    Modello("groq/meta-llama-freedom-llama3.3-70b-v", "groq",
             "meta-llama/llama-3.3-70b-overprovisioned",
             (VISIONE_LEGGERA,), contesto=131_072, max_output=8_192,
             vision=False, quota_giorno_richieste=100,
             quota_giorno_token=100_000, priorita=60,
             note="placeholder visione leggera, da confermare"),

    # ------------- Google Gemini API (free tier, finestre orarie) ------
    Modello("gemini/gemini-2.5-flash", "gemini", "gemini-2.5-flash",
             (VISIONE_PESANTE, SCRITTURA, RAGIONAMENTO),
             contesto=1_048_576, max_output=8_192, vision=True,
             quota_giorno_richieste=100, quota_giorno_token=200_000,
             priorita=15, note="1M contesto; limiti anche orari: leggere headers"),
    Modello("gemini/gemini-2.0-flash-lite", "gemini", "gemini-2.0-flash-lite",
             (VISIONE_LEGGERA, SCRITTURA), contesto=1_048_576,
             max_output=8_192, vision=True,
             quota_giorno_richieste=200, quota_giorno_token=200_000,
             priorita=25, note="economico per batch di slide semplici"),
    Modello("gemini/gemini-2.5-pro", "gemini", "gemini-2.5-pro",
             (RAGIONAMENTO, VISIONE_PESANTE), contesto=1_048_576,
             max_output=8_192, vision=True,
             quota_giorno_richieste=10, quota_giorno_token=100_000,
             priorita=40, note="riservato ai piccoli task difficili"),

    # ------------------ Mistral La Plateforme (free tier) --------------
    Modello("mistral/mistral-small-latest", "mistral", "mistral-small-latest",
             (SCRITTURA, VISIONE_LEGGERA), contesto=131_072,
             max_output=8_192, vision=True,
             quota_giorno_richieste=120, quota_giorno_token=60_000,
             priorita=45),
    Modello("mistral/magistral-medium-latest", "mistral",
             "magistral-medium-latest", (RAGIONAMENTO, VISIONE_PESANTE),
             contesto=131_072, max_output=8_192, vision=True,
             quota_giorno_richieste=50, quota_giorno_token=60_000,
             priorita=55, note="reasoning + visione, quota scarsa"),

    # ------- OpenRouter (aggregatore: modelli .free senza carta) --------
    Modello("openrouter/meta-llama/llama-3.3-70b-instruct:free", "openrouter",
             "meta-llama/llama-3.3-70b-instruct:free",
             (SCRITTURA, RAGIONAMENTO), contesto=131_072, max_output=8_192,
             quota_giorno_richieste=50, quota_giorno_token=50_000,
             priorita=35, note="jolly quando gli altri sono esauriti"),
    Modello("openrouter/qwen/qwen3-coder:free", "openrouter",
             "qwen/qwen3-coder:free", (SCRITTURA,), contesto=131_072,
             max_output=8_192, quota_giorno_richieste=50,
             quota_giorno_token=50_000, priorita=30,
             note="ottimo per codice python strutturato"),
    Modello("openrouter/google/gemini-2.0-flash-exp:free", "openrouter",
             "google/gemini-2.0-flash-exp:free",
             (VISIONE_PESANTE, VISIONE_LEGGERA), contesto=1_000_000,
             max_output=8_192, vision=True, quota_giorno_richieste=20,
             quota_giorno_token=50_000, priorita=50),

    # ---------------------- Cerebras (velocita' estrema) ----------------
    Modello("cerebras/qwen-3-32b", "cerebras", "qwen3-32b",
             (SCRITTURA,), contesto=131_072, max_output=8_192,
             quota_giorno_richieste=1_000, quota_giorno_token=500_000,
             priorita=12, note="1M tok/giorno: ottimo per riparazioni a patch"),

    # ----------------------- SambaNova ---------------------------------
    Modello("sambanova/DeepSeek-R1-distill-qwen-32b", "sambanova",
             "DeepSeek-R1-Distill-Qwen-32B", (RAGIONAMENTO,),
             contesto=131_072, max_output=8_192,
             quota_giorno_richieste=60, quota_giorno_token=100_000,
             priorita=60),

    # ----------------------- GitHub Models ------------------------------
    Modello("github/azure-openai-gpt-4o-mini", "github",
             "OpenAI:gpt-4o-mini", (SCRITTURA, VISIONE_LEGGERA),
             contesto=128_000, max_output=4_096, vision=True,
             quota_giorno_richieste=10, quota_giorno_token=15_000,
             priorita=80, note="quota molto bassa: solo emergenze"),

    # ----------------------- DeepSeek API -------------------------------
    Modello("deepseek/deepseek-chat", "deepseek", "deepseek-chat",
             (SCRITTURA, RAGIONAMENTO), contesto=64_000, max_output=8_192,
             quota_giorno_richieste=0, quota_giorno_token=0,
             priorita=70, note="pay-as-you-go con crediti iniziali: opzionale"),

    # ----------------------- Ollama locale (zero cloud) -----------------
    Modello("ollama/qwen3:14b", "ollama", "qwen3:14b",
             (LOCAL, SCRITTURA), contesto=32_768, max_output=8_192,
             quota_giorno_richieste=0, quota_giorno_token=0,
             priorita=90, note="fallback offline; qualita' da valutare"),
    Modello("ollama/llama3.2-vision:11b", "ollama", "llama3.2-vision:11b",
             (LOCAL, VISIONE_LEGGERA), contesto=128_000, max_output=8_192,
             vision=True, quota_giorno_richieste=0, quota_giorno_token=0,
             priorita=95, note="visione senza inviare dati al cloud"),
)


def modelli_per_classe(classe: str) -> list[Modello]:
    return [m for m in MODELLI if classe in m.classi]


# ----------------------------------------------------------------------
# Preferenze di affinita' per la scelta strategica (scelta.py).
# Un solo posto dove dichiarare "chi e' il migliore per cosa": se un
# provider cambia listino basta aggiornare queste tre costanti.
# ----------------------------------------------------------------------
MODELLO_VISIONE_PREFERITO = "gemini/gemini-2.5-flash"        # slide dense
MODELLO_RAGIONAMENTO_PREFERITO = "deepseek/deepseek-chat"    # scalette capitoli
MODELLO_SCRITTURA_PREFERITO = "groq/llama-3.3-70b-versatile"  # draft paragrafi


def trova_modello(chiave: str) -> Modello | None:
    for m in MODELLI:
        if m.id == chiave:
            return m
    return None


def chiavi_con_vision() -> list[str]:
    return [m.id for m in MODELLI if m.vision]
