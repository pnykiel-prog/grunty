# Grunty — Moduł M1

Poziom 1 aplikacji analizującej działki, budowany modułami zgodnie z
`M1_specyfikacja_modulowa_claude_code.md`.

**Zakres M1:** z numerów działek → geometria (ULDK), **orientacyjny potencjał
zabudowy** liczony algorytmicznie z sąsiedztwa (BDOT) i spadku (NMT), flaga
istnienia MPZP (tylko tak/nie), popyt z demografii (GUS BDL) i rynku.
Bez ręcznego wprowadzania wskaźników MPZP/WZ/PnB.

## Zasady przekrojowe (egzekwowane w kodzie)

- Jedna próba + timeout na wywołanie zewnętrzne, **bez ponawiania i rekurencji**.
- Skończona maszyna stanów `S1..S6`, zawsze stan terminalny.
- Wszystkie wywołania przez backend (rozwiązuje CORS).
- Parametry w `core/config.py` (config-not-code).
- Brak danych → niższa pewność, nie blokada (degradacja).
- Tryb `mock` daje pełny, niepusty wynik offline.

## Struktura

```
core/        config (parametry, anti-loop, MODE), schemas (ParcelId, Level1Request/Result)
geo/         geometry: parse WKT, scalenie (union), przyleganie (touches), pole (EPSG:2180)
connectors/  uldk, bdl, market, bdot, nmt, mpzp_coverage — wspólny kontrakt fetch()->ConnectorResult
domain/      potential (potencjał z sąsiedztwa), demand (popyt wew/zew), matching (dopasowanie)
pipeline/    level1 — maszyna stanów S1..S6
api/         main — FastAPI: /api/analyze/level1 + serwowanie frontendu
frontend/    minimalny UI (osobne pola identyfikatora działki)
tests/       test_level1 — testy offline (mock): determinizm + terminalność
```

## Uruchomienie

```bash
pip install -r requirements.txt

# tryb mock (domyślny, offline)
uvicorn api.main:app --reload
# -> http://127.0.0.1:8000  (frontend), POST /api/analyze/level1

# tryb live (realne konektory; jedna próba + timeout, degradacja przy braku)
GRUNTY_MODE=live uvicorn api.main:app
```

## Testy

```bash
pip install -r requirements-dev.txt   # runtime + pytest
pytest -q
```

## Deploy (Vercel)

Aplikacja jest gotowa pod Vercel (`vercel.json` + entrypoint `api/index.py`
eksponujący ASGI `app`). Produkcyjny deploy idzie z gałęzi **main**.
`requirements.txt` zawiera tylko zależności runtime (bez pytest) — mniejszy
bundle funkcji. Domyślny tryb: `mock`; dla `live` ustaw `GRUNTY_MODE=live`
w zmiennych środowiskowych projektu Vercel.

Sprawdzają: poprawna działka → powierzchnia i geometria; nieprzylegające → błąd
terminalny; determinizm; **zero pętli, zawsze terminal**; pełny wynik w mocku.

## Konektory (kontrakt)

Każdy: `fetch(...) -> ConnectorResult(dane|None, status, pewnosc)`, jedna próba +
timeout, tryby `mock`/`live`.

- **ULDK** (potwierdzone): `GetParcelById&result=geom_wkt&srid=2180`; linia 1 =
  status (`0`=ok), linia 2 = WKT (odcinany prefiks `SRID=…;`); status ≠ 0 →
  nieznaleziona (terminal, bez ponawiania).
- **GUS BDL**: mapowanie gminy→jednostka (12 znaków, **≠ kod gminy**) z cache w
  configu; `var-id` odkrywane przez subjects/variables i zapisane w configu (rok
  danych oznaczony); brak → sygnały neutralne + niższa pewność.
- **BDOT10k**: budynki w buforze (200 m) → intensywność/pokrycie/kondygnacje;
  niepełne wysokości → fallback kondygnacji + niższa pewność.
- **NMT**: średni spadek terenu; duży spadek obniża potencjał (i flaga senioralna).
- **MPZP (KIMPZP)**: wyłącznie flaga `jest|brak|nieznane`; **bez parsowania
  treści planu** (adnotacja do wyniku, nie wchodzi do obliczeń).
- **market**: najem długoterminowy/sprzedaż + reguła wystarczalności (drabina ≤3,
  próg N próbek) → siła luki cenowej.

## Wynik (schemat)

```json
{ "status", "stan_terminalny", "tryb", "powierzchnia_m2", "geometria_wkt",
  "potencjal": { "pum_m2", "mieszkania_mlodzi", "mieszkania_seniorzy",
                 "etykieta": "orientacyjny potencjał zabudowy",
                 "flaga_mpzp": "jest|brak|nieznane" },
  "popyt": { "mlodzi": {"wew","zew","popyt"}, "seniorzy": {…} },
  "profile": { "mlodzi": {"dopasowanie","werdykt"}, "seniorzy": {…} },
  "pewnosc", "flagi": [] }
```

## Status wg kolejności wdrożenia (sekcja 7)

- **M1a** szkielet + ULDK (mock/live), scalenie + przyleganie, API + front — ✔
- **M1b** GUS BDL + model popytu wew/zew (mock pełny; live: mapowanie+pobranie,
  degradacja do sygnałów neutralnych) — ✔
- **M1c** potencjał z sąsiedztwa: BDOT (bufor) + NMT (spadek) + flaga MPZP — ✔
- **M1d** rynek + luka cenowa z regułą wystarczalności (drabina ≤3) — ✔

W trybie `live` konektory GUGiK (BDOT/NMT/MPZP) i agregatory rynkowe wykonują
pojedyncze zapytanie i **świadomie degradują** tam, gdzie warstwy/źródła wymagają
potwierdzenia z GetCapabilities/licencji — bez pętli i bez blokowania pipeline'u.
```
