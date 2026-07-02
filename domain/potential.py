"""Domena: algorytmiczny (orientacyjny) potencjał zabudowy z sąsiedztwa.

    intensywność_otoczenia = f(BDOT: pokrycie/obrysy w buforze)
    kondygnacje_typowe      = z BDOT (lub fallback)
    korekta_spadku          = z NMT (duży spadek -> niżej)
    pow. całkowita ≈ pow. działki × intensywność × korekta_spadku
    PUM ≈ pow. całkowita × PUM_EFFICIENCY
    ~liczba mieszkań = PUM / średni metraż profilu

Etykieta: "orientacyjny potencjał zabudowy". Gdy flaga MPZP = jest -> adnotacja
"obowiązuje MPZP — potencjał do potwierdzenia w planie (Poziom 2)".
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from core.config import CONFIG
from core.schemas import Potencjal
from connectors.bdot import SasiedztwoBDOT
from connectors.nmt import SpadekNMT


def _korekta_spadku(spadek_proc: float) -> float:
    p = CONFIG.potential
    if spadek_proc <= p.spadek_prog_lagodny:
        return 1.0
    if spadek_proc >= p.spadek_prog_stromy:
        return p.korekta_spadku_min
    # interpolacja liniowa 1.0 -> korekta_spadku_min
    t = (spadek_proc - p.spadek_prog_lagodny) / (p.spadek_prog_stromy - p.spadek_prog_lagodny)
    return round(1.0 - t * (1.0 - p.korekta_spadku_min), 3)


def oblicz(
    powierzchnia_m2: float,
    bdot: Optional[SasiedztwoBDOT],
    nmt: Optional[SpadekNMT],
    flaga_mpzp: str,
) -> Tuple[Potencjal, List[str]]:
    p = CONFIG.potential
    flagi: List[str] = []

    # intensywność i kondygnacje z BDOT lub fallback (niższa pewność sygnalizowana wyżej)
    if bdot is not None:
        intensywnosc = bdot.intensywnosc
        kondygnacje = bdot.kondygnacje if bdot.wysokosci_pelne else p.kondygnacje_fallback
        if not bdot.wysokosci_pelne:
            flagi.append("potencjał: kondygnacje z fallbacku (niepełne wysokości)")
    else:
        intensywnosc = 0.3 * p.kondygnacje_fallback
        kondygnacje = p.kondygnacje_fallback
        flagi.append("potencjał: brak BDOT — przyjęto intensywność zachowawczą")

    intensywnosc = max(p.intensywnosc_min, min(p.intensywnosc_max, intensywnosc))

    if nmt is not None:
        korekta = _korekta_spadku(nmt.spadek_proc)
        if nmt.spadek_proc >= p.spadek_prog_stromy:
            flagi.append("potencjał: duży spadek terenu — istotna korekta w dół")
    else:
        korekta = 1.0
        flagi.append("potencjał: brak NMT — pominięto korektę spadku")

    pow_calkowita = powierzchnia_m2 * intensywnosc * korekta
    pum = pow_calkowita * p.pum_efficiency
    mieszkania_mlodzi = int(pum // p.metraz_mlodzi)
    mieszkania_seniorzy = int(pum // p.metraz_seniorzy)

    if flaga_mpzp == "jest":
        flagi.append("obowiązuje MPZP — potencjał do potwierdzenia w planie (Poziom 2)")

    pot = Potencjal(
        pum_m2=round(pum, 1),
        mieszkania_mlodzi=mieszkania_mlodzi,
        mieszkania_seniorzy=mieszkania_seniorzy,
        intensywnosc_otoczenia=round(intensywnosc, 3),
        kondygnacje_typowe=round(float(kondygnacje), 2),
        korekta_spadku=round(korekta, 3),
        etykieta="orientacyjny potencjał zabudowy",
        flaga_mpzp=flaga_mpzp,
    )
    return pot, flagi
