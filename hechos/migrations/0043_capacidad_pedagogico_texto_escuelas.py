# Texto pedagógico: «ediciones» → escuelas (curso) en UI de capacidades

from django.db import migrations


def actualizar_pedagogico(apps, schema_editor):
    CapacidadCoordinador = apps.get_model("hechos", "CapacidadCoordinador")
    CapacidadCoordinador.objects.filter(codigo="pedagogico").update(
        nombre="Pedagógico (profesores, estructura de escuelas (curso))",
        descripcion=(
            "Tareas pedagógicas: profesores, estructura de escuelas (curso) "
            "y lo compartido con lo académico."
        ),
    )


def revertir_pedagogico(apps, schema_editor):
    CapacidadCoordinador = apps.get_model("hechos", "CapacidadCoordinador")
    CapacidadCoordinador.objects.filter(codigo="pedagogico").update(
        nombre="Pedagógico (profesores, estructura de ediciones)",
        descripcion=(
            "Tareas pedagógicas: profesores, estructura de ediciones y lo compartido con lo académico."
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0042_tipo_coordinador_combinado"),
    ]

    operations = [
        migrations.RunPython(actualizar_pedagogico, revertir_pedagogico),
    ]
