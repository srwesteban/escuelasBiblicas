from django.core.management.base import BaseCommand
from django.db import transaction
from hechos.models import Curso, EdicionCurso, Profesor
from core.models import Sede
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Crea múltiples ediciones para un curso específico'

    def add_arguments(self, parser):
        parser.add_argument(
            '--curso-id',
            type=int,
            required=True,
            help='ID del curso para crear ediciones',
        )
        parser.add_argument(
            '--ediciones',
            nargs='+',
            default=['Grupo A', 'Grupo B'],
            help='Nombres de las ediciones a crear',
        )
        parser.add_argument(
            '--profesor-id',
            type=int,
            help='ID del profesor para asignar a las ediciones',
        )
        parser.add_argument(
            '--fecha-inicio',
            type=str,
            help='Fecha de inicio en formato YYYY-MM-DD',
        )
        parser.add_argument(
            '--duracion-semanas',
            type=int,
            default=4,
            help='Duración en semanas',
        )

    def handle(self, *args, **options):
        curso_id = options['curso_id']
        ediciones = options['ediciones']
        profesor_id = options.get('profesor_id')
        fecha_inicio = options.get('fecha_inicio')
        duracion_semanas = options['duracion_semanas']
        
        try:
            with transaction.atomic():
                # Obtener el curso
                curso = Curso.objects.get(id=curso_id)
                self.stdout.write(f'Curso: {curso.nombre}')
                
                # Obtener profesor si se especificó
                profesor = None
                if profesor_id:
                    profesor = Profesor.objects.get(id=profesor_id)
                    self.stdout.write(f'Profesor: {profesor.user.get_full_name()}')
                
                # Calcular fechas
                if fecha_inicio:
                    fecha_inicio_obj = date.fromisoformat(fecha_inicio)
                else:
                    fecha_inicio_obj = date.today()
                
                fecha_fin_obj = fecha_inicio_obj + timedelta(weeks=duracion_semanas)
                
                # Crear ediciones
                for i, nombre_edicion in enumerate(ediciones):
                    # Verificar si ya existe
                    if EdicionCurso.objects.filter(curso=curso, nombre_edicion=nombre_edicion).exists():
                        self.stdout.write(f'  ⚠️  Edición "{nombre_edicion}" ya existe')
                        continue
                    
                    # Crear edición
                    edicion = EdicionCurso.objects.create(
                        curso=curso,
                        nombre_edicion=nombre_edicion,
                        profesor=profesor,
                        fecha_inicio=fecha_inicio_obj,
                        fecha_fin=fecha_fin_obj,
                        horario=f'Por definir - {nombre_edicion}',
                        aula=f'Aula {i+1}',
                        cupo_maximo=30,
                        is_active=True
                    )
                    
                    self.stdout.write(f'  ✓ Creada edición: {edicion.nombre_edicion}')
                    self.stdout.write(f'    - Fecha inicio: {fecha_inicio_obj}')
                    self.stdout.write(f'    - Fecha fin: {fecha_fin_obj}')
                    self.stdout.write(f'    - Profesor: {profesor.user.get_full_name() if profesor else "Sin asignar"}')
                    self.stdout.write(f'    - Aula: {edicion.aula}')
                    self.stdout.write(f'    - Cupo: {edicion.cupo_maximo}')
                
                self.stdout.write(self.style.SUCCESS(f'¡Creadas {len(ediciones)} ediciones para el curso {curso.nombre}!'))
                
        except Curso.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Curso con ID {curso_id} no encontrado'))
        except Profesor.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Profesor con ID {profesor_id} no encontrado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            raise
