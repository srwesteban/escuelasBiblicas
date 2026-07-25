# Generated manually for grilla de notas (profesor).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
        ("hechos", "0063_edicioncurso_modalidad"),
    ]

    operations = [
        migrations.CreateModel(
            name="EscuelaGrillaNotasConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("num_columnas", models.PositiveIntegerField(default=5)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "escuela",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_configs",
                        to="hechos.escuela",
                    ),
                ),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_configs",
                        to="core.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración grilla de notas",
                "verbose_name_plural": "Configuraciones grilla de notas",
            },
        ),
        migrations.CreateModel(
            name="NotasGrillaCelda",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("columna", models.PositiveIntegerField(help_text="1 = Nota 1, 2 = Nota 2, …", verbose_name="Columna")),
                ("valor", models.CharField(blank=True, max_length=64)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "escuela",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_celdas",
                        to="hechos.escuela",
                    ),
                ),
                (
                    "estudiante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_celdas",
                        to="hechos.estudiante",
                    ),
                ),
                (
                    "registrado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="grilla_notas_registros",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_celdas",
                        to="core.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "Celda grilla notas",
                "verbose_name_plural": "Celdas grilla notas",
                "ordering": ["columna", "estudiante__user__last_name"],
                "unique_together": {("escuela", "estudiante", "columna")},
            },
        ),
        migrations.CreateModel(
            name="NotasGrillaEstadoFinal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "estado",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("", "—"),
                            ("aprobado", "Aprobado"),
                            ("no_aprobado", "No aprobado"),
                        ],
                        default="",
                        max_length=20,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "escuela",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_estados_finales",
                        to="hechos.escuela",
                    ),
                ),
                (
                    "estudiante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_estados_finales",
                        to="hechos.estudiante",
                    ),
                ),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grilla_notas_estados_finales",
                        to="core.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "Estado final grilla notas",
                "verbose_name_plural": "Estados finales grilla notas",
                "unique_together": {("escuela", "estudiante")},
            },
        ),
        migrations.AddConstraint(
            model_name="escuelagrillanotasconfig",
            constraint=models.UniqueConstraint(
                fields=("escuela", "sede"), name="uniq_grilla_notas_config_escuela_sede"
            ),
        ),
    ]
