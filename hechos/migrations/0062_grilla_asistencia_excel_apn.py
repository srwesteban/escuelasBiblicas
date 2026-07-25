# Alinea letras A/P/N al Excel de referencia y sincroniza columnas con clases.

from django.db import migrations, models


def _remap_valores_forwards(apps, schema_editor):
    Celda = apps.get_model("hechos", "AsistenciaGrillaCelda")
    rotacion = {"P": "A", "A": "N", "N": "P"}
    for cel in Celda.objects.all().only("id", "valor"):
        nuevo = rotacion.get(cel.valor)
        if nuevo and nuevo != cel.valor:
            cel.valor = nuevo
            cel.save(update_fields=["valor"])


def _remap_valores_backwards(apps, schema_editor):
    Celda = apps.get_model("hechos", "AsistenciaGrillaCelda")
    rotacion = {"A": "P", "N": "A", "P": "N"}
    for cel in Celda.objects.all().only("id", "valor"):
        nuevo = rotacion.get(cel.valor)
        if nuevo and nuevo != cel.valor:
            cel.valor = nuevo
            cel.save(update_fields=["valor"])


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0061_grilla_asistencia_escuela"),
    ]

    operations = [
        migrations.AlterField(
            model_name="escuelagrillaasistenciaconfig",
            name="num_columnas",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="asistenciagrillacelda",
            name="valor",
            field=models.CharField(
                choices=[
                    ("A", "Asistió (A)"),
                    ("P", "P"),
                    ("N", "Inasistencia (N)"),
                ],
                max_length=1,
            ),
        ),
        migrations.RunPython(_remap_valores_forwards, _remap_valores_backwards),
    ]
