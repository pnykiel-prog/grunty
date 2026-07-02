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


class Level1Request(BaseModel):
    dzialki: List[ParcelId] = Field(..., min_length=1)


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
    dopasowanie: float
    werdykt: str


class Profile(BaseModel):
    mlodzi: ProfilOcena
    seniorzy: ProfilOcena


class Level1Result(BaseModel):
    status: str                 # ok | blad_wejscia | nieznaleziona | blad
    stan_terminalny: str        # nazwa stanu S1..S6 na którym zakończono
    tryb: str                   # mock | live
    powierzchnia_m2: Optional[float] = None
    geometria_wkt: Optional[str] = None
    potencjal: Optional[Potencjal] = None
    popyt: Optional[Popyt] = None
    profile: Optional[Profile] = None
    pewnosc: float = 0.0
    flagi: List[str] = Field(default_factory=list)
    komunikat: Optional[str] = None
