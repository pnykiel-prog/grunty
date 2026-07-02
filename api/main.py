"""API M1 — FastAPI: /api/analyze/level1 + serwowanie frontendu.

Wszystkie wywołania zewnętrzne idą przez backend (rozwiązuje CORS).
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from core.config import CONFIG
from core.schemas import Level1Request, Level1Result
from pipeline.level1 import run_level1

app = FastAPI(title="Grunty M1", version="1.0")

_FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "tryb": CONFIG.mode}


@app.post("/api/analyze/level1")
async def analyze_level1(request: Request) -> JSONResponse:
    body = await request.json()
    # Walidacja wejścia jako terminal S1 (błędna działka -> komunikat, nie 500).
    # Akceptujemy oba sposoby wprowadzania: osobne pola LUB pełny identyfikator.
    try:
        req = Level1Request.from_items((body or {}).get("dzialki"))
    except ValidationError as exc:
        wynik = Level1Result(
            status="blad_wejscia", stan_terminalny="S1", tryb=CONFIG.mode,
            komunikat="Niepoprawne dane wejściowe działki.",
            flagi=[str(e.get("msg", "")) for e in exc.errors()],
        )
        return JSONResponse(status_code=200, content=wynik.model_dump())
    except (ValueError, TypeError, KeyError) as exc:
        wynik = Level1Result(
            status="blad_wejscia", stan_terminalny="S1", tryb=CONFIG.mode,
            komunikat=str(exc) or "Niepoprawne dane wejściowe działki.",
        )
        return JSONResponse(status_code=200, content=wynik.model_dump())

    wynik = run_level1(req)
    return JSONResponse(status_code=200, content=wynik.model_dump())


# Serwowanie frontendu (na końcu, aby nie przykryć tras /api/*).
if os.path.isdir(_FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIR, html=True), name="frontend")
