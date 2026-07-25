"""
Resolución de la oferta académica por escuela.

La matrícula y las clases se anclan a ``Escuela``; no hay entidad «edición».
"""

from __future__ import annotations

from django.db.models import QuerySet

from hechos.models import Escuela


def ediciones_activas_en_sede(escuela: Escuela, sede) -> QuerySet:
    """Compatibilidad de nombre: devuelve 0 o 1 fila ``Escuela`` si la oferta está activa en la sede."""
    if not escuela or not sede or escuela.sede_id != sede.id:
        return Escuela.objects.none()
    if not escuela.is_active:
        return Escuela.objects.none()
    return Escuela.objects.filter(pk=escuela.pk)


def edicion_prioritaria_para_matricula(escuelas_qs) -> Escuela | None:
    """Primera escuela con cupo libre; si ninguna tiene cupo, la primera fila (orden estable por id)."""
    lst = list(escuelas_qs)
    if not lst:
        return None
    for e in lst:
        if e.cupos_disponibles > 0:
            return e
    return lst[0]
