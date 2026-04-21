from django.db import migrations


def separar_fundamentos_en_tres_escuelas(apps, schema_editor):
    """
    Fundamentos es un nivel; Crecimiento espiritual, Primeros pasos y Followers
    son tres escuelas distintas, no cursos de una sola escuela "Fundamentos".
    """
    Sede = apps.get_model("core", "Sede")
    EscuelaPrograma = apps.get_model("hechos", "EscuelaPrograma")
    nombres = ["Crecimiento espiritual", "Primeros pasos", "Followers"]

    for sede in Sede.objects.all():
        EscuelaPrograma.objects.filter(
            sede_id=sede.pk,
            nivel="formacion",
            nombre="Fundamentos",
        ).delete()
        for nombre in nombres:
            EscuelaPrograma.objects.get_or_create(
                sede_id=sede.pk,
                nivel="formacion",
                nombre=nombre,
                defaults={"cursos": [], "is_active": True},
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("hechos", "0045_seed_escuelas_programa_catalogo"),
    ]

    operations = [
        migrations.RunPython(separar_fundamentos_en_tres_escuelas, noop),
    ]
