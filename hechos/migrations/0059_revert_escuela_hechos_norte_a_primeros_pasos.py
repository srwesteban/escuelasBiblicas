# Datos: revertir nombre de escuela operativa confundido con nombre de sede.

from django.db import migrations


def revert_nombre_escuela(apps, schema_editor):
    Escuela = apps.get_model("hechos", "Escuela")
    Escuela.objects.filter(pk=2, nombre="Hechos Norte").update(nombre="Primero pasos")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("hechos", "0058_plantillas_constraints_y_sembrado"),
    ]

    operations = [
        migrations.RunPython(revert_nombre_escuela, noop),
    ]
