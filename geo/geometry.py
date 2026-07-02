"""Operacje geometryczne: parse WKT, scalenie, przyleganie, powierzchnia.

Współrzędne pracują w EPSG:2180 (metryczny układ PL-1992), bo ULDK odpytujemy
z ``srid=2180`` — dzięki temu pole powierzchni jest wprost w m² bez reprojekcji.
"""
from __future__ import annotations

from typing import List, Tuple

from shapely import wkt as shapely_wkt
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def parse_wkt(raw: str) -> BaseGeometry:
    """Parsuje WKT, odcinając ewentualny prefiks ``SRID=…;``."""
    if raw is None:
        raise ValueError("pusty WKT")
    s = raw.strip()
    if s.upper().startswith("SRID="):
        # format 'SRID=2180;POLYGON(...)'
        _, _, s = s.partition(";")
        s = s.strip()
    geom = shapely_wkt.loads(s)
    if geom.is_empty:
        raise ValueError("geometria pusta")
    return geom


def scal(geoms: List[BaseGeometry]) -> BaseGeometry:
    """Scalenie (union) wielu działek w jedną geometrię."""
    if not geoms:
        raise ValueError("brak geometrii do scalenia")
    return unary_union(geoms)


def przylegaja(geoms: List[BaseGeometry]) -> Tuple[bool, str]:
    """Sprawdza, czy działki tworzą jeden spójny obszar.

    Dwie działki uznajemy za przylegające, gdy się stykają (``touches``) lub
    nakładają (``intersects`` z niezerowym polem części wspólnej). Cały zbiór
    jest poprawny, gdy graf przylegania jest spójny (jedna składowa).
    """
    n = len(geoms)
    if n <= 1:
        return True, "pojedyncza działka"

    # graf: krawędź gdy touches lub intersects
    adj = {i: set() for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            gi, gj = geoms[i], geoms[j]
            if gi.touches(gj) or gi.intersects(gj):
                adj[i].add(j)
                adj[j].add(i)

    # BFS bez rekurencji (zakaz rekurencji — anti-loop)
    visited = set()
    stack = [0]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        for nb in adj[node]:
            if nb not in visited:
                stack.append(nb)

    if len(visited) == n:
        return True, "działki przylegają (obszar spójny)"
    return False, "działki nie przylegają — brak wspólnej granicy"


def powierzchnia_m2(geom: BaseGeometry) -> float:
    """Powierzchnia w m² (współrzędne w EPSG:2180 są metryczne)."""
    return float(geom.area)


def centroid_xy(geom: BaseGeometry) -> Tuple[float, float]:
    c = geom.centroid
    return float(c.x), float(c.y)


def bufor(geom: BaseGeometry, promien_m: float) -> BaseGeometry:
    """Bufor wokół geometrii (w metrach, EPSG:2180)."""
    return geom.buffer(promien_m)
