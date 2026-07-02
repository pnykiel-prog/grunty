# M1 — modularna specyfikacja budowy (dla Claude Code)

Buduj Poziom 1 od podstaw, modułami, w kolejności z sekcji 7. Trzymaj zasady przekrojowe (anty-pętla, config-not-code) z `SPECYFIKACJA_BUDOWY_aplikacja.md`. Ten dokument uszczegóławia M1 i **zmienia jedną rzecz**: pojemność liczymy **algorytmicznie z sąsiedztwa**, a nie z ręcznie wpisywanych wskaźników MPZP/WZ/PnB.

---

## 0. Zakres M1 (zaktualizowany)

Wejście: **numer/numery działek** (osobne pola). Automatycznie:
1. **ULDK** → geometria, lokalizacja, rozmiar (scalenie wielu działek + walidacja przylegania).
2. **Potencjał zabudowy** → algorytmicznie z **sąsiedztwa (BDOT)** + **spadku (NMT)**; wynik nazywamy **„orientacyjny potencjał zabudowy”**, nie „co dopuszcza plan”.
3. **Flaga MPZP** → jedno zapytanie „plan istnieje / nie / nieznane” (bez odczytu treści).
4. **Popyt** → **GUS BDL** (demografia) + **rynek** (najem długoterminowy / sprzedaż), rozdział wewnętrzny/zewnętrzny.

Bez ręcznego wprowadzania wskaźników. Bez środowiska, uzbrojenia, izochron, kosztów (to Poziom 2).

---

## 1. Zasady przekrojowe (skrót — obowiązują w każdym module)

Jedna próba + timeout na wywołanie zewnętrzne, degradacja przy błędzie, **zakaz ponawiania i rekurencji**. Skończona maszyna stanów, zawsze stan terminalny. Wszystkie wywołania przez **backend/proxy** (CORS). Parametry w konfiguracji. Brak danych → niższa pewność, nie blokada.

---

## 2. Podział na moduły

```
core/
  config          parametry, limity anty-pętla, słowniki, id zmiennych BDL, MODE mock/live
  schemas         modele wejścia/wyjścia (ParcelId, Level1Request, Level1Result)
geo/
  geometry        parse WKT, scalenie (union), przyleganie (touches), powierzchnia (EPSG:2180)
connectors/
  uldk            geometria działki (sekcja 3.1)
  bdl             demografia GUS BDL (sekcja 3.2)
  market          rynek najem/sprzedaż + reguła wystarczalności (drabina ≤3)
  bdot            budynki sąsiedztwa: obrysy/intensywność/wysokości (sekcja 3.3)
  nmt             spadek terenu (sekcja 3.3)
  mpzp_coverage   flaga istnienia planu (sekcja 3.4)
domain/
  potential       algorytmiczny potencjał zabudowy z sąsiedztwa + spadku
  demand          model popytu (wewnętrzny/zewnętrzny)
pipeline/
  level1          maszyna stanów S1–S6
api/
  main            FastAPI: /api/analyze/level1, serwowanie frontendu
tests/
  test_level1     testy offline (mock), determinizm + terminalność
```

Każdy konektor ma wspólny kontrakt: `fetch(...) -> (dane|None, status, pewnosc)`; jedna próba + timeout; `mock`/`live`.

---

## 3. Konektory — konkretne podpięcia

### 3.1 ULDK (potwierdzone)
```
GET https://uldk.gugik.gov.pl/?request=GetParcelById
    &id=<WWPPGG_R.XXXX.NDZ>&result=geom_wkt&srid=2180
```
- identyfikator z osobnych pól: obręb dopełniony do 4 cyfr, cyfra rodzaju gminy po `_`, numer może mieć `/`;
- odpowiedź: **linia 1 = status** (`0`=ok), linia 2 = geometria (WKT po `result=geom_wkt`; przy prefiksie `SRID=…;` odciąć);
- status ≠ `0` → „nieznaleziona” (np. wymagany arkusz `AR`); obsłużyć jako terminal, nie ponawiać.

### 3.2 GUS BDL — demografia (potwierdzone)
Baza: `https://bdl.stat.gov.pl/api/v1/` (JSON: `?format=json`). Opcjonalny `X-ClientId` (limity).

**Kolejność integracji:**
1. **Mapowanie gminy → jednostka BDL.** BDL używa 12-znakowego identyfikatora jednostki (NUTS/TERYT), **nie** kodu gminy z działki wprost. Zmapuj raz (wyszukanie jednostki po nazwie/TERYT) i **cache’uj** w konfiguracji.
2. **Dobór zmiennych** (nie hardkodować na ślepo — odkryć i zapisać w configu):
   - `/subjects?lang=pl&format=json` → temat „Ludność” → `/subjects?parent-id=<K…>` → `/variables?subject-id=<…>`;
   - zmienne potrzebne w M1: ludność wg grup wieku (udział 20–39 i 65+), saldo/napływ migracji, bezrobocie, zasób mieszkaniowy.
3. **Pobranie danych** — jednostka + wiele zmiennych:
   ```
   GET /data/by-unit/{unitId}?var-id={id1}&var-id={id2}&format=json&year=2023
   ```
   albo jedna zmienna, wiele jednostek: `/data/by-variable/{varId}?unit-level=6&format=json` (6=gmina).
   Dane to trójka `[wartość, id_atrybutu, id_roku]`; paginacja `page` + `page-size`.

**Anty-pętla:** krok mapowania i krok pobrania — po jednej próbie z timeoutem; brak → sygnały neutralne + niższa pewność (nie blokować).

