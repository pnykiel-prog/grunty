"""Pipeline M1 — skończona maszyna stanów S1..S6.

Każdy stan ma jedno wyjście naprzód, brak krawędzi wstecznych, brak
auto-przeliczania i rekurencji. Zawsze kończymy w stanie terminalnym.

S1  Walidacja wejścia (identyfikatory)            (błąd -> terminal)
S2  ULDK -> geometria + scalenie + przyleganie     (nieznaleziona/nieprzyleganie -> terminal)
S3  Potencjał: BDOT + NMT -> orientacyjny; flaga MPZP (adnotacja)
S4  Popyt: BDL (demografia) + rynek                 (brak -> niższa pewność)
S5  Dopasowanie potencjał <-> popyt -> ocena profili
S6  WYNIK (terminal)
"""
from __future__ import annotations

from typing import List

from core.config import CONFIG
from core.schemas import DzialkaGeo, Level1Request, Level1Result
from geo import geometry as geo

from connectors import uldk, bdot, nmt, mpzp_coverage, bdl, market
from connectors.base import NOT_FOUND
from domain import potential as dom_potential
from domain import demand as dom_demand
from domain import matching as dom_matching
from domain import presentation as dom_present
from domain.matching import KontekstOceny


def _srednia(pewnosci: List[float]) -> float:
    vals = [p for p in pewnosci if p is not None]
    if not vals:
        return 0.0
    return round(sum(vals) / len(vals), 3)


def run_level1(request: Level1Request) -> Level1Result:
    tryb = CONFIG.mode
    flagi: List[str] = []
    pewnosci: List[float] = []

    # --- S1: walidacja wejścia -------------------------------------------
    if not request.dzialki:
        return Level1Result(status="blad_wejscia", stan_terminalny="S1",
                            tryb=tryb, komunikat="Brak działek na wejściu.")

    # --- S2: ULDK -> geometrie, scalenie, przyleganie --------------------
    geoms = []
    dzialki_geo: List[DzialkaGeo] = []
    pewnosc_uldk: List[float] = []
    for pid in request.dzialki:
        res = uldk.fetch(pid)
        pewnosci.append(res.pewnosc)
        pewnosc_uldk.append(res.pewnosc)
        flagi.extend(res.flagi)
        if res.status == NOT_FOUND or res.dane is None:
            return Level1Result(
                status="nieznaleziona", stan_terminalny="S2", tryb=tryb,
                dzialki=dzialki_geo,
                komunikat=f"Nie znaleziono działki {pid.numer} w rejestrze ULDK",
                pewnosc=_srednia(pewnosci), flagi=flagi,
            )
        try:
            g = geo.parse_wkt(res.dane)
        except Exception:
            return Level1Result(
                status="nieznaleziona", stan_terminalny="S2", tryb=tryb,
                dzialki=dzialki_geo,
                komunikat=f"Niepoprawna geometria ULDK dla działki {pid.numer}",
                pewnosc=_srednia(pewnosci), flagi=flagi,
            )
        geoms.append(g)
        dzialki_geo.append(DzialkaGeo(id=pid.uldk_id(),
                                      powierzchnia_m2=round(geo.powierzchnia_m2(g), 2),
                                      wkt=g.wkt))

    ok_przyl, powod = geo.przylegaja(geoms)
    if not ok_przyl:
        return Level1Result(
            status="blad_wejscia", stan_terminalny="S2", tryb=tryb,
            dzialki=dzialki_geo,
            komunikat="Między wskazanymi działkami wykryto przerwę — scalenie "
                      "w jeden teren niemożliwe.",
            pewnosc=_srednia(pewnosci), flagi=flagi,
        )

    scalona = geo.scal(geoms)
    powierzchnia = geo.powierzchnia_m2(scalona)
    teryt = request.dzialki[0].teryt_gmina
    cx, cy = geo.centroid_xy(scalona)

    # --- S3: potencjał (BDOT + NMT) + flaga MPZP -------------------------
    r_bdot = bdot.fetch(scalona, teryt)
    r_nmt = nmt.fetch(scalona, teryt)
    r_mpzp = mpzp_coverage.fetch((cx, cy), teryt)
    for r in (r_bdot, r_nmt, r_mpzp):
        pewnosci.append(r.pewnosc)
        flagi.extend(r.flagi)

    flaga_mpzp = r_mpzp.dane if r_mpzp.dane in ("jest", "brak", "nieznane") else "nieznane"
    potencjal, flagi_pot = dom_potential.oblicz(
        powierzchnia, r_bdot.dane, r_nmt.dane, flaga_mpzp)
    flagi.extend(flagi_pot)

    # --- S4: popyt (BDL + rynek) -----------------------------------------
    r_bdl = bdl.fetch(teryt)
    r_market = market.fetch(teryt)
    for r in (r_bdl, r_market):
        pewnosci.append(r.pewnosc)
        flagi.extend(r.flagi)
    popyt = dom_demand.oblicz(r_bdl.dane, r_market.dane)

    # --- S5: dopasowanie potencjał <-> popyt -----------------------------
    p_uldk = _srednia(pewnosc_uldk)
    # pewność per profil z konektorów najbardziej istotnych dla profilu
    pewnosc_mlodzi = _srednia([p_uldk, r_bdot.pewnosc, r_bdl.pewnosc, r_market.pewnosc])
    pewnosc_seniorzy = _srednia([p_uldk, r_bdot.pewnosc, r_bdl.pewnosc, r_nmt.pewnosc])
    ctx = KontekstOceny(
        potencjal=potencjal, demo=r_bdl.dane, rynek=r_market.dane, nmt=r_nmt.dane,
        pewnosc_mlodzi=pewnosc_mlodzi, pewnosc_seniorzy=pewnosc_seniorzy,
    )
    profile = dom_matching.oblicz(potencjal, popyt, ctx)

    # warstwa prezentacyjna
    flagi_sygnaly = dom_present.buduj_flagi(potencjal, r_bdl.dane, r_nmt.dane)
    bdot_wys = getattr(r_bdot.dane, "wysokosci_pelne", None)
    czego_nie = dom_present.buduj_braki(
        r_bdot.status, r_nmt.status, r_bdl.status, r_market.status,
        flaga_mpzp, bdot_wys)
    pewnosc_ogolna = _srednia(pewnosci)
    brama = dom_present.buduj_brame(profile, pewnosc_ogolna)

    # --- S6: WYNIK (terminal) --------------------------------------------
    return Level1Result(
        status="ok",
        stan_terminalny="S6",
        tryb=tryb,
        powierzchnia_m2=round(powierzchnia, 2),
        geometria_wkt=scalona.wkt,
        dzialki=dzialki_geo,
        potencjal=potencjal,
        popyt=popyt,
        profile=profile,
        flagi_sygnaly=flagi_sygnaly,
        czego_nie_pobrano=czego_nie,
        brama=brama,
        pewnosc=pewnosc_ogolna,
        flagi=flagi,
        komunikat=None,
    )
