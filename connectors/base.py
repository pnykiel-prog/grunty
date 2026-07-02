"""Wspólny kontrakt konektorów.

Każdy konektor: ``fetch(...) -> ConnectorResult`` z polami (dane|None, status,
pewnosc). Jedna próba + timeout, degradacja przy błędzie, BEZ ponawiania i
rekurencji. Tryb mock zwraca pełny, deterministyczny wynik offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx

from core.config import CONFIG


# statusy konektora
OK = "ok"
DEGRADED = "degraded"     # brak danych / błąd — działamy dalej z niższą pewnością
NOT_FOUND = "not_found"   # zasób nie istnieje (terminal dla ULDK)


@dataclass
class ConnectorResult:
    dane: Optional[Any]
    status: str
    pewnosc: float
    zrodlo: str = ""
    flagi: list = field(default_factory=list)
    surowa_odpowiedz: Optional[str] = None  # log przed parsowaniem

    @property
    def ok(self) -> bool:
        return self.status == OK


def degraded(zrodlo: str, powod: str, pewnosc: float = 0.3) -> ConnectorResult:
    """Zdegradowany wynik — sygnalizuje brak danych bez blokowania pipeline'u."""
    return ConnectorResult(
        dane=None, status=DEGRADED, pewnosc=pewnosc, zrodlo=zrodlo,
        flagi=[f"{zrodlo}: {powod}"],
    )


def http_get(url: str, params: Optional[Dict[str, Any]] = None,
             headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Pojedyncze wywołanie GET z timeoutem. BEZ retry (anti-loop)."""
    timeout = CONFIG.antiloop.http_timeout_s
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        return client.get(url, params=params, headers=headers or {})
