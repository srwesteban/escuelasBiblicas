from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Obsoleto: no hay múltiples ediciones por curso.'

    def handle(self, *args, **options):
        raise CommandError('Este comando está obsoleto.')