### 3.3 Sąsiedztwo (BDOT10k) + spadek (NMT) — do potencjału
- **BDOT10k budynki:** obrysy budynków w buforze wokół działki (np. 150–300 m) → policz lokalną intensywność/pokrycie i typową liczbę kondygnacji/wysokość. Usługi GUGiK — adres i warstwy ustal z katalogu `https://integracja.gugik.gov.pl/` / GetCapabilities. **Uwaga:** wysokości bywają niepełne — fallback: przyjmij typową kondygnację z otoczenia lub oznacz niższą pewność.
- **NMT:** średni spadek na terenie działki (raster/WCS lub kafel). Duży spadek obniża potencjał (i osobno flaga dla profilu senioralnego).
- Oba: jedno ograniczone zapytanie, degradacja przy braku.

### 3.4 Flaga istnienia MPZP (KIMPZP) — tylko tak/nie
```
GetFeatureInfo w centroidzie terenu do KIMPZP
```
Wynik → flaga: `plan_jest` / `plan_brak` / `nieznane` (przy błędzie/timeoucie). **Nie parsować treści planu, nie czytać wskaźników.** Flaga tylko dokleja adnotację do wyniku; nie wchodzi do obliczeń.

---

## 4. Domena

### 4.1 potential (algorytmiczny potencjał)
```
intensywność_otoczenia = f(BDOT: pokrycie/obrysy w buforze)
kondygnacje_typowe      = z BDOT (lub fallback)
korekta_spadku          = z NMT (duży spadek → niżej)
pow. całkowita ≈ pow. działki × intensywność_otoczenia × korekta_spadku
PUM ≈ pow. całkowita × PUM_EFFICIENCY
~liczba mieszkań = PUM / średni metraż profilu
```
Etykieta wyniku: **„orientacyjny potencjał zabudowy”**. Jeśli `flaga MPZP = plan_jest` → dodaj adnotację **„obowiązuje MPZP — potencjał do potwierdzenia w planie (Poziom 2)”**.

### 4.2 demand (popyt, wew/zew)
Jak w modelu popytu: wewnętrzny = grupa docelowa × kwalifikacja dochodowa × napięcie; zewnętrzny = napływ migracyjny × siła luki cenowej; **bez mnożnika usług** (to Poziom 2). Rynek przez regułę wystarczalności (drabina ≤3, progi N).

---

## 5. Pipeline M1 (maszyna stanów)

```
S1  Wejście działek → walidacja przylegania           (błąd → terminal)
S2  ULDK → lokalizacja + rozmiar                        (nieznaleziona → terminal)
S3  Potencjał: BDOT + NMT → orientacyjny potencjał; flaga MPZP (adnotacja)
S4  Popyt: BDL (demografia) + rynek                     (brak → niższa pewność)
S5  Dopasowanie potencjał ↔ popyt → ocena per profil
S6  WYNIK (terminal)
```
Każdy stan: jedno wyjście naprzód, bez krawędzi wstecznych, bez auto-przeliczania.

---

## 6. Wynik M1 (schemat)
```
{ status, tryb, powierzchnia_m2,
  potencjal: { pum_m2, mieszkania, etykieta:"orientacyjny", flaga_mpzp:"jest|brak|nieznane" },
  popyt: { mlodzi:{wew,zew,popyt}, seniorzy:{...} },
  profile: { mlodzi:{dopasowanie,werdykt}, seniorzy:{...} },
  pewnosc, flagi:[...] }
```

---

## 7. Kolejność wdrożenia i kryteria akceptacji

**M1a — szkielet + ULDK (mock i live).** Osobne pola → identyfikator; wiele działek + przyleganie; ULDK; API + minimalny front.
*Akceptacja:* poprawna działka → powierzchnia i geometria; błędna → komunikat; nieprzylegające → błąd; **zero pętli, zawsze terminal**.

**M1b — GUS BDL live + popyt.** Mapowanie gminy→jednostka (cache), dobór var-id (config), pobranie, model popytu wew/zew.
*Akceptacja:* dla realnej gminy zwraca sygnały demograficzne; brak danych → niższa pewność, nie blokada.

**M1c — potencjał z sąsiedztwa.** BDOT (bufor) + NMT (spadek) → orientacyjny potencjał; flaga MPZP.
*Akceptacja:* potencjał liczony bez ręcznych wskaźników; przy istniejącym planie adnotacja „do potwierdzenia”.

**M1d — rynek + luka cenowa.** Konektor rynku z regułą wystarczalności (drabina ≤3, filtr najmu długoterminowego).
*Akceptacja:* luka cenowa liczona; słabe dane → degradacja, nie ponawianie.

---

## 8. Pułapki (wpisać do pamięci wykonawcy)

- **BDL: jednostka ≠ kod gminy** — najpierw zmapuj gminę na 12-znakowy identyfikator jednostki BDL, potem pobieraj dane.
- **BDL: var-id nie hardkodować na ślepo** — odkryć przez subjects/variables, zapisać w configu, oznaczyć rok danych.
- **BDOT: wysokości niepełne** — fallback + niższa pewność.
- **MPZP: tylko flaga** — bez parsowania treści (to było źródło pętli).
- **Wszystko przez backend** (CORS); logować surowe odpowiedzi przed parsowaniem.
- **Tryb mock** musi dawać pełny, niepusty wynik offline — do odróżnienia „błąd logiki” od „błąd integracji”.
