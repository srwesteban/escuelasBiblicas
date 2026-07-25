from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Obsoleto: el docente titular se asigna en el modelo Escuela (maestro).'

    def handle(self, *args, **options):
        raise CommandError(
            'Este comando está obsoleto. Asigna el maestro en cada Escuela desde el admin o el flujo pedagógico.'
        )
