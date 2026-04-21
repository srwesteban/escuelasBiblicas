from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Sede


@receiver(post_save, sender=Sede)
def sede_creada_sembrar_programa_formacion(sender, instance, created, **kwargs):
    if not created:
        return
    from hechos.programa_formacion_seed import sembrar_programa_formacion_en_sede

    sembrar_programa_formacion_en_sede(instance)
