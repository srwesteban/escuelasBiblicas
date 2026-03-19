from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede
from hechos.models import Estudiante, Profesor, RutaEstudio, Curso, Matricula, Clase, Asistencia, Nota
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea clases de prueba para las sedes existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='ID de la sede específica (si no se especifica, se crean para todas las sedes)'
        )

    def handle(self, *args, **options):
        sede_id = options.get('sede_id')
        
        if sede_id:
            try:
                sedes = [Sede.objects.get(id=sede_id)]
            except Sede.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ No se encontró la sede con ID {sede_id}')
                )
                return
        else:
            sedes = Sede.objects.filter(is_active=True)
        
        if not sedes.exists():
            self.stdout.write(
                self.style.ERROR('❌ No hay sedes activas disponibles')
            )
            return
        
        for sede in sedes:
            self.stdout.write(
                self.style.SUCCESS(f'\n🏢 Procesando sede: {sede.nombre}')
            )
            
            # Obtener profesores de la sede
            profesores = Profesor.objects.filter(sede=sede, is_active=True)
            if not profesores.exists():
                self.stdout.write(
                    self.style.WARNING(f'⚠️  No hay profesores en la sede {sede.nombre}')
                )
                continue
            
            # Obtener cursos de la sede
            cursos = Curso.objects.filter(sede=sede, is_active=True)
            if not cursos.exists():
                self.stdout.write(
                    self.style.WARNING(f'⚠️  No hay cursos en la sede {sede.nombre}')
                )
                continue
            
            # Crear clases para cada curso
            clases_creadas = 0
            for curso in cursos:
                # Crear 8 clases para cada curso (2 meses de clases)
                for i in range(1, 9):
                    fecha_clase = datetime.now() + timedelta(days=i*7)  # Una clase por semana
                    
                    clase, created = Clase.objects.get_or_create(
                        sede=sede,
                        curso=curso,
                        numero_clase=i,
                        defaults={
                            'titulo': f'Clase {i}: {curso.nombre}',
                            'descripcion': f'Descripción de la clase {i} del curso {curso.nombre}',
                            'fecha_clase': fecha_clase,
                            'duracion_minutos': 90,
                            'profesor': curso.profesor,
                            'aula': f'Aula {i % 3 + 1}',
                            'is_active': True
                        }
                    )
                    
                    if created:
                        clases_creadas += 1
                        self.stdout.write(f'  ✅ Clase creada: {clase.titulo}')
            
            # Crear asistencias de ejemplo para las clases
            estudiantes = Estudiante.objects.filter(sede=sede, is_active=True)
            if estudiantes.exists():
                clases = Clase.objects.filter(sede=sede, is_active=True)
                asistencias_creadas = 0
                
                for clase in clases:
                    # Obtener estudiantes matriculados en el curso
                    estudiantes_curso = estudiantes.filter(
                        matriculas__curso=clase.curso,
                        matriculas__is_active=True
                    )
                    
                    for estudiante in estudiantes_curso:
                        # Crear asistencia aleatoria
                        estados = ['presente', 'ausente', 'tarde', 'justificado']
                        estado = random.choices(estados, weights=[70, 15, 10, 5])[0]
                        
                        asistencia, created = Asistencia.objects.get_or_create(
                            sede=sede,
                            clase=clase,
                            estudiante=estudiante,
                            defaults={
                                'estado': estado,
                                'observaciones': f'Asistencia registrada para {estudiante.user.get_full_name()}',
                                'registrado_por': clase.profesor.user if clase.profesor else None
                            }
                        )
                        
                        if created:
                            asistencias_creadas += 1
                
                self.stdout.write(f'  ✅ Creadas {asistencias_creadas} asistencias de ejemplo')
            
            # Crear notas de ejemplo
            if estudiantes.exists() and cursos.exists():
                notas_creadas = 0
                tipos_nota = ['parcial', 'final', 'tarea', 'participacion']
                
                for curso in cursos:
                    estudiantes_curso = estudiantes.filter(
                        matriculas__curso=curso,
                        matriculas__is_active=True
                    )
                    
                    for estudiante in estudiantes_curso:
                        # Crear 3-5 notas por estudiante por curso
                        num_notas = random.randint(3, 5)
                        for i in range(num_notas):
                            tipo = random.choice(tipos_nota)
                            puntaje_obtenido = random.randint(60, 100)
                            puntaje_maximo = 100
                            
                            nota, created = Nota.objects.get_or_create(
                                sede=sede,
                                estudiante=estudiante,
                                curso=curso,
                                titulo=f'{tipo.title()} {i+1}',
                                defaults={
                                    'tipo': tipo,
                                    'descripcion': f'Evaluación de {tipo} para {estudiante.user.get_full_name()}',
                                    'puntaje_obtenido': puntaje_obtenido,
                                    'puntaje_maximo': puntaje_maximo,
                                    'fecha_evaluacion': datetime.now().date() - timedelta(days=random.randint(1, 30)),
                                    'profesor': curso.profesor,
                                    'observaciones': f'Nota generada automáticamente para {estudiante.user.get_full_name()}'
                                }
                            )
                            
                            if created:
                                notas_creadas += 1
                
                self.stdout.write(f'  ✅ Creadas {notas_creadas} notas de ejemplo')
            
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Sede {sede.nombre} procesada exitosamente')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Proceso completado para {sedes.count()} sede(s)')
        )
