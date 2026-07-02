"""Domena: model popytu (wewnętrzny / zewnętrzny), profile młodzi/seniorzy.

  wewnętrzny = grupa_docelowa × kwalifikacja_dochodowa × napięcie
  zewnętrzny = napływ_migracyjny × siła_luki_cenowej
  popyt      = waga_wew·wew + waga_zew·zew

Bez mnożnika usług (to Poziom 2). Wartości znormalizowane do 0..1.
"""
from __future__ import annotations

from typing import Optional

from core.config import CONFIG
from core.schemas import Popyt, ProfilPopyt
from connectors.bdl import DemografiaBDL
from connectors.market import Rynek


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _napiecie(zasob_mieszkaniowy: float) -> float:
    # mniej mieszkań/1000 -> większe napięcie popytowe
    return _clamp01((440.0 - zasob_mieszkaniowy) / 140.0)


def _kwalifikacja_dochodowa(bezrobocie: float) -> float:
    # niższe bezrobocie -> wyższa zdolność dochodowa
    return _clamp01(1.0 - bezrobocie / 0.15)


def _naplyw(saldo_migracji: float) -> float:
    # saldo /1000 z zakresu [-10,+10] -> [0,1]
    return _clamp01((saldo_migracji + 10.0) / 20.0)


def _profil(grupa_docelowa: float, demo: DemografiaBDL,
            luka_cenowa: float) -> ProfilPopyt:
    d = CONFIG.demand
    kwalifikacja = _kwalifikacja_dochodowa(demo.bezrobocie)
    napiecie = _napiecie(demo.zasob_mieszkaniowy)
    wew = _clamp01(grupa_docelowa / 0.35) * kwalifikacja * napiecie

    naplyw = _naplyw(demo.saldo_migracji)
    zew = naplyw * _clamp01(luka_cenowa)

    popyt = d.waga_wew * wew + d.waga_zew * zew
    return ProfilPopyt(wew=round(wew, 3), zew=round(zew, 3), popyt=round(popyt, 3))


def oblicz(demo: Optional[DemografiaBDL], rynek: Optional[Rynek]) -> Popyt:
    # przy braku danych używamy neutralnych sygnałów (degradacja, nie blokada)
    if demo is None:
        from connectors.bdl import _neutralne
        demo = _neutralne(CONFIG.bdl.rok_danych)
    luka = rynek.luka_cenowa if rynek is not None else 0.4

    mlodzi = _profil(demo.udzial_20_39, demo, luka)
    seniorzy = _profil(demo.udzial_65p, demo, luka)
    return Popyt(mlodzi=mlodzi, seniorzy=seniorzy)
