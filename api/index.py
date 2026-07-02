"""Punkt wejścia serverless dla Vercel (@vercel/python).

Vercel wykrywa zmienną `app` (aplikacja ASGI) i serwuje ją jako funkcję.
Cały ruch (/, /api/*) jest przekierowany tutaj przez vercel.json, a FastAPI
obsługuje zarówno API, jak i statyczny frontend.
"""
import os
import sys

# Zapewnij, że pakiety najwyższego poziomu (core, geo, connectors, ...) oraz
# pakiet `api` są importowalne z katalogu głównego repozytorium.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from api.main import app  # noqa: E402

__all__ = ["app"]
