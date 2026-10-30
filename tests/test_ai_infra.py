# -*- coding: utf-8 -*-
"""
test_ai_infra.py - Test della bozza di infrastruttura AI (Fase A).

Verificano i soli componenti deterministici: stima token, budget assembler,
router con quote, compressione pattern, digest locale, pipeline con provider
stub. Nessun accesso di rete.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.ai.tokeni import (stima_token, stima_token_messaggi,
                                troncava_per_righe, assembla_contesto,
                                BloccoContesto)
from app.core.ai.router import (Router, OK, QUOTA_ESAURITA,
                                QuotaEsauritaException)
from app.core.ai.catalogo import SCRITTURA, VISIONE_PESANTE, trova_modello
from app.core.ai.prompt import pattern_compresso, risparmio_stimato, \
    costruisci_messaggi, innesta_boilerplate
from app.core.ai.contesto import digest_paragrafo_locale, schede_pertinenti
from app.core.ai.pipeline import genera_paragrafo_assistito, _applica_patch


# ---------------------------------------------------------------- tokeni

def test_stima_token_ordine_grandezza():
    assert 20 <= stima_token("hello world " * 10) <= 50
    assert stima_token("") == 0
    # il CJK costa piu' del latino a pari lunghezza
    assert stima_token("漢字" * 20) > stima_token("ab" * 20)


def test_stima_token_messaggi_multimodale():
    msg = [{"role": "user", "content": [
        {"type": "text", "text": "ciao"},
        {"type": "image_url", "image_url": {"url": "x"}},
    ]}]
    tok = stima_token_messaggi(msg)
    assert tok > 1_000  # l'immagine pesa ~1100


def test_troncamento_non_spezza_righe():
    testo = "\n".join(f"riga numero {i} di prova" for i in range(200))
    taglio = troncava_per_righe(testo, 100)
    assert "[troncato]" in taglio
    assert all(r.startswith("riga numero") for r in taglio.splitlines()[:-1])


def test_budget_assembler_priorizza():
    blocchi = [
        BloccoContesto("indispensabile", "A" * 400, priorita=5,
                       comprimibile=False),
        BloccoContesto("media", "B" * 4_000, priorita=30),
        BloccoContesto("opzionale", "C" * 4_000, priorita=70),
    ]
    sel, usati = assembla_contesto(blocchi, budget=2_000, margine_uscita=500)
    nomi = {b.nome for b in sel}
    assert "indispensabile" in nomi
    assert "opzionale" not in nomi   # priorita' troppo bassa per entrare
    assert usati <= 1_500


# ---------------------------------------------------------------- router

def _router_tmp(tmp_path):
    return Router(path_stato=Path(tmp_path) / "_ai_quota.json")


def test_router_sceglie_il_migliore_disponibile(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _router_tmp(d)
        m = r.scegli(SCRITTURA, token_stimati=1_000)
        assert m is not None and SCRITTURA in m.classi


def test_router_switch_su_quota_esaurita(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _router_tmp(d)
        primo = r.scegli(SCRITTURA)
        # simula quota esaurita riportata dal provider
        r.registra_esito(primo, QUOTA_ESAURITA)
        secondo = r.scegli(SCRITTURA)
        assert secondo.id != primo.id          # switch automatico
        assert r.disponibile(primo) is False   # non lo riprova oggi


def test_router_precheck_token_evita_chiamata_inutile():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = _router_tmp(d)
        m = trova_modello("github/azure-openai-gpt-4o-mini")
        # chiede piu' token di quanti la quota giornaliera ne consenta
        assert r.disponibile(m, token_stimati=m.quota_giorno_token + 1) is False


def test_router_rollover_del_giorno():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        finto_adesso = {"t": datetime(2026, 10, 30, 23, 0, tzinfo=timezone.utc)}
        r = Router(path_stato=Path(d) / "q.json",
                   ora_adesso=lambda: finto_adesso["t"])
        m = r.scegli(SCRITTURA)
        r.registra_esito(m, QUOTA_ESAURITA)
        assert r.disponibile(m) is False
        # passa la mezzanotte UTC: le quote si rinnovano
        finto_adesso["t"] = finto_adesso["t"] + timedelta(hours=2)
        assert r.disponibile(m) is True


def test_router_quota_zero_tutti_pausa():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = Router(path_stato=Path(d) / "q.json")
        from app.core.ai.catalogo import modelli_per_classe
        for m in modelli_per_classe(VISIONE_PESANTE):
            r.registra_esito(m, QUOTA_ESAURITA)
        try:
            r.scegli(VISIONE_PESANTE, richiede_vision=True)
            assert False, "dovrebbe sollevare QuotaEsauritaException"
        except QuotaEsauritaException as e:
            assert "rollover" in str(e)


def test_router_persistenza(tmp_path=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "q.json"
        r1 = Router(path_stato=p)
        m = r1.scegli(SCRITTURA)
        r1.registra_esito(m, OK, token_usati=5_000)
        r2 = Router(path_stato=p)   # riavvio dell'app
        assert r2._stato(m.id).token == 5_000


# ---------------------------------------------------------------- prompt

def test_pattern_compresso_piu_corto_del_completo():
    from app.core.pattern_paragrafo import PATTERN_PARAGRAFO
    metrica = risparmio_stimato(PATTERN_PARAGRAFO)
    assert metrica["risparmio_pct"] >= 50
    assert metrica["pattern_compatto_tok"] < metrica["pattern_pieno_tok"]


def test_costruisci_messaggi_cache_key_stabile():
    m1, k1 = costruisci_messaggi("SYSTEM", ["ctx"], "task")
    m2, k2 = costruisci_messaggi("SYSTEM", ["ctx diverso"], "task")
    assert k1 == k2                      # statico invariato -> cache valida
    assert m1[0]["role"] == "system"     # blocco cacheabile sempre in testa


def test_innesto_boilerplate():
    corpo = "METADATI = {'titolo': 'X'}\ndef story():\n    return []\n"
    completo = innesta_boilerplate(corpo)
    assert "def figura(nome_file):" in completo
    assert "def story():" in completo


# ---------------------------------------------------------------- contesto

def test_digest_locale_da_codice():
    contenuto = (
        '"""\nIl Processo\n=========\n"""\n'
        'def story():\n'
        '    return [P("Il processo e\' un programma in esecuzione."),\n'
        '            definizione("PID", "Identificatore numerico del processo."),\n'
        '            figura("L1_S003_processo.png")]\n'
    )
    d = digest_paragrafo_locale(contenuto)
    assert d["titolo"] == "Il Processo"
    assert any("processo" in c.lower() for c in d["concetti"])
    assert "L1_S003_processo.png" in d["figure"]


def test_schede_pertinenti_selezione():
    schede = {
        "L1": [{"slide": 3, "titolo": "Schema del processo",
                "punti": ["stati del processo"]},
               {"slide": 9, "titolo": "Gestione memoria",
                "punti": ["heap stack"]}],
    }
    sel = schede_pertinenti(schede, ["processo"], max_schede=1)
    assert len(sel) == 1
    assert "processo" in json.dumps(sel).lower()


# ---------------------------------------------------------------- pipeline

def _valida_finta(contenuto):
    import ast
    try:
        ast.parse(contenuto)
    except SyntaxError as e:
        return {"ok": False, "errore": str(e)}
    return {"ok": True}


def test_pipeline_draft_ok():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = Router(path_stato=Path(d) / "q.json")
        buon_codice = ("METADATI = {'titolo': 'T'}\n"
                       "def story():\n    return []\n")

        def provider(modello, messaggi, max_tokens):
            return buon_codice, 900, OK

        esito = genera_paragrafo_assistito(
            router=r, provider=provider, contesto_blocchi=["ctx"],
            pattern_completo="REGOLE...", titolo_paragrafo="Test",
            valida_fn=_valida_finta)
        assert esito.ok and esito.tentativi == 1
        assert "def figura" in esito.contenuto  # boilerplate innestato


def test_pipeline_switch_dopo_quota_esaurita():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        r = Router(path_stato=Path(d) / "q.json")
        buoni = iter([QUOTA_ESAURITA, OK])
        codice = "def story():\n    return []\n"

        def provider(modello, messaggi, max_tokens):
            esito = next(buoni)
            return (codice, 500, esito) if esito == OK else ("", 0, esito)

        res = genera_paragrafo_assistito(
            router=r, provider=provider, contesto_blocchi=[],
            pattern_completo="R", titolo_paragrafo="X",
            valida_fn=_valida_finta)
        assert res.ok
        assert len(res.cambi_modello) == 2      # ha cambiato modello


def test_applica_patch():
    base = "def story():\n    return [P('vecchio')]\n"
    patch = "@@SOSTITUISCI:\nreturn [P('vecchio')]\n>>>\nreturn [P('nuovo')]\n"
    out = _applica_patch(base, patch)
    assert "nuovo" in out and "vecchio" not in out
