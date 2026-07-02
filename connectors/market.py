"""Konektor rynku — najem długoterminowy / sprzedaż + reguła wystarczalności.

Reguła wystarczalności: drabina o maks. 3 szczeblach (lokalny -> gminny ->
regionalny). Wspinamy się dopóki liczba próbek < progu N. Im niższy szczebel
zaspokoił próg, tym wyższa pewność. Filtr: tylko najem długoterminowy.

Z rynku wyliczamy też siłę luki cenowej (do popytu zewnętrznego).
Mock: deterministyczne dane offline. Live: świadoma degradacja (źródła TBD).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from core.config import CONFIG

from .base import OK, ConnectorResult, degraded

# poziom referencyjny ceny sprzedaży (proxy progu opłacalności podaży), zł/m2
_CENA_REFERENCYJNA = 9000.0


@dataclass
class Rynek:
    czynsz_m2: float          # najem długoterminowy, zł/m2/mc
    cena_sprzedaz_m2: float    # zł/m2
    probki: int               # liczba próbek zebranych na użytym szczeblu
    szczebel: int             # 0=lokalny, 1=gminny, 2=regionalny
    luka_cenowa: float        # siła luki cenowej (0..1)


def _mock_szczebel(teryt: str, szczebel: int) -> Tuple[float, float, int]:
    """Zwraca (czynsz, cena_sprzedaz, liczba_probek) dla danego szczebla."""
    s = abs(hash((teryt, szczebel)))
    # wyższy szczebel = więcej próbek (szerszy zasięg), ale mniej precyzyjny
    probki = (s % 4) + szczebel * 4          # szczebel 0: 0..3, 1: 4..7, 2: 8..11
    czynsz = 28.0 + (s % 22)                  # 28..49 zł/m2/mc
    cena = 6500.0 + (s % 4500)                # 6500..10999 zł/m2
    return round(czynsz, 2), round(cena, 2), probki


def fetch(teryt: str) -> ConnectorResult:
    prog = CONFIG.market.prog_probek
    max_szczebli = CONFIG.market.drabina_max

    if not CONFIG.is_mock:
        # LIVE: agregatory ofert wymagają potwierdzenia źródeł/licencji.
        return degraded("market", "źródła ofert do potwierdzenia; degradacja", pewnosc=0.3)

    # drabina wystarczalności — jedna pętla ograniczona max_szczebli (bez rekurencji)
    zebrane = 0
    uzyty_szczebel = 0
    czynsz = cena = 0.0
    for szczebel in range(max_szczebli):
        czynsz, cena, probki = _mock_szczebel(teryt, szczebel)
        zebrane += probki
        uzyty_szczebel = szczebel
        if zebrane >= prog:
            break

    luka = max(0.0, min(1.0, (_CENA_REFERENCYJNA - cena) / _CENA_REFERENCYJNA + 0.5))
    dane = Rynek(czynsz_m2=czynsz, cena_sprzedaz_m2=cena, probki=zebrane,
                 szczebel=uzyty_szczebel, luka_cenowa=round(luka, 3))

    # pewność maleje z użytym szczeblem i przy niedoborze próbek
    pewnosc = 0.85 - 0.2 * uzyty_szczebel
    flagi = []
    if zebrane < prog:
        pewnosc = min(pewnosc, 0.45)
        flagi.append("market: niewystarczające dane po wyczerpaniu drabiny")
    return ConnectorResult(dane=dane, status=OK, pewnosc=round(pewnosc, 3),
                           zrodlo="market(mock)", flagi=flagi)
