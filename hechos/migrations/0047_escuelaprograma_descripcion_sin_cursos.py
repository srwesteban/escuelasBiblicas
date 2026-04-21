from django.db import migrations, models


def cursos_json_a_descripcion(apps, schema_editor):
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")
    for ep in EscuelaPrograma.objects.all():
        raw = ep.cursos
        if not raw:
            continue
        if isinstance(raw, list) and raw:
            ep.descripcion = "\n".join(str(x) for x in raw)
            ep.save(update_fields=["descripcion"])


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0046_fundamentos_tres_escuelas"),
    ]

    operations = [
        migrations.AddField(
            model_name="escuelaprograma",
            name="descripcion",
            field=models.TextField(blank=True, default="", verbose_name="Descripción"),
            preserve_default=False,
        ),
        migrations.RunPython(cursos_json_a_descripcion, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="escuelaprograma",
            name="cursos",
        ),
    ]
