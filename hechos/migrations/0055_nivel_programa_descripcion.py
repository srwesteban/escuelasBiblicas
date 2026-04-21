from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0054_remove_placeholder_niveles_sin_escuelas"),
    ]

    operations = [
        migrations.AddField(
            model_name="nivelprograma",
            name="descripcion",
            field=models.TextField(
                blank=True,
                help_text="Texto opcional que se muestra en el acordeón de escuelas (enfoque, propósito del nivel).",
                verbose_name="Descripción del nivel",
            ),
        ),
    ]
