from django.db import migrations


def seed_escuelas_programa_desde_catalogo(apps, schema_editor):
    from hechos.catalogo_formacion import (
        CATALOGO_TRAMOS,
        TRAMO_ID_TO_NIVEL,
        cursos_planos_desde_catalogo_items,
    )

    Sede = apps.get_model("core", "Sede")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")

    for sede in Sede.objects.all():
        for tramo in CATALOGO_TRAMOS:
            nivel = TRAMO_ID_TO_NIVEL[tramo["id"]]
            for eb in tramo["escuelas_base"]:
                cursos = cursos_planos_desde_catalogo_items(eb["cursos"])
                EscuelaPrograma.objects.get_or_create(
                    sede_id=sede.pk,
                    nivel=nivel,
                    nombre=eb["nombre"],
                    defaults={"cursos": cursos, "is_active": True},
                )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0044_escuela_programa"),
    ]

    operations = [
        migrations.RunPython(seed_escuelas_programa_desde_catalogo, noop),
    ]
