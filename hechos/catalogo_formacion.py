"""
Catálogo canónico de Formación global (niveles y escuelas plantilla).

Fuente de verdad en código para `NivelProgramaPlantilla` y
`EscuelaProgramaPlantilla` (pantalla /director/programa-escuelas/).

Tras cambiar de base de datos:
    python manage.py ensure_programa_global
"""

from __future__ import annotations

from typing import Any

# --- Metadatos (referencia legada / UI) ---

CATALOGO_FORMACION_INTRO = (
    "Referencia del programa: bloques por nivel y cursos. "
    "Fundamentos se ofrece con inscripción gratuita (sin costo de matrícula). "
    "A partir del Nivel 1 puede definirse el valor de la matrícula al configurar cada oferta."
)


def get_catalogo_formacion_context() -> dict[str, Any]:
    """Contexto listo para plantillas Django."""
    return {
        "intro": CATALOGO_FORMACION_INTRO,
        "tramos": CATALOGO_TRAMOS,
    }


# Mapa id de tramo (catálogo) → valor legado EscuelaPrograma.nivel
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


# ---------------------------------------------------------------------------
# Catálogo canónico → plantillas globales (Formación global)
# jerarquia 0 = Fundamentos (se muestra como «Nivel 1: …» en la UI).
# ---------------------------------------------------------------------------

PROGRAMA_GLOBAL_NIVELES: list[dict[str, Any]] = [
    {
        "jerarquia": 0,
        "nombre": "Fundamentos",
        "descripcion": "",
        "escuelas": [
            {"nombre": "Crecimiento espiritual"},
            {"nombre": "Followers"},
            {"nombre": "Primeros pasos"},
        ],
    },
    {
        "jerarquia": 1,
        "nombre": "Sanos y Libres",
        "descripcion": (
            "Enfocado en la restauración integral de la persona, afirmando su "
            "identidad en Cristo y estableciendo fundamentos espirituales sólidos."
        ),
        "escuelas": [
            {"nombre": "Sanidad Integral"},
            {"nombre": "Transformación para Hombres"},
            {"nombre": "Transformación para Jóvenes"},
            {"nombre": "Transformación para Mujeres"},
        ],
    },
    {
        "jerarquia": 2,
        "nombre": "Equipados",
        "descripcion": (
            "Orientado a desarrollar una vida de servicio alineada con la visión "
            "de la iglesia, entendiendo el llamado a ser parte activa del cuerpo de Cristo."
        ),
        "escuelas": [
            {"nombre": "Pasión por Servir"},
            {"nombre": "Visión"},
        ],
    },
    {
        "jerarquia": 3,
        "nombre": "Liderando",
        "descripcion": (
            "Dirigido a formar líderes que puedan guiar y pastorear en los diferentes "
            "contextos de la iglesia: generaciones (niños, adolescentes, jóvenes) y "
            "grupos familiares o homogéneos."
        ),
        "escuelas": [
            {
                "nombre": "Nuevo Lead Hechos",
                "tiene_matricula": True,
                "costo_matricula_cop": 200000,
            },
            {
                "nombre": "Nuevo Lead Kids",
                "tiene_matricula": True,
                "costo_matricula_cop": 100000,
            },
            {
                "nombre": "Nuevo lead Youth",
                "tiene_matricula": True,
                "costo_matricula_cop": 10000,
            },
            {"nombre": "Supervisión Hechos"},
            {"nombre": "Supervisión Kids"},
            {"nombre": "Supervisión Youth"},
        ],
    },
    {
        "jerarquia": 4,
        "nombre": "Desarrollando llamado",
        "descripcion": (
            "Enfocado en la formación específica en las diferentes áreas ministeriales "
            "que operan dentro de la iglesia, fortaleciendo el camino al llamado segun "
            "sus  dones y habilidades o experiencia."
        ),
        "escuelas": [
            {"nombre": "Consejeros"},
            {"nombre": "Guías - Consolidador"},
            {"nombre": "Intercesión"},
            {"nombre": "Kids - Generaciones"},
            {"nombre": "Maestros"},
            {"nombre": "Misiones y evangelismo"},
            {"nombre": "Worship (Alabanza y Danza)"},
            {"nombre": "Youth"},
        ],
    },
]


