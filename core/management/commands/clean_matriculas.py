from django.core.management.base import BaseCommand
from hechos.models import Matricula, EdicionCurso, Curso
from django.db import transaction

class Command(BaseCommand):
    help = 'Limpia matrículas sin edición de curso asignada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Eliminar matrículas sin edición de curso (por defecto solo muestra)',
        )

    def handle(self, *args, **options):
        # Buscar matrículas sin edicion_curso
        matriculas_sin_edicion = Matricula.objects.filter(edicion_curso__isnull=True)
        
        self.stdout.write(f"Matrículas sin edición de curso: {matriculas_sin_edicion.count()}")
        
        if matriculas_sin_edicion.count() > 0:
            self.stdout.write("\nMatrículas problemáticas:")
            for matricula in matriculas_sin_edicion:
                self.stdout.write(
                    f"- ID: {matricula.id}, Estudiante: {matricula.estudiante.user.get_full_name()}, "
                    f"Fecha: {matricula.fecha_matricula}"
                )
        
        if options['delete']:
            with transaction.atomic():
                deleted_count = matriculas_sin_edicion.count()
                matriculas_sin_edicion.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Se eliminaron {deleted_count} matrículas sin edición de curso.')
                )
        else:
            self.stdout.write(
                self.style.WARNING('Usa --delete para eliminar estas matrículas.')
            )
            
        # Verificar ediciones de curso sin curso
        ediciones_sin_curso = EdicionCurso.objects.filter(curso__isnull=True)
        
        self.stdout.write(f"\nEdiciones sin curso: {ediciones_sin_curso.count()}")
        
        if ediciones_sin_curso.count() > 0:
            self.stdout.write("\nEdiciones problemáticas:")
            for edicion in ediciones_sin_curso:
                self.stdout.write(
                    f"- ID: {edicion.id}, Nombre: {edicion.nombre_edicion}"
                )
        
        if options['delete'] and ediciones_sin_curso.count() > 0:
            with transaction.atomic():
                deleted_ediciones = ediciones_sin_curso.count()
                ediciones_sin_curso.delete()
                self.stdout.write(
                    self.style.SUCCESS(f'Se eliminaron {deleted_ediciones} ediciones sin curso.')
                )

