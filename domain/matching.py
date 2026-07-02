"""Domena: dopasowanie potencjał ↔ popyt (S5) -> ocena per profil.

Produkuje prezentacyjną ocenę: score 0..100, kategorię werdyktu, pewność oraz
sygnały (wypunktowania). Sygnały wyłącznie z danych M1 (potencjał z sąsiedztwa,
spadek, demografia, rynek, flaga MPZP) — bez uzbrojenia/izochron/środowiska,
które należą do Poziomu 2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from core.config import CONFIG
from core.schemas import Popyt, Potencjal, Profile, ProfilOcena
from connectors.bdl import DemografiaBDL
from connectors.market import Rynek
from connectors.nmt import SpadekNMT


@dataclass
class KontekstOceny:
    potencjal: Potencjal
    demo: Optional[DemografiaBDL]
    rynek: Optional[Rynek]
    nmt: Optional[SpadekNMT]
    pewnosc_mlodzi: float
    pewnosc_seniorzy: float


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _kategoria_werdykt(score: int) -> tuple[str, str]:
    if score >= 65:
        return "nadaje_sie", "Nadaje się"
    if score >= 45:
        return "warunkowo", "Warunkowo"
    return "nie", "Nie w tym profilu"


def _score(popyt_norm: float, mieszkania: int, pewnosc: float) -> tuple[int, float]:
    podaz = min(1.0, mieszkania / 25.0)
    dopasowanie = _clamp01(0.55 * popyt_norm + 0.45 * podaz)
    score01 = 0.45 * popyt_norm + 0.35 * podaz + 0.20 * pewnosc
    return int(round(100 * _clamp01(score01))), round(dopasowanie, 3)


def _sygnaly_wspolne(ctx: KontekstOceny) -> List[str]:
    s: List[str] = []
    p = ctx.potencjal
    s.append(f"Otoczenie: intensywność {p.intensywnosc_otoczenia}, "
             f"typowo {p.kondygnacje_typowe:g} kondygnacji")
    if ctx.nmt is not None:
        sp = ctx.nmt.spadek_proc
        if sp >= CONFIG.potential.spadek_prog_stromy:
            s.append(f"Duży spadek terenu {sp:g}% — istotna korekta potencjału")
        elif sp <= CONFIG.potential.spadek_prog_lagodny:
            s.append(f"Teren płaski (spadek {sp:g}%) — bez korekty")
        else:
            s.append(f"Umiarkowany spadek {sp:g}% — niewielka korekta")
    if p.flaga_mpzp == "brak":
        s.append("Brak MPZP — przeznaczenie do potwierdzenia")
    elif p.flaga_mpzp == "jest":
        s.append("Obowiązuje MPZP — potencjał do potwierdzenia w planie (P2)")
    return s


def _sygnaly_profil(ctx: KontekstOceny, udzial: float, popyt_wew: float,
                    popyt_zew: float, senior: bool) -> List[str]:
    s: List[str] = []
    grupa = "65+" if senior else "20–39 lat"
    s.append(f"Udział grupy {grupa}: {udzial:.0%} — popyt wewnętrzny {popyt_wew:.2f}")
    if ctx.demo is not None and ctx.demo.saldo_migracji > 0:
        s.append(f"Dodatnie saldo migracji +{ctx.demo.saldo_migracji:g}/1000 "
                 f"— wspiera popyt zewnętrzny {popyt_zew:.2f}")
    elif ctx.demo is not None:
        s.append(f"Saldo migracji {ctx.demo.saldo_migracji:g}/1000 "
                 f"— popyt zewnętrzny {popyt_zew:.2f}")
    if ctx.rynek is not None:
        s.append(f"Czynsz najmu ~{ctx.rynek.czynsz_m2:g} zł/m²/mc, "
                 f"luka cenowa {ctx.rynek.luka_cenowa:.2f}")
    if senior and ctx.nmt is not None and ctx.nmt.spadek_proc >= CONFIG.potential.spadek_prog_lagodny:
        s.append(f"Spadek {ctx.nmt.spadek_proc:g}% — sprawdzić dostępność dla seniorów")
    return s[:3]


def _ocena(popyt_norm: float, mieszkania: int, pewnosc: float,
           sygnaly: List[str]) -> ProfilOcena:
    score, dopasowanie = _score(popyt_norm, mieszkania, pewnosc)
    kategoria, werdykt = _kategoria_werdykt(score)
    return ProfilOcena(dopasowanie=dopasowanie, score=score, kategoria=kategoria,
                       werdykt=werdykt, pewnosc=round(pewnosc, 3), sygnaly=sygnaly)


def oblicz(potencjal: Potencjal, popyt: Popyt, ctx: KontekstOceny) -> Profile:
    wspolne = _sygnaly_wspolne(ctx)
    udzial_m = ctx.demo.udzial_20_39 if ctx.demo else 0.26
    udzial_s = ctx.demo.udzial_65p if ctx.demo else 0.19

    syg_m = wspolne[:1] + _sygnaly_profil(ctx, udzial_m, popyt.mlodzi.wew,
                                          popyt.mlodzi.zew, senior=False)
    syg_s = wspolne[:1] + _sygnaly_profil(ctx, udzial_s, popyt.seniorzy.wew,
                                          popyt.seniorzy.zew, senior=True)

    mlodzi = _ocena(popyt.mlodzi.popyt, potencjal.mieszkania_mlodzi,
                    ctx.pewnosc_mlodzi, syg_m)
    seniorzy = _ocena(popyt.seniorzy.popyt, potencjal.mieszkania_seniorzy,
                      ctx.pewnosc_seniorzy, syg_s)

    rekomendowany = "mlodzi" if mlodzi.score >= seniorzy.score else "seniorzy"
    return Profile(mlodzi=mlodzi, seniorzy=seniorzy, rekomendowany=rekomendowany)
