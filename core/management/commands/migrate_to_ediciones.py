from django.core.management.base import BaseCommand
from django.db import transaction
from hechos.models import Curso, EdicionCurso, Matricula, Clase
from core.models import Sede


class Command(BaseCommand):
    help = 'Migra cursos existentes a ediciones de curso'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Ejecutar sin hacer cambios reales',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODO DRY-RUN: No se realizarán cambios reales'))
        
        try:
            with transaction.atomic():
                # Obtener todas las sedes
                sedes = Sede.objects.all()
                
                for sede in sedes:
                    self.stdout.write(f'Procesando sede: {sede.nombre}')
                    
                    # Obtener cursos de la sede
                    cursos = Curso.objects.filter(sede=sede)
                    
                    for curso in cursos:
                        self.stdout.write(f'  Procesando curso: {curso.nombre}')
                        
                        # Crear una edición por defecto para cada curso
                        if not dry_run:
                            edicion = EdicionCurso.objects.create(
                                curso=curso,
                                nombre_edicion='Grupo Principal',
                                profesor=None,  # Se asignará después si es necesario
                                fecha_inicio=curso.created_at.date(),
                                fecha_fin=curso.created_at.date(),
                                horario='Por definir',
                                aula='Por definir',
                                cupo_maximo=30,
                                is_active=curso.is_active
                            )
                            
                            # Migrar matrículas existentes (si las hay)
                            matriculas = Matricula.objects.filter(
                                sede=sede,
                                edicion_curso__isnull=True
                            )
                            
                            for matricula in matriculas:
                                matricula.edicion_curso = edicion
                                matricula.save()
                            
                            # Migrar clases existentes (si las hay)
                            clases = Clase.objects.filter(
                                sede=sede,
                                edicion_curso__isnull=True
                            )
                            
                            for clase in clases:
                                clase.edicion_curso = edicion
                                clase.save()
                            
                            self.stdout.write(f'    ✓ Creada edición: {edicion.nombre_edicion}')
                            self.stdout.write(f'    ✓ Migradas {matriculas.count()} matrículas')
                            self.stdout.write(f'    ✓ Migradas {clases.count()} clases')
                        else:
                            matriculas_count = Matricula.objects.filter(sede=sede, edicion_curso__isnull=True).count()
                            clases_count = Clase.objects.filter(sede=sede, edicion_curso__isnull=True).count()
                            self.stdout.write(f'    [DRY-RUN] Se crearía edición "Grupo Principal"')
                            self.stdout.write(f'    [DRY-RUN] Se migrarían {matriculas_count} matrículas')
                            self.stdout.write(f'    [DRY-RUN] Se migrarían {clases_count} clases')
                
                if dry_run:
                    self.stdout.write(self.style.SUCCESS('DRY-RUN completado. No se realizaron cambios.'))
                else:
                    self.stdout.write(self.style.SUCCESS('Migración completada exitosamente!'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante la migración: {str(e)}'))
            raise
