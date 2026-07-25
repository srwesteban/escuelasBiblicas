from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Obsoleto: ya no existen ediciones; la oferta se configura en Escuela.'

    def handle(self, *args, **options):
        raise CommandError(
            'Este comando está obsoleto. Crea o edita escuelas operativas y el asistente de estructura en la app.'
        )
