"""Testy offline (mock) M1: determinizm, terminalność, degradacja.

Uruchamiane w trybie mock (domyślnym) — bez sieci. Weryfikują, że pipeline
zawsze kończy w stanie terminalnym i daje pełny, niepusty wynik.
"""
from __future__ import annotations

from core.config import CONFIG
from core.schemas import Level1Request, ParcelId
from pipeline.level1 import run_level1


def _pid(numer: str, teryt: str = "146501", obreb: str = "0001") -> ParcelId:
    return ParcelId(teryt=teryt, rodzaj_gminy="1", obreb=obreb, numer=numer)


def test_tryb_mock():
    assert CONFIG.is_mock, "Testy zakładają domyślny tryb mock"


def test_pojedyncza_dzialka_ok():
    wynik = run_level1(Level1Request(dzialki=[_pid("1")]))
    assert wynik.status == "ok"
    assert wynik.stan_terminalny == "S6"
    assert wynik.powierzchnia_m2 and wynik.powierzchnia_m2 > 0
    assert wynik.potencjal is not None
    assert wynik.potencjal.etykieta == "orientacyjny potencjał zabudowy"
    assert wynik.popyt is not None and wynik.profile is not None
    assert wynik.potencjal.flaga_mpzp in ("jest", "brak", "nieznane")


def test_prezentacja_kompletna():
    """Warstwa prezentacyjna: score, kategoria, rekomendacja, bramka, geometrie."""
    wynik = run_level1(Level1Request(dzialki=[_pid("1"), _pid("2")]))
    assert wynik.profile.rekomendowany in ("mlodzi", "seniorzy")
    for prof in (wynik.profile.mlodzi, wynik.profile.seniorzy):
        assert 0 <= prof.score <= 100
        assert prof.kategoria in ("nadaje_sie", "warunkowo", "nie")
        assert 0.0 <= prof.pewnosc <= 1.0
        assert len(prof.sygnaly) >= 1
    assert wynik.brama is not None
    assert isinstance(wynik.brama.przechodzi, bool)
    assert wynik.flagi_sygnaly, "oczekiwano chipów flag/sygnałów"
    for s in wynik.flagi_sygnaly:
        assert s.typ in ("positive", "neutral", "warning")
    # geometrie per działka (do mapy)
    assert len(wynik.dzialki) == 2
    assert all(d.wkt and d.powierzchnia_m2 > 0 for d in wynik.dzialki)


def test_mock_daje_niepusty_wynik():
    """Tryb mock musi dawać pełny, niepusty wynik offline."""
    wynik = run_level1(Level1Request(dzialki=[_pid("5")]))
    d = wynik.model_dump()
    for klucz in ("powierzchnia_m2", "potencjal", "popyt", "profile"):
        assert d[klucz] is not None


def test_determinizm():
    """Ten sam wejściowy zestaw -> identyczny wynik (bez losowości/pętli)."""
    req = Level1Request(dzialki=[_pid("7"), _pid("8")])
    w1 = run_level1(req).model_dump()
    w2 = run_level1(req).model_dump()
    assert w1 == w2


def test_wiele_przylegajacych_dzialek():
    """Numery 1,2,3 w mocku stykają się bokiem -> obszar spójny, scalenie."""
    req = Level1Request(dzialki=[_pid("1"), _pid("2"), _pid("3")])
    wynik = run_level1(req)
    assert wynik.status == "ok"
    assert wynik.stan_terminalny == "S6"
    # 3 kwadraty 30 m obok siebie -> ~2700 m²
    assert 2600 < wynik.powierzchnia_m2 < 2800


def test_nieprzylegajace_blad_terminal():
    """Numery 1 i 3 mają lukę (brak numeru 2) -> nieprzylegające -> terminal."""
    req = Level1Request(dzialki=[_pid("1"), _pid("3")])
    wynik = run_level1(req)
    assert wynik.status == "blad_wejscia"
    assert wynik.stan_terminalny == "S2"
    assert "scalenie" in (wynik.komunikat or "").lower()
    # geometrie działek dostępne mimo błędu (do podświetlenia przerwy na mapie)
    assert len(wynik.dzialki) == 2


def test_zawsze_terminal():
    """Każda ścieżka kończy w zdefiniowanym stanie terminalnym (bez pętli)."""
    przypadki = [
        [_pid("1")],
        [_pid("1"), _pid("2")],
        [_pid("1"), _pid("3")],
    ]
    dozwolone = {"S1", "S2", "S6"}
    for dzialki in przypadki:
        wynik = run_level1(Level1Request(dzialki=dzialki))
        assert wynik.stan_terminalny in dozwolone
        assert wynik.status in {"ok", "blad_wejscia", "nieznaleziona", "blad"}


def test_pewnosc_w_zakresie():
    wynik = run_level1(Level1Request(dzialki=[_pid("2")]))
    assert 0.0 <= wynik.pewnosc <= 1.0


def test_uldk_id_format():
    pid = ParcelId(teryt="146501", rodzaj_gminy="1", obreb="1", numer="12/3")
    assert pid.uldk_id() == "146501_1.0001.12/3"
    pid_ar = ParcelId(teryt="146501", rodzaj_gminy="1", obreb="12", numer="5", arkusz="3")
    assert pid_ar.uldk_id() == "146501_1.0012.AR_3.5"
