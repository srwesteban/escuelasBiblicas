"""
Nivel 3 — Liderando: cuatro escuelas (Nuevo Lead + tres Supervisión), no una sola «Liderando».
"""

from django.db import migrations


NIVEL3 = "n3"
CANONICAL = [
    "Nuevo Lead",
    "Supervisión - Kids",
    "Supervisión - Youth",
    "Supervisión - Grupos Hechos",
]


def _is_legacy_liderando(nombre: str) -> bool:
    return (nombre or "").strip().lower() == "liderando"


def nivel3_cuatro_escuelas_liderando(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")

    for sede in Sede.objects.all():
        legacy_desc = ""
        legacy_tm = False
        legacy_costo = None

        for ep in EscuelaPrograma.objects.filter(
            sede_id=sede.pk,
            nivel=NIVEL3,
            is_active=True,
        ):
            if _is_legacy_liderando(ep.nombre):
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
                nivel=NIVEL3,
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
        ("hechos", "0050_nivel2_dos_escuelas_equipados"),
    ]

    operations = [
        migrations.RunPython(nivel3_cuatro_escuelas_liderando, noop),
    ]