def ensure_programa_plantillas(*, update_existing: bool = True) -> dict[str, int]:
    """
    Crea (y opcionalmente actualiza) NivelProgramaPlantilla / EscuelaProgramaPlantilla
    a partir de PROGRAMA_GLOBAL_NIVELES. No toca sedes ni otras tablas.
    """
    from hechos.models import EscuelaProgramaPlantilla, NivelProgramaPlantilla

    stats = {
        "niveles_creados": 0,
        "niveles_actualizados": 0,
        "escuelas_creadas": 0,
        "escuelas_actualizadas": 0,
    }

    for nivel_data in PROGRAMA_GLOBAL_NIVELES:
        jerarquia = nivel_data["jerarquia"]
        nombre = (nivel_data.get("nombre") or "").strip()
        descripcion = nivel_data.get("descripcion") or ""

        nivel, created = NivelProgramaPlantilla.objects.get_or_create(
            jerarquia=jerarquia,
            defaults={"nombre": nombre, "descripcion": descripcion},
        )
        if created:
            stats["niveles_creados"] += 1
        elif update_existing:
            dirty = False
            if nivel.nombre != nombre:
                nivel.nombre = nombre
                dirty = True
            if (nivel.descripcion or "") != descripcion:
                nivel.descripcion = descripcion
                dirty = True
            if dirty:
                nivel.save(update_fields=["nombre", "descripcion", "updated_at"])
                stats["niveles_actualizados"] += 1

        for esc in nivel_data.get("escuelas") or []:
            esc_nombre = (esc.get("nombre") or "").strip()
            if not esc_nombre:
                continue
            esc_desc = esc.get("descripcion") or ""
            tiene_mat = bool(esc.get("tiene_matricula", False))
            costo = esc.get("costo_matricula_cop")

            escuela, esc_created = EscuelaProgramaPlantilla.objects.get_or_create(
                nivel_plantilla=nivel,
                nombre=esc_nombre,
                defaults={
                    "descripcion": esc_desc,
                    "tiene_matricula": tiene_mat,
                    "costo_matricula_cop": costo,
                },
            )
            if esc_created:
                stats["escuelas_creadas"] += 1
            elif update_existing:
                dirty = False
                if (escuela.descripcion or "") != esc_desc:
                    escuela.descripcion = esc_desc
                    dirty = True
                if escuela.tiene_matricula != tiene_mat:
                    escuela.tiene_matricula = tiene_mat
                    dirty = True
                if escuela.costo_matricula_cop != costo:
                    escuela.costo_matricula_cop = costo
                    dirty = True
                if dirty:
                    escuela.save(
                        update_fields=[
                            "descripcion",
                            "tiene_matricula",
                            "costo_matricula_cop",
                            "updated_at",
                        ]
                    )
                    stats["escuelas_actualizadas"] += 1

    return stats


# Lista de tramos (compatibilidad con migraciones / helpers legados).
CATALOGO_TRAMOS: list[dict[str, Any]] = [
    {
        "id": "fundamentos",
        "titulo": "Fundamentos",
        "matricula_gratuita": True,
        "nota_matricula": "Inscripción gratuita: sin costo de matrícula.",
        "escuelas_base": [
            {"nombre": eb["nombre"], "cursos": []}
            for eb in PROGRAMA_GLOBAL_NIVELES[0]["escuelas"]
        ],
    },
    {
        "id": "nivel_1",
        "titulo": "Nivel 1 — Sanos y Libres",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        "escuelas_base": [
            {"nombre": eb["nombre"], "cursos": []}
            for eb in PROGRAMA_GLOBAL_NIVELES[1]["escuelas"]
        ],
    },
    {
        "id": "nivel_2",
        "titulo": "Nivel 2 — Equipados",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        "escuelas_base": [
            {"nombre": eb["nombre"], "cursos": []}
            for eb in PROGRAMA_GLOBAL_NIVELES[2]["escuelas"]
        ],
    },
    {
        "id": "nivel_3",
        "titulo": "Nivel 3 — Liderando",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        "escuelas_base": [
            {"nombre": eb["nombre"], "cursos": []}
            for eb in PROGRAMA_GLOBAL_NIVELES[3]["escuelas"]
        ],
    },
    {
        "id": "nivel_4",
        "titulo": "Nivel 4 — Desarrollando llamado",
        "matricula_gratuita": False,
        "nota_matricula": "Puede definirse el valor de la matrícula.",
        "escuelas_base": [
            {"nombre": eb["nombre"], "cursos": []}
            for eb in PROGRAMA_GLOBAL_NIVELES[4]["escuelas"]
        ],
    },
]


def escuelas_base_catalogo_para_jerarquia(jerarquia: int) -> list[str]:
    """
    Nombres de escuela de referencia en el catálogo HECHOS para una jerarquía (0–4).
    Vacío si no hay tramo (ej. jerarquía 5+ o niveles totalmente personalizados).
    """
    for nivel in PROGRAMA_GLOBAL_NIVELES:
        if nivel["jerarquia"] == jerarquia:
            return [eb["nombre"] for eb in nivel.get("escuelas") or []]
    return []
