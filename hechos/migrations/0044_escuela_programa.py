import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_sede_user_sede"),
        ("hechos", "0043_capacidad_pedagogico_texto_escuelas"),
    ]

    operations = [
        migrations.CreateModel(
            name="EscuelaPrograma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "nivel",
                    models.CharField(
                        choices=[
                            ("formacion", "Formación"),
                            ("n1", "Nivel 1"),
                            ("n2", "Nivel 2"),
                            ("n3", "Nivel 3"),
                            ("n4", "Nivel 4"),
                            ("n5", "Nivel 5"),
                            ("n6", "Nivel 6"),
                            ("n7", "Nivel 7"),
                            ("n8", "Nivel 8"),
                            ("n9", "Nivel 9"),
                            ("n10", "Nivel 10"),
                        ],
                        max_length=20,
                    ),
                ),
                ("nombre", models.CharField(max_length=200)),
                ("cursos", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="escuelas_programa",
                        to="core.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "Escuela (programa)",
                "verbose_name_plural": "Escuelas (programa)",
                "ordering": ["nivel", "nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="escuelaprograma",
            constraint=models.UniqueConstraint(
                fields=("sede", "nivel", "nombre"),
                name="uniq_hechos_escuela_programa_sede_nivel_nombre",
            ),
        ),
    ]
