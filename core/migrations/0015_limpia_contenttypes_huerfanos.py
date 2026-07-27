# Generated manually — limpia ContentType/Permission huérfanos de modelos ya eliminados.

from django.db import migrations


ORPHAN_CONTENT_TYPES = (
    ("core", "pastorsede"),
    ("guias", "ministerio"),
    ("guias", "personanueva"),
    ("guias", "eventoespecial"),
    ("guias", "seguimiento"),
    ("guias", "interesministerio"),
)


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    for app_label, model in ORPHAN_CONTENT_TYPES:
        cts = ContentType.objects.filter(app_label=app_label, model=model)
        for ct in cts:
            Permission.objects.filter(content_type_id=ct.id).delete()
            ct.delete()


def backwards(apps, schema_editor):
    # No recreamos modelos eliminados; los ContentType se regenerarían solo si existieran.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0014_remove_sede_foto_pastor_and_more"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
