# Alinear catálogo global: mismo significado que el Excel («Nuevo Lead Hechos»).

from django.db import migrations


def alinear_nombres(apps, schema_editor):
    Plantilla = apps.get_model("hechos", "EscuelaProgramaPlantilla")
    EP = apps.get_model("hechos", "EscuelaPrograma")

    Plantilla.objects.filter(nombre__iexact="Nuevo lead - Grupo Hechos").update(nombre="Nuevo Lead Hechos")
    EP.objects.filter(nombre__iexact="Nuevo lead - Grupo Hechos").update(nombre="Nuevo Lead Hechos")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("hechos", "0059_revert_escuela_hechos_norte_a_primeros_pasos"),
    ]

    operations = [
        migrations.RunPython(alinear_nombres, noop),
    ]
