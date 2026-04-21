# Generated manually — textos sin la palabra «ámbito»

from django.db import migrations


def actualizar_textos(apps, schema_editor):
    CapacidadCoordinador = apps.get_model('hechos', 'CapacidadCoordinador')
    actualizaciones = [
        (
            'academico',
            'Académico (estudiantes, matrículas, solicitudes)',
            'Tareas académicas: estudiantes, matrículas, solicitudes y lo compartido con lo pedagógico.',
        ),
        (
            'pedagogico',
            'Pedagógico (profesores, estructura de ediciones)',
            'Tareas pedagógicas: profesores, estructura de ediciones y lo compartido con lo académico.',
        ),
        (
            'financiero',
            'Financiero (recursos, ofrendas, presupuestos)',
            'Recursos de la sede: ofrendas, recaudos y presupuesto de eventos.',
        ),
        (
            'logistico',
            'Logístico (salones y espacios)',
            'Salones y asignación por escuela.',
        ),
    ]
    for codigo, nombre, descripcion in actualizaciones:
        CapacidadCoordinador.objects.filter(codigo=codigo).update(nombre=nombre, descripcion=descripcion)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hechos', '0040_adminescuela_capacidades_explicitas'),
    ]

    operations = [
        migrations.RunPython(actualizar_textos, noop),
    ]
