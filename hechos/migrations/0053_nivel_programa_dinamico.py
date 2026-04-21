"""
Niveles de programa por sede (jerarquía + nombre). Migra el CharField nivel → FK NivelPrograma.
"""

import django.db.models.deletion
from django.db import migrations, models


LEGACY_NIVEL_A_JERARQUIA = {
    "formacion": 0,
    "n1": 1,
    "n2": 2,
    "n3": 3,
    "n4": 4,
    "n5": 5,
    "n6": 6,
    "n7": 7,
    "n8": 8,
    "n9": 9,
    "n10": 10,
}


def _nombre_catalogo_jerarquia(j):
    if j == 0:
        return "Fundamentos"
    if 1 <= j <= 4:
        from hechos.catalogo_formacion import CATALOGO_TRAMOS

        tramo = next((t for t in CATALOGO_TRAMOS if t["id"] == f"nivel_{j}"), None)
        if tramo and " — " in tramo["titulo"]:
            return tramo["titulo"].split(" — ", 1)[1].strip()
    return ""


def poblar_niveles_y_enlazar_escuelas(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    NivelPrograma = apps.get_model("hechos", "NivelPrograma")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")

    cache_pk = {}

    for sede in Sede.objects.all():
        for j in range(0, 11):
            nombre = _nombre_catalogo_jerarquia(j)
            obj, _ = NivelPrograma.objects.get_or_create(
                sede_id=sede.pk,
                jerarquia=j,
                defaults={"nombre": nombre, "is_active": True},
            )
            cache_pk[(sede.pk, j)] = obj.pk

    for ep in EscuelaPrograma.objects.all():
        legacy = getattr(ep, "nivel", None)
        j = LEGACY_NIVEL_A_JERARQUIA.get(legacy, 0)
        ep.nivel_programa_id = cache_pk[(ep.sede_id, j)]
        ep.save(update_fields=["nivel_programa_id"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0052_nivel4_ocho_escuelas_desarrollando_llamado"),
    ]

    operations = [
        migrations.CreateModel(
            name="NivelPrograma",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "jerarquia",
                    models.PositiveIntegerField(
                        help_text="0 = Fundamentos (nivel cero). 1, 2, 3… definen el orden respecto a otros niveles.",
                        verbose_name="Jerarquía",
                    ),
                ),
                (
                    "nombre",
                    models.CharField(
                        blank=True,
                        help_text="Parte descriptiva (ej. Sanos y Libres). Para jerarquía 0 puede ser «Fundamentos» o dejarse vacío.",
                        max_length=200,
                        verbose_name="Nombre",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "sede",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="niveles_programa",
                        to="core.sede",
                    ),
                ),
            ],
            options={
                "verbose_name": "Nivel (programa)",
                "verbose_name_plural": "Niveles (programa)",
                "ordering": ["jerarquia", "nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="nivelprograma",
            constraint=models.UniqueConstraint(
                fields=("sede", "jerarquia"),
                name="uniq_hechos_nivel_programa_sede_jerarquia",
            ),
        ),
        migrations.AddField(
            model_name="escuelaprograma",
            name="nivel_programa",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="escuelas",
                to="hechos.nivelprograma",
                verbose_name="Nivel",
            ),
        ),
        migrations.RunPython(poblar_niveles_y_enlazar_escuelas, noop_reverse),
        migrations.RemoveField(
            model_name="escuelaprograma",
            name="nivel",
        ),
        migrations.AlterField(
            model_name="escuelaprograma",
            name="nivel_programa",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="escuelas",
                to="hechos.nivelprograma",
                verbose_name="Nivel",
            ),
        ),
        migrations.AlterModelOptions(
            name="nivelprograma",
            options={
                "ordering": ["jerarquia", "nombre"],
                "verbose_name": "Nivel (programa)",
                "verbose_name_plural": "Niveles (programa)",
            },
        ),
        # En algunas bases el nombre puede no coincidir (o faltar); no fallar al migrar.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE hechos_escuelaprograma DROP CONSTRAINT IF EXISTS "uniq_hechos_escuela_programa_sede_nivel_nombre";',
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="escuelaprograma",
                    name="uniq_hechos_escuela_programa_sede_nivel_nombre",
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="escuelaprograma",
            constraint=models.UniqueConstraint(
                fields=("sede", "nivel_programa", "nombre"),
                name="uniq_hechos_escuela_programa_sede_nivel_prog_nombre",
            ),
        ),
        migrations.AlterModelOptions(
            name="escuelaprograma",
            options={
                "ordering": ["nivel_programa__jerarquia", "nombre"],
                "verbose_name": "Escuela (programa)",
                "verbose_name_plural": "Escuelas (programa)",
            },
        ),
    ]
