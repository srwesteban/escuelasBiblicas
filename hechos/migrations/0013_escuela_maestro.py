# Generated manually for Escuela.maestro

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0012_marcar_coordinador_sede_por_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="escuela",
            name="maestro",
            field=models.ForeignKey(
                blank=True,
                help_text="Profesor responsable; puede quedar por asignar hasta definirlo.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="escuelas_dirigidas",
                to="hechos.profesor",
                verbose_name="Maestro asignado",
            ),
        ),
    ]
