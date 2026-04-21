"""
Como en 0046 para Fundamentos: el Nivel 1 no debe ser una sola escuela «paraguas»,
sino las cuatro escuelas del catálogo (Sanidad Integral + tres Transformación).

Elimina el legado «Sanos y libres» (una fila) y asegura las cuatro filas por sede.
"""

from django.db import migrations


NIVEL1 = "n1"
CANONICAL = [
    "Sanidad Integral",
    "Transformación para Jóvenes",
    "Transformación para Mujeres",
    "Transformación para Hombres",
]


def _is_legacy_sanos_y_libres(nombre: str) -> bool:
    return (nombre or "").strip().lower() == "sanos y libres"


def nivel1_cuatro_escuelas_desde_legacy(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")

    for sede in Sede.objects.all():
        legacy_desc = ""
        legacy_tm = False
        legacy_costo = None

        for ep in EscuelaPrograma.objects.filter(
            sede_id=sede.pk,
            nivel=NIVEL1,
            is_active=True,
        ):
            if _is_legacy_sanos_y_libres(ep.nombre):
                legacy_desc = (getattr(ep, "descripcion", None) or "").strip()
                legacy_tm = bool(getattr(ep, "tiene_matricula", False))
                legacy_costo = getattr(ep, "costo_matricula_cop", None)
                ep.delete()

        for i, nombre in enumerate(CANONICAL):
            defaults = {
                "descripcion": (legacy_desc if i == 0 else "") or "",
                "tiene_matricula": legacy_tm,
                "costo_matricula_cop": legacy_costo if legacy_tm else None,
                "is_active": True,
            }
            obj, created = EscuelaPrograma.objects.get_or_create(
                sede_id=sede.pk,
                nivel=NIVEL1,
                nombre=nombre,
                defaults=defaults,
            )
            if created and i == 0 and legacy_desc and not (obj.descripcion or "").strip():
                obj.descripcion = legacy_desc
                obj.save(update_fields=["descripcion"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0048_escuelaprograma_matricula"),
    ]

    operations = [
        migrations.RunPython(nivel1_cuatro_escuelas_desde_legacy, noop),
    ]
