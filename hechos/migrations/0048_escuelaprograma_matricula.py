# Generated manually for EscuelaPrograma matrícula fields.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0047_escuelaprograma_descripcion_sin_cursos"),
    ]

    operations = [
        migrations.AddField(
            model_name="escuelaprograma",
            name="tiene_matricula",
            field=models.BooleanField(
                default=False,
                help_text="Si aplica cobro de matrícula para esta escuela.",
                verbose_name="Tiene matrícula",
            ),
        ),
        migrations.AddField(
            model_name="escuelaprograma",
            name="costo_matricula_cop",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Pesos colombianos enteros. Obligatorio cuando «Tiene matrícula» está activo.",
                null=True,
                verbose_name="Costo de matrícula (COP)",
            ),
        ),
    ]
