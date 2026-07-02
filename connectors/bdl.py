"""Konektor GUS BDL — demografia gminy.

Kolejność (live):
  1. Mapowanie gminy (TERYT) -> 12-znakowy identyfikator jednostki BDL (cache).
     PUŁAPKA: jednostka BDL != kod gminy z działki.
  2. Dobór zmiennych: var-id odkryte przez subjects/variables, zapisane w config
     (NIE hardkodować na ślepo), z jawnie oznaczonym rokiem danych.
  3. Pobranie: /data/by-unit/{unitId}?var-id=...&format=json&year=YYYY.

Anti-pętla: mapowanie i pobranie — po jednej próbie z timeoutem; brak danych ->
sygnały neutralne + niższa pewność (NIE blokować).

Mock: pełne, deterministyczne sygnały offline.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.config import CONFIG

from .base import OK, ConnectorResult, degraded, http_get


@dataclass
class DemografiaBDL:
    udzial_20_39: float     # udział grupy 20-39 lat (0..1)
    udzial_65p: float       # udział grupy 65+ (0..1)
    saldo_migracji: float   # saldo migracji na 1000 mieszkańców
    bezrobocie: float       # stopa bezrobocia (0..1)
    zasob_mieszkaniowy: float  # mieszkania / 1000 mieszk. (proxy napięcia)
    rok: int


def _neutralne(rok: int) -> DemografiaBDL:
    """Sygnały neutralne przy braku danych (degradacja, nie blokada)."""
    return DemografiaBDL(
        udzial_20_39=0.26, udzial_65p=0.19, saldo_migracji=0.0,
        bezrobocie=0.06, zasob_mieszkaniowy=380.0, rok=rok,
    )


def _mock_demografia(teryt: str, rok: int) -> DemografiaBDL:
    s = abs(hash(("bdl", teryt)))
    udzial_20_39 = 0.20 + (s % 15) / 100.0        # 0.20..0.34
    udzial_65p = 0.14 + ((s // 7) % 14) / 100.0   # 0.14..0.27
    saldo = ((s // 11) % 21) - 10                 # -10..+10 /1000
    bezrobocie = 0.03 + ((s // 13) % 8) / 100.0   # 0.03..0.10
    zasob = 320.0 + ((s // 17) % 120)             # 320..439
    return DemografiaBDL(
        udzial_20_39=round(udzial_20_39, 3),
        udzial_65p=round(udzial_65p, 3),
        saldo_migracji=float(saldo),
        bezrobocie=round(bezrobocie, 3),
        zasob_mieszkaniowy=float(zasob),
        rok=rok,
    )


# --- LIVE: mapowanie gminy -> jednostka BDL (cache w configu) --------------
def _map_unit(teryt: str) -> str | None:
    cache = CONFIG.bdl.unit_cache
    if teryt in cache:
        return cache[teryt]
    try:
        # wyszukanie jednostki po TERYT — jedna próba
        resp = http_get(
            f"{CONFIG.endpoints.bdl}/units/search",
            params={"name": teryt, "format": "json"},
            headers={"X-ClientId": CONFIG.bdl.client_id} if CONFIG.bdl.client_id else None,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        unit_id = results[0].get("id")
        if unit_id:
            cache[teryt] = unit_id  # cache w pamięci configu
        return unit_id
    except Exception:
        return None


def fetch(teryt: str) -> ConnectorResult:
    rok = CONFIG.bdl.rok_danych
    if CONFIG.is_mock:
        return ConnectorResult(dane=_mock_demografia(teryt, rok), status=OK,
                               pewnosc=0.8, zrodlo="bdl(mock)")

    # LIVE — krok 1: mapowanie
    unit_id = _map_unit(teryt)
    if not unit_id:
        r = degraded("bdl", "brak mapowania gminy->jednostka; sygnały neutralne", pewnosc=0.3)
        r.dane = _neutralne(rok)
        r.status = OK  # nie blokujemy pipeline'u
        return r

    # LIVE — krok 2: dobór zmiennych (z configu, odkryte wcześniej)
    var_ids = [v for v in (
        CONFIG.bdl.var_ludnosc_20_39, CONFIG.bdl.var_ludnosc_65p,
        CONFIG.bdl.var_saldo_migracji, CONFIG.bdl.var_bezrobocie,
        CONFIG.bdl.var_zasob_mieszkaniowy,
    ) if v]
    if not var_ids:
        r = degraded("bdl", "brak odkrytych var-id w configu; sygnały neutralne", pewnosc=0.3)
        r.dane = _neutralne(rok)
        r.status = OK
        return r

    # LIVE — krok 3: pobranie (jedna próba)
    try:
        params = [("format", "json"), ("year", str(rok))]
        params += [("var-id", v) for v in var_ids]
        resp = http_get(f"{CONFIG.endpoints.bdl}/data/by-unit/{unit_id}",
                        params=params,
                        headers={"X-ClientId": CONFIG.bdl.client_id} if CONFIG.bdl.client_id else None)
        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code}")
        # Mapowanie odpowiedzi na DemografiaBDL wymaga stabilnych var-id;
        # dopóki nie potwierdzone, oddajemy neutralne z odnotowaną degradacją.
        r = degraded("bdl", "mapowanie odpowiedzi var-id do potwierdzenia", pewnosc=0.4)
        r.dane = _neutralne(rok)
        r.status = OK
        r.surowa_odpowiedz = resp.text[:2000]
        return r
    except Exception as exc:
        r = degraded("bdl", f"pobranie nieudane: {type(exc).__name__}; neutralne", pewnosc=0.3)
        r.dane = _neutralne(rok)
        r.status = OK
        return r
