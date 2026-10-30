# -*- coding: utf-8 -*-
"""
pipeline.py - Orchestratore della generazione assistita (bozza).

Stato dell'arte del task "paragrafo":

    Draft -> Valida (AST) -> [AutoRipara a patch x3] -> [Escalation] -> Fallback

Il provider reale verra' collegato in Fase B; qui la pipeline accetta un
`provider` iniettabile (funzione `chiama(modello, messaggi, max_tokens)`),
cosi' e' gia' testabile con stub e mantiene il contratto definitivo.

Regola d'oro: l'output AI non viene mai scritto su file senza passare da
valida_contenuto(); in modifica si scrive come _bozza e l'umano approva.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from app.core.ai.catalogo import (Modello, SCRITTURA, RAGIONAMENTO, LOCAL,
                                  ESCALATION)
from app.core.ai.prompt import (pattern_compresso, costruisci_messaggi,
                                innesta_boilerplate, ISTRUZIONE_SOLO_CORPO,
                                statico_per_scrittura)
from app.core.ai.guida_autore import vincoli_operativi
from app.core.ai.router import (Router, OK, QUOTA_ESAURITA, ERRORE_RETE,
                                QuotaEsauritaException)
from app.core.ai.tokeni import stima_token

# firma del provider: (modello, messaggi, max_tokens) -> (testo, token_usati, esito)
Provider = Callable[[Modello, list[dict], int], tuple[str, int, str]]

MAX_TENTATIVI_RIPARAZIONE = 3

MARCATORE_PATCH = "@@SOSTITUISCI:"


@dataclass
class EsitoTask:
    ok: bool
    contenuto: str | None = None
    modello_finale: str | None = None
    tentativi: int = 0
    cambi_modello: list[str] = field(default_factory=list)
    errore: str | None = None
    token_totali: int = 0


def _estrai_codice(testo: str) -> str:
    """Il modello a volte ignora l'istruzione 'solo codice': ripuliamo."""
    from app.core.paragrafo import pulisci_codice_markdown
    t = pulisci_codice_markdown(testo)
    # se ci sono piu' blocchi, prendiamo il piu' lungo (il modulo vero)
    return t.strip() + "\n"


def _applica_patch(contenuto: str, patch: str) -> str:
    """Patch minimale: il modello restituisce blocchi

        @@SOSTITUISCI: <frammento-esatto-da-sostituire>
        >>>
        <sostituto>

    separati da righe vuote. Evita di rigenerare tutto il paragrafo."""
    out = contenuto
    for blocco in patch.split(MARCATORE_PATCH)[1:]:
        righe = blocco.strip().splitlines()
        if not righe or ">>>" not in righe:
            continue
        i = righe.index(">>>")
        cerca = "\n".join(righe[:i]).strip()
        sostituisci = "\n".join(righe[i + 1:]).strip()
        if cerca and cerca in out:
            out = out.replace(cerca, sostituisci, 1)
    return out


def genera_paragrafo_assistito(
    *, router: Router, provider: Provider, contesto_blocchi: list[str],
    pattern_completo: str, titolo_paragrafo: str,
    valida_fn: Callable[[str], dict],
    budget_contesto_tok: int = 24_000,
    istruzione_task: str | None = None,
) -> EsitoTask:
    """Pipeline completa per UN paragrafo. Restituisce EsitoTask; il chiamante
    UI decide commit/bozza. Nessun file toccato qui.

    `istruzione_task` opzionale: consente task diversi dal "scrivi da zero"
    (es. rigenerazione guidata con istruzioni dell'utente, vedi rigenera.py)
    riusando lo stesso ciclo draft->valida->auto-ripara->escalation."""
    esito = EsitoTask(ok=False)
    # primo draft: guida autore + manuale tecnico (regole intere, cache-friendly)
    statico = statico_per_scrittura(pattern_completo)
    messaggio_task = (istruzione_task or vincoli_operativi(titolo_paragrafo)) \
        + "\n" + ISTRUZIONE_SOLO_CORPO
    messaggi, _cache_key = costruisci_messaggi(
        statico, contesto_blocchi, messaggio_task)

    classe_corrente = SCRITTURA
    esclusi: list[str] = []
    for tentativo in range(MAX_TENTATIVI_RIPARAZIONE + 2):
        try:
            modello = router.scegli(classe_corrente,
                                    token_stimati=stima_token_messaggi_safe(messaggi))
        except QuotaEsauritaException as e:
            if classe_corrente == SCRITTURA:
                # tenta il fallback locale prima di arrendersi
                try:
                    modello = router.scegli(LOCAL)
                except QuotaEsauritaException:
                    esito.errore = str(e)
                    return esito
            else:
                esito.errore = str(e)
                return esito

        esito.cambi_modello.append(modello.id)
        max_out = min(modello.max_output, 8_192)
        testo, tok, ris = provider(modello, messaggi, max_out)
        router.registra_esito(modello, ris, tok)
        esito.token_totali += tok
        esito.tentativi = tentativo + 1

        if ris == QUOTA_ESAURITA:
            esclusi.append(modello.id)
            continue                      # stesso prompt, modello nuovo
        if ris != OK:
            continue                      # cooldown gestito dal router

        contenuto = innesta_boilerplate(_estrai_codice(testo))
        val = valida_fn(contenuto)
        if val.get("ok"):
            esito.ok = True
            esito.contenuto = contenuto
            esito.modello_finale = modello.id
            return esito

        # --- auto-riparazione a patch (token minimi) ---
        esito.errore = val.get("errore")
        messaggi = costruisci_messaggi(
            pattern_compresso(),  # solo il contratto: riparazione economica
            [f"Codice attuale:\n{contenuto[:6_000]}",
             f"Errore di validazione: {val.get('errore')}\n"
             f"Dettagli: {val.get('dettagli')}"],
            "Correggi con patch nel formato "
            f"{MARCATORE_PATCH}<frammento>\n>>>\n<sostituto>. "
            "Solo le parti necessarie.")
        classe_corrente = LOCAL if tentativo >= 1 else SCRITTURA

        # escalation finale: modello forte di ragionamento
        if tentativo == MAX_TENTATIVI_RIPARAZIONE:
            classe_corrente = ESCALATION.get(SCRITTURA, RAGIONAMENTO)

    # ultima chance: ricomincia da zero con patch applicate al vecchio testo
    return esito


def stima_token_messaggi_safe(messaggi: list[dict]) -> int:
    from app.core.ai.tokeni import stima_token_messaggi
    try:
        return stima_token_messaggi(messaggi)
    except Exception:
        return 8_000  # prudente


def continua_se_troncato(provider: Provider, modello: Modello,
                         messaggi: list[dict], parziale: str,
                         max_richieste: int = 3) -> tuple[str, int]:
    """Continuazione automatica per output tagliati (finish_reason=length):
    si ri-invia il coda del parziale chiedendo di riprendere esattamente."""
    testo = parziale
    token = 0
    for _ in range(max_richieste):
        msg = messaggi + [
            {"role": "assistant", "content": testo[-3_000:]},
            {"role": "user", "content":
             "Riprendi ESATTAMENTE da dove ti sei interrotto, senza "
             "ripetere nulla e senza commenti."},
        ]
        pezzo, tok, ris = provider(modello, msg, modello.max_output)
        token += tok
        if ris != OK or not pezzo.strip():
            break
        testo += pezzo
        if len(pezzo.strip()) < modello.max_output * 2:  # stima fine naturale
            break
    return testo, token
