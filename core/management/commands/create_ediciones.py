from django.core.management.base import BaseCommand
from django.db import transaction
from hechos.models import Curso, EdicionCurso
from core.models import Sede


class Command(BaseCommand):
    help = 'Crea ediciones de curso para cursos existentes'

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
                        
                        # Verificar si ya existe una edición para este curso
                        edicion_existente = EdicionCurso.objects.filter(curso=curso).first()
                        
                        if edicion_existente:
                            self.stdout.write(f'    ✓ Ya existe edición: {edicion_existente.nombre_edicion}')
                            continue
                        
                        # Crear una edición por defecto para cada curso
                        if not dry_run:
                            edicion = EdicionCurso.objects.create(
                                curso=curso,
                                nombre_edicion='Grupo Principal',
                                profesor=None,
                                fecha_inicio=curso.created_at.date(),
                                fecha_fin=curso.created_at.date(),
                                horario='Por definir',
                                aula='Por definir',
                                cupo_maximo=30,
                                is_active=curso.is_active
                            )
                            
                            self.stdout.write(f'    ✓ Creada edición: {edicion.nombre_edicion}')
                        else:
                            self.stdout.write(f'    [DRY-RUN] Se crearía edición "Grupo Principal"')
                
                if dry_run:
                    self.stdout.write(self.style.SUCCESS('DRY-RUN completado. No se realizaron cambios.'))
                else:
                    self.stdout.write(self.style.SUCCESS('Creación de ediciones completada exitosamente!'))
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante la creación: {str(e)}'))
            raise
