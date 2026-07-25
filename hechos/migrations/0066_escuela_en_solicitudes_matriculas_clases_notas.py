# Migración de datos: solicitud / matrícula / clase / nota ancladas a Escuela;
# horarios en EscuelaHorario; eliminación de EdicionCurso y EdicionCursoHorario.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, edicion_id):
    if not edicion_id:
        return None
    ec = EdicionCurso.objects.filter(pk=edicion_id).first()
    if not ec or not ec.curso_id:
        return None
    curso = Curso.objects.filter(pk=ec.curso_id).first()
    if not curso or not curso.ruta_estudio_id:
        return None
    ruta = RutaEstudio.objects.filter(pk=curso.ruta_estudio_id).first()
    if not ruta or not ruta.escuela_id:
        return None
    return ruta.escuela_id


def _escuela_id_desde_curso(Curso, RutaEstudio, curso_id):
    if not curso_id:
        return None
    curso = Curso.objects.filter(pk=curso_id).first()
    if not curso or not curso.ruta_estudio_id:
        return None
    ruta = RutaEstudio.objects.filter(pk=curso.ruta_estudio_id).first()
    if not ruta or not ruta.escuela_id:
        return None
    return ruta.escuela_id


def forwards_copiar_horarios_ed_a_escuela(apps, schema_editor):
    EdicionCursoHorario = apps.get_model("hechos", "EdicionCursoHorario")
    EdicionCurso = apps.get_model("hechos", "EdicionCurso")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")
    EscuelaHorario = apps.get_model("hechos", "EscuelaHorario")

    for h in EdicionCursoHorario.objects.all():
        eid = _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, h.edicion_id)
        if not eid:
            continue
        if EscuelaHorario.objects.filter(escuela_id=eid, dia_semana=h.dia_semana).exists():
            continue
        EscuelaHorario.objects.create(
            escuela_id=eid,
            dia_semana=h.dia_semana,
            hora=h.hora,
        )


def forwards_rellenar_escuela_desde_ediciones(apps, schema_editor):
    """Copia fechas/cupo/modalidad/aula/horario desde una edición representativa por escuela."""
    EdicionCurso = apps.get_model("hechos", "EdicionCurso")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")
    Escuela = apps.get_model("hechos", "Escuela")

    escuela_por_id = {e.pk: e for e in Escuela.objects.all()}
    mejor = {}

    for ec in EdicionCurso.objects.filter(is_active=True).order_by("-fecha_inicio", "-id"):
        eid = _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, ec.pk)
        if not eid or eid not in escuela_por_id:
            continue
        if eid not in mejor:
            mejor[eid] = ec

    for eid, ec in mejor.items():
        e = escuela_por_id[eid]
        if getattr(ec, "fecha_inicio", None):
            e.fecha_inicio = ec.fecha_inicio
        if getattr(ec, "fecha_fin", None):
            e.fecha_fin = ec.fecha_fin
        if getattr(ec, "modalidad", None):
            e.modalidad = ec.modalidad
        if getattr(ec, "horario", None) is not None:
            e.horario = ec.horario or ""
        if getattr(ec, "aula", None) is not None:
            e.aula = ec.aula or ""
        if getattr(ec, "cupo_maximo", None) is not None:
            e.cupo_maximo = ec.cupo_maximo
        e.save(
            update_fields=[
                "fecha_inicio",
                "fecha_fin",
                "modalidad",
                "horario",
                "aula",
                "cupo_maximo",
            ]
        )


def forwards_solicitudes_escuela(apps, schema_editor):
    SolicitudMatricula = apps.get_model("hechos", "SolicitudMatricula")
    EdicionCurso = apps.get_model("hechos", "EdicionCurso")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")

    for sol in SolicitudMatricula.objects.all():
        if sol.escuela_id:
            continue
        eid = _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, sol.edicion_curso_id)
        if eid:
            sol.escuela_id = eid
            sol.save(update_fields=["escuela_id"])

    SolicitudMatricula.objects.filter(escuela__isnull=True).delete()

    seen = set()
    for sol in SolicitudMatricula.objects.order_by("estudiante_id", "escuela_id", "id"):
        key = (sol.estudiante_id, sol.escuela_id)
        if key in seen:
            sol.delete()
        else:
            seen.add(key)


def forwards_matriculas_escuela(apps, schema_editor):
    Matricula = apps.get_model("hechos", "Matricula")
    EdicionCurso = apps.get_model("hechos", "EdicionCurso")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")

    for m in Matricula.objects.all():
        if m.escuela_id:
            continue
        eid = _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, m.edicion_curso_id)
        if eid:
            m.escuela_id = eid
            m.save(update_fields=["escuela_id"])

    Matricula.objects.filter(escuela__isnull=True).delete()

    seen = set()
    for m in Matricula.objects.order_by("estudiante_id", "escuela_id", "id"):
        key = (m.estudiante_id, m.escuela_id)
        if key in seen:
            m.delete()
        else:
            seen.add(key)


def forwards_clases_escuela(apps, schema_editor):
    Clase = apps.get_model("hechos", "Clase")
    EdicionCurso = apps.get_model("hechos", "EdicionCurso")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")

    for cl in Clase.objects.all():
        if cl.escuela_id:
            continue
        eid = _escuela_id_desde_edicion(EdicionCurso, Curso, RutaEstudio, cl.edicion_curso_id)
        if eid:
            cl.escuela_id = eid
            cl.save(update_fields=["escuela_id"])

    Clase.objects.filter(escuela__isnull=True).delete()


