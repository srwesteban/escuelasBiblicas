"""Departamentos y municipios de Colombia (datos JSON en static/geo, uso local)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings

_GEO_DIR = Path(settings.BASE_DIR) / "static" / "geo"


@lru_cache(maxsize=1)
def _departments_rows() -> list[dict]:
    path = _GEO_DIR / "colombia_departments.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)["data"]


@lru_cache(maxsize=1)
def _cities_rows() -> list[dict]:
    path = _GEO_DIR / "colombia_cities.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)["data"]


def departamento_choices() -> list[tuple[str, str]]:
    """Opciones (id str, nombre), ordenadas por nombre."""
    rows = _departments_rows()
    pairs = [(str(r["id"]), r["name"]) for r in rows]
    pairs.sort(key=lambda x: x[1])
    return pairs


def ciudad_choices_for_departamento(dep_id: str | int | None) -> list[tuple[str, str]]:
    """Municipios del departamento como (nombre, nombre)."""
    if dep_id is None or dep_id == "":
        return []
    try:
        dep = int(dep_id)
    except (TypeError, ValueError):
        return []
    names = [r["name"] for r in _cities_rows() if r["departmentId"] == dep]
    names.sort(key=lambda n: n.casefold())
    return [(n, n) for n in names]


def nombre_departamento(dep_id: str | int | None) -> str:
    if dep_id is None or dep_id == "":
        return ""
    sid = str(dep_id)
    for did, name in departamento_choices():
        if did == sid:
            return name
    return ""
