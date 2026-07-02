"""Konektor ULDK (GUGiK) — geometria działki w EPSG:2180.

Live:
    GET https://uldk.gugik.gov.pl/?request=GetParcelById
        &id=<WWPPGG_R.XXXX.NDZ>&result=geom_wkt&srid=2180
    odpowiedź: linia 1 = status (0=ok), linia 2 = geometria WKT.
    status != 0 -> działka nieznaleziona (terminal, NIE ponawiać).

Mock: deterministyczny kwadrat 30 m w 2180 na podstawie numeru działki,
tak by sąsiednie numery przylegały (numer k i k+1 stykają się bokiem).
"""
from __future__ import annotations

from core.config import CONFIG
from core.schemas import ParcelId

from .base import OK, NOT_FOUND, ConnectorResult, degraded, http_get

# baza współrzędnych mocka (dowolny punkt w PL-1992); istotna jest tylko
# geometria względna: pole i przyleganie.
_MOCK_BASE_X = 638000.0
_MOCK_BASE_Y = 486000.0
_MOCK_SIDE = 30.0  # -> działka 900 m²


def _leading_int(numer: str) -> int:
    head = numer.split("/")[0]
    try:
        return int(head)
    except ValueError:
        return abs(hash(numer)) % 1000


def _suffix_int(numer: str) -> int:
    parts = numer.split("/")
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


def _mock_wkt(pid: ParcelId) -> str:
    # x wg numeru głównego (sąsiednie numery stykają się bokiem),
    # y wg sufiksu po '/' (np. 142/7 i 142/8 przylegają pionowo, są odrębne).
    kx = _leading_int(pid.numer)
    ky = _suffix_int(pid.numer)
    x0 = _MOCK_BASE_X + kx * _MOCK_SIDE
    y0 = _MOCK_BASE_Y + ky * _MOCK_SIDE
    x1 = x0 + _MOCK_SIDE
    y1 = y0 + _MOCK_SIDE
    return (
        f"POLYGON(({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"
    )


def _parse_live(body: str) -> ConnectorResult:
    # log surowej odpowiedzi przed parsowaniem
    lines = [ln for ln in body.replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        return degraded("uldk", "pusta odpowiedź")
    status = lines[0].strip()
    if status != "0":
        return ConnectorResult(
            dane=None, status=NOT_FOUND, pewnosc=0.0, zrodlo="uldk",
            flagi=[f"uldk: status={status} (nieznaleziona)"],
            surowa_odpowiedz=body,
        )
    if len(lines) < 2:
        return degraded("uldk", "brak geometrii w odpowiedzi")
    wkt = lines[1].strip()
    return ConnectorResult(dane=wkt, status=OK, pewnosc=0.95, zrodlo="uldk",
                           surowa_odpowiedz=body)


def fetch(pid: ParcelId) -> ConnectorResult:
    """Zwraca geometrię działki (WKT). Jedna próba + timeout."""
    if CONFIG.is_mock:
        # sentinel: numer 999 -> działka nieznaleziona (do demonstracji stanu S2)
        if _leading_int(pid.numer) == 999:
            return ConnectorResult(
                dane=None, status=NOT_FOUND, pewnosc=0.0, zrodlo="uldk(mock)",
                flagi=[f"uldk(mock): status=nieznaleziona ({pid.numer})"])
        return ConnectorResult(dane=_mock_wkt(pid), status=OK, pewnosc=0.9,
                               zrodlo="uldk(mock)")
    try:
        resp = http_get(
            CONFIG.endpoints.uldk,
            params={
                "request": "GetParcelById",
                "id": pid.uldk_id(),
                "result": "geom_wkt",
                "srid": "2180",
            },
        )
        if resp.status_code != 200:
            return degraded("uldk", f"HTTP {resp.status_code}")
        return _parse_live(resp.text)
    except Exception as exc:  # jedna próba, degradacja, bez retry
        return degraded("uldk", f"wyjątek: {type(exc).__name__}")
