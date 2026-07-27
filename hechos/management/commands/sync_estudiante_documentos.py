from django.core.management.base import BaseCommand

from hechos.models import Estudiante
from hechos.estudiante_documento import sincronizar_documento_estudiante


class Command(BaseCommand):
    help = (
        "Sincroniza User.documento_identidad y Estudiante.numero_documento "
        "(rellena el vacío o alinea si difieren; prioriza el User)."
    )

    def handle(self, *args, **options):
        synced = 0
        for est in Estudiante.objects.select_related("user").iterator():
            before_u = (est.user.documento_identidad or "").strip()
            before_e = (est.numero_documento or "").strip()
            after = sincronizar_documento_estudiante(est)
            if after and (after != before_u or after != before_e):
                synced += 1
        self.stdout.write(
            self.style.SUCCESS(f"Sincronización lista ({synced} perfil(es) actualizados).")
        )
