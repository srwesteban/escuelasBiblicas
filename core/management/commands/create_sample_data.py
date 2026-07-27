from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import UserAppPermission, AppModule
from hechos.models import (
    Estudiante, Profesor, AdminEscuela, RutaEstudio, Curso, 
    Matricula, Clase, Asistencia, Nota
)
from datetime import datetime, timedelta
from decimal import Decimal

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea datos de ejemplo para probar el sistema'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creando datos de ejemplo...'))
        
        # Crear usuarios de ejemplo
        self.create_sample_users()
        
        # Crear perfiles específicos
        self.create_sample_profiles()
        
        # Crear cursos de ejemplo
        self.create_sample_courses()
        
        # Crear matrículas
        self.create_sample_enrollments()
        
        # Crear clases
        self.create_sample_classes()
        
        # Crear notas de ejemplo
        self.create_sample_grades()
        
        self.stdout.write(self.style.SUCCESS('¡Datos de ejemplo creados exitosamente!'))

    def create_sample_users(self):
        """Crear usuarios de ejemplo"""
        users_data = [
            {
                'email': 'estudiante1@ejemplo.com',
                'username': 'estudiante1',
                'first_name': 'María',
                'last_name': 'González',
                'role': 'user'
            },
            {
                'email': 'estudiante2@ejemplo.com',
                'username': 'estudiante2',
                'first_name': 'Juan',
                'last_name': 'Pérez',
                'role': 'user'
            },
            {
                'email': 'profesor1@ejemplo.com',
                'username': 'profesor1',
                'first_name': 'Pastor',
                'last_name': 'Rodríguez',
                'role': 'user'
            },
            {
                'email': 'admin1@ejemplo.com',
                'username': 'admin1',
                'first_name': 'Administrador',
                'last_name': 'Iglesia',
                'role': 'app_admin'
            }
        ]
        
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                email=user_data['email'],
                defaults={
                    'username': user_data['username'],
                    'first_name': user_data['first_name'],
                    'last_name': user_data['last_name'],
                    'role': user_data['role'],
                    'is_verified': True
                }
            )
            if created:
                user.set_password('password123')
                user.save()
                self.stdout.write(f'✓ Usuario {user.get_full_name()} creado')
            else:
                self.stdout.write(f'✓ Usuario {user.get_full_name()} ya existe')

    def create_sample_profiles(self):
        """Crear perfiles específicos"""
        # Estudiante 1
        try:
            user1 = User.objects.get(email='estudiante1@ejemplo.com')
            estudiante1, created = Estudiante.objects.get_or_create(
                user=user1,
                defaults={
                    'telefono_emergencia': '555-0001',
                }
            )
            if created:
                self.stdout.write('✓ Perfil de estudiante 1 creado')
        except User.DoesNotExist:
            pass
        
        # Estudiante 2
        try:
            user2 = User.objects.get(email='estudiante2@ejemplo.com')
            estudiante2, created = Estudiante.objects.get_or_create(
                user=user2,
                defaults={
                    'telefono_emergencia': '555-0002',
                }
            )
            if created:
                self.stdout.write('✓ Perfil de estudiante 2 creado')
        except User.DoesNotExist:
            pass
        
        # Profesor
        try:
            user3 = User.objects.get(email='profesor1@ejemplo.com')
            profesor, created = Profesor.objects.get_or_create(
                user=user3,
                defaults={}
            )
            if created:
                self.stdout.write('✓ Perfil de profesor creado')
        except User.DoesNotExist:
            pass
        
        # Admin de Escuela
        try:
            user4 = User.objects.get(email='admin1@ejemplo.com')
            admin, created = AdminEscuela.objects.get_or_create(
                user=user4,
                defaults={
                    'escuela': 'Escuela Bíblica Central',
                    'cargo': 'Director Académico'
                }
            )
            if created:
                self.stdout.write('✓ Perfil de administrador creado')
        except User.DoesNotExist:
            pass

    def create_sample_courses(self):
        """Crear cursos de ejemplo"""
        try:
            ruta = RutaEstudio.objects.first()
            profesor = Profesor.objects.first()
            
            if ruta and profesor:
                curso, created = Curso.objects.get_or_create(
                    nombre='Fundamentos de la Fe - Grupo A',
                    defaults={
                        'ruta_estudio': ruta,
                        'profesor': profesor,
                        'descripcion': 'Curso básico de fundamentos de la fe cristiana',
                        'fecha_inicio': datetime.now().date(),
                        'fecha_fin': (datetime.now() + timedelta(days=90)).date(),
                        'horario': 'Lunes y Miércoles 7:00 PM - 8:30 PM',
                        'aula': 'Aula 1',
                        'capacidad_maxima': 25
                    }
                )
                if created:
                    self.stdout.write('✓ Curso de ejemplo creado')
        except Exception as e:
            self.stdout.write(f'Error creando curso: {e}')

    def create_sample_enrollments(self):
        """Crear matrículas de ejemplo"""
        try:
            curso = Curso.objects.first()
            estudiantes = Estudiante.objects.all()[:2]
            
            for estudiante in estudiantes:
                matricula, created = Matricula.objects.get_or_create(
                    estudiante=estudiante,
                    curso=curso,
                    defaults={'estado': 'activa'}
                )
                if created:
                    self.stdout.write(f'✓ Matrícula para {estudiante.user.get_full_name()} creada')
        except Exception as e:
            self.stdout.write(f'Error creando matrículas: {e}')

    def create_sample_classes(self):
        """Crear clases de ejemplo"""
        try:
            curso = Curso.objects.first()
            if curso:
                for i in range(1, 4):
                    clase, created = Clase.objects.get_or_create(
                        curso=curso,
                        numero_clase=i,
                        defaults={
                            'titulo': f'Clase {i}: Introducción a la Fe',
                            'descripcion': f'Descripción de la clase {i}',
                            'fecha_clase': datetime.now() + timedelta(days=i*7),
                            'duracion_minutos': 90,
                            'profesor': curso.profesor,
                            'aula': 'Aula 1'
                        }
                    )
                    if created:
                        self.stdout.write(f'✓ Clase {i} creada')
        except Exception as e:
            self.stdout.write(f'Error creando clases: {e}')

    def create_sample_grades(self):
        """Crear notas de ejemplo"""
        try:
            curso = Curso.objects.first()
            estudiantes = Estudiante.objects.all()[:2]
            
            for estudiante in estudiantes:
                nota, created = Nota.objects.get_or_create(
                    estudiante=estudiante,
                    curso=curso,
                    titulo='Evaluación Parcial 1',
                    defaults={
                        'tipo': 'parcial',
                        'descripcion': 'Primera evaluación parcial del curso',
                        'puntaje_obtenido': Decimal('85.00'),
                        'puntaje_maximo': Decimal('100.00'),
                        'fecha_evaluacion': datetime.now().date(),
                        'profesor': curso.profesor,
                        'observaciones': 'Excelente trabajo'
                    }
                )
                if created:
                    self.stdout.write(f'✓ Nota para {estudiante.user.get_full_name()} creada')
        except Exception as e:
            self.stdout.write(f'Error creando notas: {e}')
