# Sedes creadas antes de exigir departamento: ciudad Pasto sin dep → Nariño (52).

from django.db import migrations


def rellena_departamento_pasto(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    Sede.objects.filter(ciudad__iexact="Pasto", departamento="").update(departamento="52")


def noop_reverse(apps, schema_editor):
    # No revertimos: el vacío era un dato incompleto, no el estado deseado.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_user_tipo_documento"),
    ]

    operations = [
        migrations.RunPython(rellena_departamento_pasto, noop_reverse),
    ]
