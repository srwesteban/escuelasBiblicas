from django.core.management.base import BaseCommand
from django.db import transaction

from hechos.models import Matricula


class Command(BaseCommand):
    help = 'Lista o elimina matrículas sin escuela operativa asignada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Eliminar matrículas sin escuela (por defecto solo muestra)',
        )

    def handle(self, *args, **options):
        qs = Matricula.objects.filter(escuela__isnull=True)
        n = qs.count()
        self.stdout.write(f'Matrículas sin escuela: {n}')
        if n > 0:
            self.stdout.write('\nMatrículas problemáticas:')
            for matricula in qs[:500]:
                self.stdout.write(
                    f"- ID: {matricula.id}, Estudiante: {matricula.estudiante.user.get_full_name()}, "
                    f"Fecha: {matricula.fecha_matricula}"
                )
            if n > 500:
                self.stdout.write(f'… y {n - 500} más.')
        if options['delete'] and n > 0:
            with transaction.atomic():
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f'Se eliminaron {deleted} filas relacionadas (incl. matrículas).'))
        elif n > 0:
            self.stdout.write(self.style.WARNING('Usa --delete para eliminar estas matrículas.'))
