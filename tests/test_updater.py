import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from app.core import updater


class TestControllaAggiornamenti(unittest.TestCase):
    def test_rileva_versione_github_piu_recente(self):
        dati = {
            "version": "0.4.3",
            "url": "https://example.com/releases",
            "changelog": "Nuova funzione",
        }
        risposta = patch.object(
            updater,
            "urlopen",
            return_value=_Risposta(json.dumps(dati).encode("utf-8")),
        )
        with risposta:
            risultato = updater.controlla_aggiornamenti(Path("inesistente"))
        self.assertEqual(risultato, dati)

    def test_versione_corrente_non_avvisa(self):
        dati = {"version": updater.__version__}
        with patch.object(
            updater,
            "urlopen",
            return_value=_Risposta(json.dumps(dati).encode("utf-8")),
        ):
            self.assertIsNone(updater.controlla_aggiornamenti(Path("inesistente")))

    def test_usa_metadata_locale_se_github_non_raggiungibile(self):
        dati = {"version": "0.4.3", "url": "https://example.com/releases"}
        with tempfile.TemporaryDirectory() as directory:
            percorso = Path(directory) / "latest_version.json"
            percorso.write_text(json.dumps(dati), encoding="utf-8")
            with patch.object(updater, "urlopen", side_effect=URLError("offline")):
                risultato = updater.controlla_aggiornamenti(Path(directory))
        self.assertEqual(risultato["version"], "0.4.3")

    def test_ignora_versioni_non_valide(self):
        dati = {"version": "v0.4.1"}
        with patch.object(
            updater,
            "urlopen",
            return_value=_Risposta(json.dumps(dati).encode("utf-8")),
        ):
            self.assertIsNone(updater.controlla_aggiornamenti(Path("inesistente")))


class _Risposta:
    def __init__(self, contenuto):
        self.contenuto = contenuto

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.contenuto


if __name__ == "__main__":
    unittest.main()
