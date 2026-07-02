"""Domena: budowa warstwy prezentacyjnej M1 — chipy flag, białe plamy, bramka.

Wszystko wyłącznie z danych M1. Nie fabrykujemy sygnałów spoza zakresu
(uzbrojenie/izochrony/środowisko = Poziom 2).
"""
from __future__ import annotations

from typing import List, Optional

from core.schemas import (BrakDanych, Brama, Potencjal, Profile, Sygnal)
from connectors.bdl import DemografiaBDL
from connectors.nmt import SpadekNMT
from connectors.base import DEGRADED


def buduj_flagi(potencjal: Potencjal, demo: Optional[DemografiaBDL],
                nmt: Optional[SpadekNMT]) -> List[Sygnal]:
    flagi: List[Sygnal] = []

    # MPZP
    if potencjal.flaga_mpzp == "brak":
        flagi.append(Sygnal(tekst="Brak MPZP — biała plama planistyczna", typ="warning"))
    elif potencjal.flaga_mpzp == "jest":
        flagi.append(Sygnal(tekst="Obowiązuje MPZP — do potwierdzenia w planie", typ="neutral"))
    else:
        flagi.append(Sygnal(tekst="Status MPZP nieznany", typ="warning"))

    # spadek terenu
    if nmt is not None:
        sp = nmt.spadek_proc
        if sp >= 20:
            flagi.append(Sygnal(tekst=f"Duży spadek terenu {sp:g}%", typ="warning"))
        elif sp <= 8:
            flagi.append(Sygnal(tekst=f"Teren płaski (spadek {sp:g}%)", typ="positive"))
        else:
            flagi.append(Sygnal(tekst=f"Umiarkowany spadek {sp:g}%", typ="neutral"))

    # demografia / rynek mieszkaniowy
    if demo is not None:
        if demo.saldo_migracji > 0:
            flagi.append(Sygnal(tekst=f"Dodatnie saldo migracji +{demo.saldo_migracji:g}/1000", typ="positive"))
        elif demo.saldo_migracji < 0:
            flagi.append(Sygnal(tekst=f"Ujemne saldo migracji {demo.saldo_migracji:g}/1000", typ="warning"))
        if demo.zasob_mieszkaniowy < 360:
            flagi.append(Sygnal(tekst="Wysokie napięcie mieszkaniowe (niski zasób)", typ="positive"))

    # intensywność otoczenia
    flagi.append(Sygnal(tekst=f"Intensywność otoczenia {potencjal.intensywnosc_otoczenia}", typ="neutral"))
    return flagi


def buduj_braki(status_bdot: str, status_nmt: str, status_bdl: str,
                status_market: str, flaga_mpzp: str,
                bdot_wysokosci_pelne: Optional[bool]) -> List[BrakDanych]:
    braki: List[BrakDanych] = []

    if flaga_mpzp == "nieznane":
        braki.append(BrakDanych(
            tytul="MPZP / Studium uwarunkowań",
            opis="brak/niepewny status planu dla obrębu",
            wplyw_pkt=-18))
    if status_bdot == DEGRADED:
        braki.append(BrakDanych(
            tytul="BDOT10k — sąsiedztwo",
            opis="brak obrysów budynków w buforze — intensywność zachowawcza",
            wplyw_pkt=-15))
    elif bdot_wysokosci_pelne is False:
        braki.append(BrakDanych(
            tytul="BDOT10k — wysokości budynków",
            opis="niepełne wysokości — kondygnacje z fallbacku",
            wplyw_pkt=-6))
    if status_nmt == DEGRADED:
        braki.append(BrakDanych(
            tytul="NMT — spadek terenu",
            opis="brak modelu terenu — pominięto korektę spadku",
            wplyw_pkt=-8))
    if status_bdl == DEGRADED:
        braki.append(BrakDanych(
            tytul="GUS BDL — demografia",
            opis="brak danych jednostki — sygnały neutralne",
            wplyw_pkt=-12))
    if status_market == DEGRADED:
        braki.append(BrakDanych(
            tytul="Rynek nieruchomości",
            opis="niewystarczające dane ofertowe — degradacja",
            wplyw_pkt=-10))
    return braki


def buduj_brame(profile: Profile, pewnosc: float) -> Brama:
    rek = profile.mlodzi if profile.rekomendowany == "mlodzi" else profile.seniorzy
    nazwa = "Młodzi" if profile.rekomendowany == "mlodzi" else "Seniorzy"
    przechodzi = rek.kategoria in ("nadaje_sie", "warunkowo")
    if przechodzi:
        etykieta = f"Teren przechodzi przesiew dla profilu „{nazwa}”"
    else:
        etykieta = "Teren nie przechodzi wstępnego przesiewu"
    return Brama(przechodzi=przechodzi, profil=nazwa,
                 pewnosc_wstepna=round(pewnosc, 3), etykieta=etykieta)
