from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Obsoleto: la migración de datos de edición a escuela debe hacerse con migraciones Django 0066+.'

    def handle(self, *args, **options):
        raise CommandError(
            'Este comando está obsoleto. Usa las migraciones del app hechos para alinear la base de datos.'
        )
