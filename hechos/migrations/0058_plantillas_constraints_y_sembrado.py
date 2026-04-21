# Índices únicos parciales + datos (transacción separada: evita error PG con triggers pendientes).

from django.db import migrations, models
from django.db.models import Q


def seed_plantillas_desde_sede_referencia_y_sembrar_todas(apps, schema_editor):
    Sede = apps.get_model("core", "Sede")
    NP = apps.get_model("hechos", "NivelPrograma")
    EP = apps.get_model("hechos", "EscuelaPrograma")
    NPP = apps.get_model("hechos", "NivelProgramaPlantilla")
    EPP = apps.get_model("hechos", "EscuelaProgramaPlantilla")

    ref_pk = None
    for pk in Sede.objects.order_by("pk").values_list("pk", flat=True):
        if NP.objects.filter(sede_id=pk).exists():
            ref_pk = pk
            break
    if not ref_pk:
        return

    old_np_to_pl = {}
    for np in NP.objects.filter(sede_id=ref_pk).order_by("jerarquia"):
        pl, _ = NPP.objects.update_or_create(
            jerarquia=np.jerarquia,
            defaults={
                "nombre": np.nombre,
                "descripcion": np.descripcion or "",
            },
        )
        old_np_to_pl[np.pk] = pl

    for ep in EP.objects.filter(sede_id=ref_pk).order_by("nivel_programa_id", "nombre"):
        pl_n = old_np_to_pl.get(ep.nivel_programa_id)
        if not pl_n:
            continue
        EPP.objects.update_or_create(
            nivel_plantilla_id=pl_n.pk,
            nombre=ep.nombre,
            defaults={
                "descripcion": ep.descripcion or "",
                "tiene_matricula": ep.tiene_matricula,
                "costo_matricula_cop": ep.costo_matricula_cop,
            },
        )

    for np in NP.objects.all():
        pl = NPP.objects.filter(jerarquia=np.jerarquia).first()
        if not pl or np.plantilla_id:
            continue
        if NP.objects.filter(sede_id=np.sede_id, plantilla_id=pl.pk).exclude(pk=np.pk).exists():
            continue
        np.plantilla_id = pl.pk
        np.save(update_fields=["plantilla_id"])

    for ep in EP.objects.all():
        if ep.plantilla_id:
            continue
        np_row = NP.objects.filter(pk=ep.nivel_programa_id).first()
        if not np_row:
            continue
        npl = NPP.objects.filter(jerarquia=np_row.jerarquia).first()
        if not npl:
            continue
        epl = EPP.objects.filter(nivel_plantilla_id=npl.pk, nombre=ep.nombre).first()
        if not epl:
            continue
        if EP.objects.filter(sede_id=ep.sede_id, plantilla_id=epl.pk).exclude(pk=ep.pk).exists():
            continue
        ep.plantilla_id = epl.pk
        ep.save(update_fields=["plantilla_id"])

    npp_ordered = list(NPP.objects.order_by("jerarquia"))
    epp_ordered = list(EPP.objects.order_by("nivel_plantilla_id", "nombre"))
    for sede in Sede.objects.all():
        for npl in npp_ordered:
            nivel, created = NP.objects.get_or_create(
                sede_id=sede.pk,
                jerarquia=npl.jerarquia,
                defaults={
                    "nombre": npl.nombre,
                    "descripcion": npl.descripcion or "",
                    "is_active": True,
                    "plantilla_id": npl.pk,
                },
            )
            if not created and nivel.plantilla_id != npl.pk:
                nivel.plantilla_id = npl.pk
                nivel.save(update_fields=["plantilla_id"])

        for epl in epp_ordered:
            nj = NPP.objects.filter(pk=epl.nivel_plantilla_id).first()
            if not nj:
                continue
            nivel = NP.objects.filter(sede_id=sede.pk, jerarquia=nj.jerarquia).first()
            if not nivel:
                continue
            ep_obj, created = EP.objects.get_or_create(
                sede_id=sede.pk,
                nivel_programa_id=nivel.pk,
                nombre=epl.nombre,
                defaults={
                    "descripcion": epl.descripcion or "",
                    "tiene_matricula": epl.tiene_matricula,
                    "costo_matricula_cop": epl.costo_matricula_cop,
                    "is_active": True,
                    "plantilla_id": epl.pk,
                },
            )
            if not created and ep_obj.plantilla_id != epl.pk:
                ep_obj.plantilla_id = epl.pk
                ep_obj.save(update_fields=["plantilla_id"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("hechos", "0057_plantillas_programa_formacion_global"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="escuelaprograma",
            constraint=models.UniqueConstraint(
                condition=Q(plantilla__isnull=False),
                fields=("sede", "plantilla"),
                name="uniq_hechos_escuela_programa_sede_plantilla",
            ),
        ),
        migrations.AddConstraint(
            model_name="nivelprograma",
            constraint=models.UniqueConstraint(
                condition=Q(plantilla__isnull=False),
                fields=("sede", "plantilla"),
                name="uniq_hechos_nivel_programa_sede_plantilla",
            ),
        ),
        migrations.RunPython(
            seed_plantillas_desde_sede_referencia_y_sembrar_todas,
            noop_reverse,
        ),
    ]
