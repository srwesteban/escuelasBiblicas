"""
Elimina niveles de jerarquía >= 5 que no tienen ninguna EscuelaPrograma asociada.
Esos registros solo servían para la migración 0053 y no deben aparecer como «creados» por el usuario.
"""

from django.db import migrations
from django.db.models import Count


def quitar_placeholders(apps, schema_editor):
    NivelPrograma = apps.get_model("hechos", "NivelPrograma")
    qs = (
        NivelPrograma.objects.filter(jerarquia__gte=5)
        .annotate(_n=Count("escuelas"))
        .filter(_n=0)
    )
    qs.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0053_nivel_programa_dinamico"),
    ]

    operations = [
        migrations.RunPython(quitar_placeholders, noop_reverse),
    ]