def forwards_notas_escuela(apps, schema_editor):
    Nota = apps.get_model("hechos", "Nota")
    Curso = apps.get_model("hechos", "Curso")
    RutaEstudio = apps.get_model("hechos", "RutaEstudio")

    for n in Nota.objects.all():
        if n.escuela_id:
            continue
        eid = _escuela_id_desde_curso(Curso, RutaEstudio, n.curso_id)
        if eid:
            n.escuela_id = eid
            n.save(update_fields=["escuela_id"])

    Nota.objects.filter(escuela__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0001_initial"),
        ("hechos", "0065_alter_escuela_options_alter_escuela_unique_together_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="escuela",
            name="fecha_inicio",
            field=models.DateField(blank=True, null=True, verbose_name="Inicio de clases"),
        ),
        migrations.AddField(
            model_name="escuela",
            name="fecha_fin",
            field=models.DateField(blank=True, null=True, verbose_name="Fin de clases"),
        ),
        migrations.AddField(
            model_name="escuela",
            name="modalidad",
            field=models.CharField(
                choices=[
                    ("presencial", "Presencial"),
                    ("virtual", "Virtual"),
                    ("hibrida", "Híbrida"),
                ],
                default="presencial",
                help_text="Modalidad de la escuela: presencial, virtual o híbrida.",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="escuela",
            name="horario",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Ej: Lunes y Miércoles 7:00 PM",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="escuela",
            name="aula",
            field=models.CharField(blank=True, default="", max_length=50),
        ),
        migrations.AddField(
            model_name="escuela",
            name="cupo_maximo",
            field=models.PositiveIntegerField(
                default=30, help_text="Cupo máximo de estudiantes"
            ),
        ),
        migrations.CreateModel(
            name="EscuelaHorario",
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
                    "dia_semana",
                    models.IntegerField(
                        choices=[
                            (0, "Lunes"),
                            (1, "Martes"),
                            (2, "Miércoles"),
                            (3, "Jueves"),
                            (4, "Viernes"),
                            (5, "Sábado"),
                            (6, "Domingo"),
                        ]
                    ),
                ),
                ("hora", models.TimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "escuela",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="estructura_horarios",
                        to="hechos.escuela",
                    ),
                ),
            ],
            options={
                "verbose_name": "Horario de escuela",
                "verbose_name_plural": "Horarios de escuela",
                "ordering": ["escuela", "dia_semana", "hora"],
            },
        ),
        migrations.AddConstraint(
            model_name="escuelahorario",
            constraint=models.UniqueConstraint(
                fields=("escuela", "dia_semana"),
                name="uniq_escuela_dia_semana",
            ),
        ),
        migrations.RunPython(forwards_copiar_horarios_ed_a_escuela, noop_reverse),
        migrations.DeleteModel(name="EdicionCursoHorario"),
        migrations.RunPython(forwards_rellenar_escuela_desde_ediciones, noop_reverse),
        migrations.AddField(
            model_name="solicitudmatricula",
            name="escuela",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solicitudes_matricula",
                to="hechos.escuela",
            ),
        ),
        migrations.RunPython(forwards_solicitudes_escuela, noop_reverse),
        migrations.AlterUniqueTogether(
            name="solicitudmatricula",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="solicitudmatricula",
            name="edicion_curso",
        ),
        migrations.AlterField(
            model_name="solicitudmatricula",
            name="escuela",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solicitudes_matricula",
                to="hechos.escuela",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="solicitudmatricula",
            unique_together={("estudiante", "escuela")},
        ),
        migrations.AddField(
            model_name="matricula",
            name="escuela",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="matriculas",
                to="hechos.escuela",
            ),
        ),
        migrations.RunPython(forwards_matriculas_escuela, noop_reverse),
        migrations.AlterUniqueTogether(
            name="matricula",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="matricula",
            name="edicion_curso",
        ),
        migrations.AlterField(
            model_name="matricula",
            name="escuela",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="matriculas",
                to="hechos.escuela",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="matricula",
            unique_together={("estudiante", "escuela")},
        ),
        migrations.AddField(
            model_name="clase",
            name="escuela",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="clases",
                to="hechos.escuela",
            ),
        ),
        migrations.RunPython(forwards_clases_escuela, noop_reverse),
        migrations.AlterUniqueTogether(
            name="clase",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="clase",
            name="edicion_curso",
        ),
        migrations.AlterField(
            model_name="clase",
            name="escuela",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="clases",
                to="hechos.escuela",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="clase",
            unique_together={("escuela", "numero_clase")},
        ),
        migrations.AlterModelOptions(
            name="clase",
            options={
                "ordering": ["escuela", "numero_clase"],
                "verbose_name": "Clase",
                "verbose_name_plural": "Clases",
            },
        ),
        migrations.AddField(
            model_name="nota",
            name="escuela",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notas_legacy",
                to="hechos.escuela",
            ),
        ),
        migrations.RunPython(forwards_notas_escuela, noop_reverse),
        migrations.RemoveField(
            model_name="nota",
            name="curso",
        ),
        migrations.AlterField(
            model_name="nota",
            name="escuela",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="notas_legacy",
                to="hechos.escuela",
            ),
        ),
        migrations.DeleteModel(name="EdicionCurso"),
    ]
