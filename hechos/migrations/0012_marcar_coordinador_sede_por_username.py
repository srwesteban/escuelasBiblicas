from django.db import migrations


def forwards(apps, schema_editor):
    AdminEscuela = apps.get_model('hechos', 'AdminEscuela')
    for ae in AdminEscuela.objects.filter(is_active=True).select_related('user', 'sede'):
        user = ae.user
        if not user:
            continue
        un = (user.username or '').lower()
        em = (user.email or '').lower()
        if 'coordinadorsede' in un or 'coordinadorsede' in em:
            ae.tipo_coordinador = 'sede'
            if ae.sede_id:
                ae.cargo = f'Coordinador de sede — {ae.sede.nombre}'
            ae.save(update_fields=['tipo_coordinador', 'cargo'])


def backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hechos', '0011_adminescuela_tipo_coordinador'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
