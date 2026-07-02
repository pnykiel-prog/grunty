"""Modele wejścia/wyjścia M1 (ParcelId, Level1Request, Level1Result)."""
from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Wejście
# ---------------------------------------------------------------------------
class ParcelId(BaseModel):
    """Identyfikator działki z OSOBNYCH pól.

    Docelowy format ULDK: ``WWPPGG_R.XXXX[.AR_n].NDZ`` gdzie
    - ``teryt`` = WWPPGG (województwo+powiat+gmina, 6 cyfr),
    - ``rodzaj_gminy`` = R (1 cyfra),
    - ``obreb`` = XXXX (dopełniany do 4 cyfr),
    - ``numer`` = NDZ (może zawierać ``/``),
    - ``arkusz`` = opcjonalny numer arkusza (AR_n).
    """

    teryt: str = Field(..., description="WWPPGG — 6 cyfr")
    rodzaj_gminy: str = Field(..., description="R — 1 cyfra rodzaju gminy")
    obreb: str = Field(..., description="numer obrębu (dopełniany do 4 cyfr)")
    numer: str = Field(..., description="numer działki, może zawierać '/'")
    arkusz: Optional[str] = Field(default=None, description="numer arkusza (AR)")

    @field_validator("teryt")
    @classmethod
    def _teryt_6(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{6}", v):
            raise ValueError("teryt musi mieć dokładnie 6 cyfr (WWPPGG)")
        return v

    @field_validator("rodzaj_gminy")
    @classmethod
    def _rodzaj_1(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d", v):
            raise ValueError("rodzaj_gminy musi być 1 cyfrą")
        return v

    @field_validator("obreb")
    @classmethod
    def _obreb(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"\d{1,4}", v):
            raise ValueError("obreb musi być liczbą 1-4 cyfrowej")
        return v

    @field_validator("numer")
    @classmethod
    def _numer(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[0-9]+(/[0-9]+)*", v):
            raise ValueError("numer działki ma nieprawidłowy format")
        return v

    @property
    def teryt_gmina(self) -> str:
        """TERYT gminy (6 cyfr) — do mapowania na jednostkę BDL."""
        return self.teryt

    def uldk_id(self) -> str:
        obreb4 = self.obreb.zfill(4)
        head = f"{self.teryt}_{self.rodzaj_gminy}.{obreb4}"
        if self.arkusz:
            return f"{head}.AR_{self.arkusz}.{self.numer}"
        return f"{head}.{self.numer}"

    @classmethod
    def from_uldk_id(cls, raw: str) -> "ParcelId":
        """Parsuje pełny identyfikator ULDK ``WWPPGG_R.XXXX[.AR_n].NDZ``.

        Umożliwia wprowadzanie działki jednym polem zamiast osobnych pól.
        Walidacja poszczególnych segmentów odbywa się w walidatorach pól.
        """
        s = (raw or "").strip()
        if "_" not in s or "." not in s:
            raise ValueError(
                "Identyfikator ULDK musi mieć format WWPPGG_R.XXXX[.AR_n].NDZ")
        teryt, rest = s.split("_", 1)
        parts = rest.split(".")
        if len(parts) < 3:
            raise ValueError("Identyfikator ULDK: za mało segmentów")
        rodzaj, obreb = parts[0], parts[1]
        arkusz = None
        idx = 2
        if parts[idx].upper().startswith("AR_"):
            arkusz = parts[idx][3:]
            idx += 1
        if idx >= len(parts):
            raise ValueError("Identyfikator ULDK: brak numeru działki")
        numer = ".".join(parts[idx:])
        return cls(teryt=teryt, rodzaj_gminy=rodzaj, obreb=obreb,
                   numer=numer, arkusz=arkusz)


def parse_dzialka(item) -> ParcelId:
    """Buduje ParcelId z pozycji wejścia — pola osobne LUB pełny identyfikator.

    Klient może przesłać:
      - obiekt z osobnymi polami (teryt/rodzaj_gminy/obreb/numer[/arkusz]),
      - obiekt z pełnym identyfikatorem: ``{"id": "WWPPGG_R.XXXX.NDZ"}``.
    """
    if isinstance(item, ParcelId):
        return item
    if isinstance(item, dict) and item.get("id") and not item.get("teryt"):
        return ParcelId.from_uldk_id(str(item["id"]))
    return ParcelId.model_validate(item)


class Level1Request(BaseModel):
    dzialki: List[ParcelId] = Field(..., min_length=1)

    @classmethod
    def from_items(cls, items) -> "Level1Request":
        """Tworzy żądanie z listy pozycji mieszanych (pola lub identyfikator)."""
        if not isinstance(items, list) or not items:
            raise ValueError("Brak działek na wejściu.")
        return cls(dzialki=[parse_dzialka(x) for x in items])


# ---------------------------------------------------------------------------
# Wyjście
# ---------------------------------------------------------------------------
class Potencjal(BaseModel):
    pum_m2: float
    mieszkania_mlodzi: int
    mieszkania_seniorzy: int
    intensywnosc_otoczenia: float
    kondygnacje_typowe: float
    korekta_spadku: float
    etykieta: str = "orientacyjny potencjał zabudowy"
    flaga_mpzp: str = "nieznane"  # jest | brak | nieznane


class ProfilPopyt(BaseModel):
    wew: float
    zew: float
    popyt: float


class Popyt(BaseModel):
    mlodzi: ProfilPopyt
    seniorzy: ProfilPopyt


class ProfilOcena(BaseModel):
    dopasowanie: float          # 0..1 (surowa miara)
    score: int                  # 0..100 (do prezentacji)
    kategoria: str              # nadaje_sie | warunkowo | nie
    werdykt: str                # etykieta prezentacyjna
    pewnosc: float              # 0..1 pewność oceny profilu
    sygnaly: List[str] = Field(default_factory=list)


class Profile(BaseModel):
    mlodzi: ProfilOcena
    seniorzy: ProfilOcena
    rekomendowany: str          # mlodzi | seniorzy


class Sygnal(BaseModel):
    tekst: str
    typ: str                    # positive | neutral | warning


class BrakDanych(BaseModel):
    tytul: str
    opis: str
    wplyw_pkt: int              # szacowany spadek pewności (pkt)


class Brama(BaseModel):
    przechodzi: bool
    profil: str                 # profil, dla którego teren przechodzi przesiew
    pewnosc_wstepna: float
    etykieta: str


class DzialkaGeo(BaseModel):
    id: str
    powierzchnia_m2: float
    wkt: str


class Level1Result(BaseModel):
    status: str                 # ok | blad_wejscia | nieznaleziona | blad
    stan_terminalny: str        # nazwa stanu S1..S6 na którym zakończono
    tryb: str                   # mock | live
    powierzchnia_m2: Optional[float] = None
    geometria_wkt: Optional[str] = None
    dzialki: List[DzialkaGeo] = Field(default_factory=list)
    potencjal: Optional[Potencjal] = None
    popyt: Optional[Popyt] = None
    profile: Optional[Profile] = None
    flagi_sygnaly: List[Sygnal] = Field(default_factory=list)
    czego_nie_pobrano: List[BrakDanych] = Field(default_factory=list)
    brama: Optional[Brama] = None
    pewnosc: float = 0.0
    flagi: List[str] = Field(default_factory=list)
    komunikat: Optional[str] = None
