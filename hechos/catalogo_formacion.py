"""
Catálogo de referencia de la estructura de formación (niveles, escuelas base y cursos).

Úsalo como base para UI y, más adelante, para crear escuelas/rutas desde plantilla.
No sustituye aún los modelos Escuela / RutaEstudio / Curso: es documentación viva en código.
"""

from __future__ import annotations

from typing import Any

# --- Metadatos mostrados en coordinación de sede (lista de escuelas) ---

CATALOGO_FORMACION_INTRO = (
    "Referencia del programa: bloques por nivel y cursos. "
    "Fundamentos se ofrece con inscripción gratuita (sin costo de matrícula). "
    "A partir del Nivel 1 puede definirse el valor de la matrícula al configurar cada oferta."
)

# Lista de tramos (Fundamentos + niveles 1–4) con escuelas base y cursos.
# Cada curso puede tener "categorias" (sub-rutas: ej. Transformación jóvenes / mujeres / hombres).


def get_catalogo_formacion_context() -> dict[str, Any]:
    """Contexto listo para plantillas Django."""
    return {
        "intro": CATALOGO_FORMACION_INTRO,
        "tramos": CATALOGO_TRAMOS,
    }


# Mapa id de tramo (catálogo) → valor de EscuelaPrograma.nivel
TRAMO_ID_TO_NIVEL: dict[str, str] = {
    "fundamentos": "formacion",
    "nivel_1": "n1",
    "nivel_2": "n2",
    "nivel_3": "n3",
    "nivel_4": "n4",
}


def cursos_planos_desde_catalogo_items(items: list[dict[str, Any]]) -> list[str]:
    """Convierte la lista de cursos del catálogo (con categorías opcionales) en líneas planas para JSON."""
    out: list[str] = []
    for it in items:
        out.append(it["nombre"])
        for cat in it.get("categorias") or []:
            out.append(cat)
    return out


CATALOGO_TRAMOS: list[dict[str, Any]] = [
    {
        "id": "fundamentos",
        "titulo": "Fundamentos",
        "matricula_gratuita": True,
        "nota_matricula": "Inscripción gratuita: sin costo de matrícula.",
        # Tres escuelas distintas dentro del nivel Fundamentos (no una sola escuela "Fundamentos").
        "escuelas_base": [
            {"nombre": "Crecimiento espiritual", "cursos": []},
            {"nombre": "Primeros pasos", "cursos": []},
            {"nombre": "Followers", "cursos": []},
        ],
    },
    {
        "id": "nivel_1",
        "titulo": "Nivel 1 — Sanos y Libres",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        # Siempre cuatro escuelas distintas bajo este nivel (una fila en sede por cada nombre).
        "escuelas_base": [
            {"nombre": "Sanidad Integral", "cursos": []},
            {"nombre": "Transformación para Jóvenes", "cursos": []},
            {"nombre": "Transformación para Mujeres", "cursos": []},
            {"nombre": "Transformación para Hombres", "cursos": []},
        ],
    },
    {
        "id": "nivel_2",
        "titulo": "Nivel 2 — Equipados",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        # Dos escuelas dentro del nivel (no una sola fila «Equipados»).
        "escuelas_base": [
            {"nombre": "Pasión por Servir", "cursos": []},
            {"nombre": "Visión", "cursos": []},
        ],
    },
    {
        "id": "nivel_3",
        "titulo": "Nivel 3 — Liderando",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        # Cuatro escuelas dentro del nivel (no una sola fila «Liderando»).
        "escuelas_base": [
            {"nombre": "Nuevo Lead", "cursos": []},
            {"nombre": "Supervisión - Kids", "cursos": []},
            {"nombre": "Supervisión - Youth", "cursos": []},
            {"nombre": "Supervisión - Grupos Hechos", "cursos": []},
        ],
    },
    {
        "id": "nivel_4",
        "titulo": "Nivel 4 — Desarrollando llamado",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        # Ocho escuelas dentro del nivel (no una sola fila «Desarrollando llamado»).
        "escuelas_base": [
            {"nombre": "Intercesión", "cursos": []},
            {"nombre": "Worship (Alabanza y Danza)", "cursos": []},
            {"nombre": "Youth", "cursos": []},
            {"nombre": "Guías - Consolidador", "cursos": []},
            {"nombre": "Maestros", "cursos": []},
            {"nombre": "Consejeros", "cursos": []},
            {"nombre": "Misiones y evangelismo", "cursos": []},
            {"nombre": "Kids - Generaciones", "cursos": []},
        ],
    },
]


def escuelas_base_catalogo_para_jerarquia(jerarquia: int) -> list[str]:
    """
    Nombres de escuela de referencia en el catálogo HECHOS para una jerarquía (0–4 con tramo).
    Vacío si no hay tramo (ej. jerarquía 5+ o niveles totalmente personalizados).
    """
    if jerarquia == 0:
        tid = "fundamentos"
    elif 1 <= jerarquia <= 4:
        tid = f"nivel_{jerarquia}"
    else:
        return []
    tramo = next((t for t in CATALOGO_TRAMOS if t["id"] == tid), None)
    if not tramo:
        return []
    return [eb["nombre"] for eb in tramo.get("escuelas_base") or []]
