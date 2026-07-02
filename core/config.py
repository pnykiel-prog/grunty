"""Konfiguracja M1 (config-not-code).

Wszystkie parametry, limity anty-pętla, słowniki, id zmiennych BDL oraz
przełącznik trybu (mock/live) trzymamy tutaj. Kod domenowy i konektory nie
zawierają "magicznych liczb" — czytają je stąd.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict


# --- tryb pracy -------------------------------------------------------------
# mock  -> pełny, deterministyczny wynik offline (bez sieci)
# live  -> realne wywołania konektorów (jedna próba + timeout)
MODE = os.environ.get("GRUNTY_MODE", "mock").strip().lower()


@dataclass(frozen=True)
class Endpoints:
    uldk: str = "https://uldk.gugik.gov.pl/"
    bdl: str = "https://bdl.stat.gov.pl/api/v1"
    # Usługi GUGiK (WMS/WFS/WCS) — dokładne warstwy do ustalenia z GetCapabilities.
    bdot_wfs: str = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WFS/PobierzBudynki"
    nmt_wcs: str = "https://mapy.geoportal.gov.pl/wss/service/PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF"
    kimpzp_wms: str = "https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaMiejscowychPlanowZagospodarowaniaPrzestrzennego"


@dataclass(frozen=True)
class AntiLoop:
    """Limity przekrojowe — jedna próba, timeout, brak ponawiania."""
    http_timeout_s: float = 8.0
    max_attempts: int = 1          # zakaz ponawiania
    allow_recursion: bool = False  # zakaz rekurencji


@dataclass(frozen=True)
class PotentialParams:
    bufor_bdot_m: float = 200.0        # promień bufora sąsiedztwa
    pum_efficiency: float = 0.80       # PUM / powierzchnia całkowita
    intensywnosc_min: float = 0.3      # ograniczenia sanity
    intensywnosc_max: float = 3.5
    # duży spadek obniża potencjał; mapowanie spadku [%] -> korekta [0..1]
    spadek_prog_lagodny: float = 8.0   # < prog: bez kary
    spadek_prog_stromy: float = 20.0   # > prog: maksymalna kara
    korekta_spadku_min: float = 0.55
    # typowy metraż mieszkania wg profilu (m2)
    metraz_mlodzi: float = 45.0
    metraz_seniorzy: float = 58.0
    # fallback typowej liczby kondygnacji, gdy BDOT nie zwraca wysokości
    kondygnacje_fallback: float = 3.0


@dataclass(frozen=True)
class DemandParams:
    # wagi łączenia popytu wewnętrznego / zewnętrznego
    waga_wew: float = 0.6
    waga_zew: float = 0.4
    # progi werdyktu (znormalizowany popyt 0..1)
    prog_wysoki: float = 0.6
    prog_sredni: float = 0.35


@dataclass(frozen=True)
class MarketParams:
    # reguła wystarczalności: drabina o maks. 3 szczeblach, próg N próbek
    drabina_max: int = 3
    prog_probek: int = 5
    filtr_najem_dlugoterminowy: bool = True


@dataclass(frozen=True)
class BdlConfig:
    """Zmienne BDL odkrywamy przez subjects/variables i zapisujemy tutaj.

    UWAGA (pułapka): jednostka BDL != kod gminy z działki. Najpierw mapujemy
    gminę (TERYT) na 12-znakowy identyfikator jednostki, potem pobieramy dane.
    var-id NIE hardkodujemy na ślepo — poniższe to zapisane wyniki odkrycia,
    z jawnie oznaczonym rokiem danych.
    """
    rok_danych: int = 2023
    unit_level_gmina: int = 6
    # odkryte var-id (subjects -> variables); do uzupełnienia po odkryciu live.
    var_ludnosc_20_39: str = os.environ.get("BDL_VAR_LUD_20_39", "")
    var_ludnosc_65p: str = os.environ.get("BDL_VAR_LUD_65P", "")
    var_saldo_migracji: str = os.environ.get("BDL_VAR_MIGRACJA", "")
    var_bezrobocie: str = os.environ.get("BDL_VAR_BEZROBOCIE", "")
    var_zasob_mieszkaniowy: str = os.environ.get("BDL_VAR_ZASOB_MIESZ", "")
    # cache: TERYT gminy (6 cyfr) -> identyfikator jednostki BDL (12 znaków)
    unit_cache: Dict[str, str] = field(default_factory=dict)
    client_id: str = os.environ.get("BDL_CLIENT_ID", "")


@dataclass(frozen=True)
class Config:
    mode: str = MODE
    endpoints: Endpoints = field(default_factory=Endpoints)
    antiloop: AntiLoop = field(default_factory=AntiLoop)
    potential: PotentialParams = field(default_factory=PotentialParams)
    demand: DemandParams = field(default_factory=DemandParams)
    market: MarketParams = field(default_factory=MarketParams)
    bdl: BdlConfig = field(default_factory=BdlConfig)

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"


CONFIG = Config()
