# -*- coding: utf-8 -*-
"""
build_report.py - Struttura per raccogliere problemi di build.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


LIVELLO_WARN = "warn"
LIVELLO_ERRORE = "errore"

ORIGINE_MOTORE = "motore"
ORIGINE_PARAGRAFO = "paragrafo"
ORIGINE_FLOWABLE = "flowable"
ORIGINE_SISTEMA = "sistema"


@dataclass
class Problema:
    livello: str
    origine: str
    contesto: str
    messaggio: str
    dettaglio: str = ""

    def etichetta(self) -> str:
        prefisso = "X" if self.livello == LIVELLO_ERRORE else "!"
        return f"[{prefisso}] {self.contesto}: {self.messaggio}"


@dataclass
class BuildReport:
    libro: str
    pdf_path: Path | None = None
    ok: bool = False
    problemi: list[Problema] = field(default_factory=list)
    n_paragrafi_ok: int = 0
    n_paragrafi_falliti: int = 0
    durata_sec: float = 0.0

    def aggiungi(self, livello, origine, contesto, messaggio, dettaglio=""):
        self.problemi.append(Problema(
            livello=livello, origine=origine,
            contesto=contesto, messaggio=messaggio, dettaglio=dettaglio,
        ))

    def warn(self, origine, contesto, messaggio, dettaglio=""):
        self.aggiungi(LIVELLO_WARN, origine, contesto, messaggio, dettaglio)

    def errore(self, origine, contesto, messaggio, dettaglio=""):
        self.aggiungi(LIVELLO_ERRORE, origine, contesto, messaggio, dettaglio)

    @property
    def n_errori(self):
        return sum(1 for p in self.problemi if p.livello == LIVELLO_ERRORE)

    @property
    def n_warn(self):
        return sum(1 for p in self.problemi if p.livello == LIVELLO_WARN)

    def riassunto(self) -> str:
        if not self.problemi:
            return "Nessun problema."
        parti = []
        if self.n_errori:
            parti.append(f"{self.n_errori} errori")
        if self.n_warn:
            parti.append(f"{self.n_warn} avvisi")
        return " / ".join(parti)