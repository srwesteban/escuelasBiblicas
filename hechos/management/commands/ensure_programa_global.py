from django.core.management.base import BaseCommand

from hechos.catalogo_formacion import ensure_programa_plantillas


class Command(BaseCommand):
    help = (
        "Asegura el catálogo de Formación global (NivelProgramaPlantilla y "
        "EscuelaProgramaPlantilla) desde hechos/catalogo_formacion.py. "
        "No toca sedes, usuarios ni matrículas. Útil tras migrate en una BD nueva."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-update",
            action="store_true",
            help="Solo crea filas faltantes; no actualiza nombre/descripción/matrícula existentes.",
        )

    def handle(self, *args, **options):
        stats = ensure_programa_plantillas(update_existing=not options["no_update"])
        self.stdout.write(
            self.style.SUCCESS(
                "Formación global OK — "
                f"niveles +{stats['niveles_creados']}/~{stats['niveles_actualizados']}, "
                f"escuelas +{stats['escuelas_creadas']}/~{stats['escuelas_actualizadas']}"
            )
        )
