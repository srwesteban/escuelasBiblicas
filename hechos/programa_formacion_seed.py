"""
Sembrado idempotente de NivelPrograma / EscuelaPrograma en una sede desde plantillas globales.
"""

from __future__ import annotations

from django.db import transaction

from hechos.models import (
    EscuelaPrograma,
    EscuelaProgramaPlantilla,
    NivelPrograma,
    NivelProgramaPlantilla,
)


@transaction.atomic
def sembrar_programa_formacion_en_sede(sede) -> None:
    """
    Garantiza que la sede tenga niveles y escuelas del programa alineados al catálogo global.
    No pisa nombre/descripcion locales en filas ya existentes; solo enlaza plantilla si faltaba.
    """
    if not NivelProgramaPlantilla.objects.exists():
        return

    for npl in NivelProgramaPlantilla.objects.order_by("jerarquia"):
        nivel, created = NivelPrograma.objects.get_or_create(
            sede=sede,
            jerarquia=npl.jerarquia,
            defaults={
                "nombre": npl.nombre,
                "descripcion": npl.descripcion,
                "is_active": True,
                "plantilla": npl,
            },
        )
        if not created and nivel.plantilla_id != npl.pk:
            nivel.plantilla = npl
            nivel.save(update_fields=["plantilla"])

    for epl in EscuelaProgramaPlantilla.objects.select_related("nivel_plantilla").order_by(
        "nivel_plantilla__jerarquia",
        "nombre",
    ):
        nivel = NivelPrograma.objects.filter(
            sede=sede,
            jerarquia=epl.nivel_plantilla.jerarquia,
        ).first()
        if not nivel:
            continue
        ep, created = EscuelaPrograma.objects.get_or_create(
            sede=sede,
            nivel_programa=nivel,
            nombre=epl.nombre,
            defaults={
                "descripcion": epl.descripcion,
                "tiene_matricula": epl.tiene_matricula,
                "costo_matricula_cop": epl.costo_matricula_cop,
                "is_active": True,
                "plantilla": epl,
            },
        )
        if not created and ep.plantilla_id != epl.pk:
            ep.plantilla = epl
            ep.save(update_fields=["plantilla"])


@transaction.atomic
def sincronizar_copias_sede_desde_plantillas() -> None:
    """Replica texto y matrícula desde plantillas globales hacia cada sede (filas enlazadas)."""
    for npl in NivelProgramaPlantilla.objects.all():
        NivelPrograma.objects.filter(plantilla=npl).update(
            nombre=npl.nombre,
            descripcion=npl.descripcion,
        )
    for epl in EscuelaProgramaPlantilla.objects.all():
        EscuelaPrograma.objects.filter(plantilla=epl, is_active=True).update(
            nombre=epl.nombre,
            descripcion=epl.descripcion,
            tiene_matricula=epl.tiene_matricula,
            costo_matricula_cop=epl.costo_matricula_cop,
        )


def propagar_catalogo_global_a_todas_las_sedes() -> None:
    """Tras cambiar plantillas: asegura filas por sede y sincroniza contenido."""
    from core.models import Sede

    for sede in Sede.objects.all():
        sembrar_programa_formacion_en_sede(sede)
    sincronizar_copias_sede_desde_plantillas()
