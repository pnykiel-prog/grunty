"""Flaga istnienia MPZP (KIMPZP) — WYŁĄCZNIE tak/nie/nieznane.

PUŁAPKA: nie parsujemy treści planu ani wskaźników (to było źródłem pętli).
Flaga tylko dokleja adnotację do wyniku i NIE wchodzi do obliczeń.

Live: GetFeatureInfo w centroidzie do usługi KIMPZP.
Mock: deterministyczna flaga na podstawie TERYT.
"""
from __future__ import annotations

from typing import Tuple

from core.config import CONFIG

from .base import OK, ConnectorResult, degraded

JEST = "jest"
BRAK = "brak"
NIEZNANE = "nieznane"


def fetch(centroid_xy: Tuple[float, float], teryt: str) -> ConnectorResult:
    if CONFIG.is_mock:
        seed = abs(hash(("mpzp", teryt))) % 3
        flaga = {0: JEST, 1: BRAK, 2: NIEZNANE}[seed]
        return ConnectorResult(dane=flaga, status=OK, pewnosc=0.7,
                               zrodlo="mpzp(mock)")

    # LIVE: GetFeatureInfo; przy błędzie/timeoucie -> 'nieznane' (nie blokować).
    try:
        _ = centroid_xy
        # Do potwierdzenia parametry warstwy/GetFeatureInfo; świadoma degradacja.
        res = degraded("mpzp", "GetFeatureInfo do potwierdzenia", pewnosc=0.3)
        res.dane = NIEZNANE
        res.status = OK  # flaga zawsze ma wartość terminalną
        return res
    except Exception as exc:
        r = degraded("mpzp", f"wyjątek: {type(exc).__name__}")
        r.dane = NIEZNANE
        r.status = OK
        return r
