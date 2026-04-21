"""
Nivel 2 — Equipados: dos escuelas distintas (Pasión por Servir y Visión), no una sola «Equipados».

Elimina el legado por sede y asegura las dos filas canónicas.
"""

from django.db import migrations


NIVEL2 = "n2"
CANONICAL = [
    "Pasión por Servir",
    "Visión",
]


def _is_legacy_equipados(nombre: str) -> bool:
    return (nombre or "").strip().lower() == "equipados"


def nivel2_dos_escuelas_equipados(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")

    for sede in Sede.objects.all():
        legacy_desc = ""
        legacy_tm = False
        legacy_costo = None

        for ep in EscuelaPrograma.objects.filter(
            sede_id=sede.pk,
            nivel=NIVEL2,
            is_active=True,
        ):
            if _is_legacy_equipados(ep.nombre):
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
                nivel=NIVEL2,
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
        ("hechos", "0049_nivel1_cuatro_escuelas_sanos_y_libres"),
    ]

    operations = [
        migrations.RunPython(nivel2_dos_escuelas_equipados, noop),
    ]
