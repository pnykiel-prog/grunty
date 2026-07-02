"""Konektor BDOT10k — budynki sąsiedztwa (do algorytmicznego potencjału).

Liczymy w buforze wokół działki lokalną intensywność/pokrycie oraz typową
liczbę kondygnacji. PUŁAPKA: wysokości bywają niepełne -> fallback do typowej
kondygnacji z otoczenia i niższa pewność.

Live: WFS GUGiK (obrysy budynków w bboxie bufora). Mock: deterministyczne
sygnały otoczenia na podstawie TERYT gminy.
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from core.config import CONFIG
from geo import geometry as geo

from .base import OK, ConnectorResult, degraded


@dataclass
class SasiedztwoBDOT:
    intensywnosc: float      # przybliżona intensywność zabudowy otoczenia
    kondygnacje: float       # typowa liczba kondygnacji
    pokrycie: float          # udział pokrycia budynkami w buforze (0..1)
    wysokosci_pelne: bool    # czy dane wysokości były kompletne


def _mock_sasiedztwo(centroid_seed: int) -> SasiedztwoBDOT:
    # deterministyczna wariacja w rozsądnych granicach
    pokrycie = 0.20 + (centroid_seed % 30) / 100.0        # 0.20..0.49
    kondygnacje = 2.0 + (centroid_seed % 5)               # 2..6
    intensywnosc = round(pokrycie * kondygnacje, 3)
    # w mocku część przypadków ma niepełne wysokości (co ~3. gmina)
    wysokosci_pelne = (centroid_seed % 3) != 0
    return SasiedztwoBDOT(
        intensywnosc=intensywnosc,
        kondygnacje=float(kondygnacje),
        pokrycie=round(pokrycie, 3),
        wysokosci_pelne=wysokosci_pelne,
    )


def fetch(geom: BaseGeometry, teryt: str) -> ConnectorResult:
    """Zwraca sygnały sąsiedztwa z bufora wokół działki. Jedna próba."""
    if CONFIG.is_mock:
        seed = abs(hash(teryt)) % 997
        dane = _mock_sasiedztwo(seed)
        pewnosc = 0.85 if dane.wysokosci_pelne else 0.6
        flagi = [] if dane.wysokosci_pelne else ["bdot: wysokości niepełne — fallback kondygnacji"]
        return ConnectorResult(dane=dane, status=OK, pewnosc=pewnosc,
                               zrodlo="bdot(mock)", flagi=flagi)

    # LIVE: bufor -> bbox -> WFS GetFeature (jedna próba, degradacja przy braku)
    try:
        buf = geo.bufor(geom, CONFIG.potential.bufor_bdot_m)
        minx, miny, maxx, maxy = buf.bounds
        # Realne parsowanie GML/obrysów wymaga warstw ustalonych z GetCapabilities.
        # Do czasu potwierdzenia warstw degradujemy świadomie (bez pętli).
        _ = (minx, miny, maxx, maxy)
        return degraded("bdot", "warstwa WFS do potwierdzenia (GetCapabilities)", pewnosc=0.3)
    except Exception as exc:
        return degraded("bdot", f"wyjątek: {type(exc).__name__}")
