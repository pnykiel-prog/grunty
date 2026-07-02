"""Domena: dopasowanie potencjał ↔ popyt (S5) -> ocena per profil."""
from __future__ import annotations

from core.config import CONFIG
from core.schemas import Popyt, Potencjal, Profile, ProfilOcena


def _werdykt(dopasowanie: float) -> str:
    d = CONFIG.demand
    if dopasowanie >= d.prog_wysoki:
        return "wysoki potencjał — rekomendowany"
    if dopasowanie >= d.prog_sredni:
        return "umiarkowany potencjał"
    return "niski potencjał"


def _ocena(mieszkania: int, popyt: float) -> ProfilOcena:
    # dostępność podaży: 20+ mieszkań traktujemy jako pełną
    podaz_factor = min(1.0, mieszkania / 20.0)
    dopasowanie = round(popyt * (0.5 + 0.5 * podaz_factor), 3)
    return ProfilOcena(dopasowanie=dopasowanie, werdykt=_werdykt(dopasowanie))


def oblicz(potencjal: Potencjal, popyt: Popyt) -> Profile:
    return Profile(
        mlodzi=_ocena(potencjal.mieszkania_mlodzi, popyt.mlodzi.popyt),
        seniorzy=_ocena(potencjal.mieszkania_seniorzy, popyt.seniorzy.popyt),
    )
