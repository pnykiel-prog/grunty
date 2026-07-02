"""Konektor NMT — średni spadek terenu na działce.

Duży spadek obniża potencjał (i osobno stanowi flagę dla profilu senioralnego).
Live: raster/WCS NMT w obszarze działki. Mock: deterministyczny spadek [%].
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry

from core.config import CONFIG

from .base import OK, ConnectorResult, degraded


@dataclass
class SpadekNMT:
    spadek_proc: float  # średni spadek terenu w procentach


def fetch(geom: BaseGeometry, teryt: str) -> ConnectorResult:
    if CONFIG.is_mock:
        seed = abs(hash(("nmt", teryt))) % 100
        spadek = round(2.0 + seed * 0.25, 2)  # 2%..~27%
        return ConnectorResult(dane=SpadekNMT(spadek_proc=spadek), status=OK,
                               pewnosc=0.8, zrodlo="nmt(mock)")

    # LIVE: pojedyncze zapytanie WCS o wycinek NMT, policz spadek; degradacja.
    try:
        _ = geom.bounds
        return degraded("nmt", "WCS NMT do potwierdzenia", pewnosc=0.3)
    except Exception as exc:
        return degraded("nmt", f"wyjątek: {type(exc).__name__}")
