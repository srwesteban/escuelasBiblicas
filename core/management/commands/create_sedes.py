from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede
from hechos.models import Estudiante, Profesor, AdminEscuela, RutaEstudio, Curso, Matricula, Clase, Asistencia, Nota
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea sedes de ejemplo y datos asociados'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-nombre',
            type=str,
            default='Sede Central',
            help='Nombre de la sede a crear'
        )
        parser.add_argument(
            '--sede-direccion',
            type=str,
            default='Calle Principal 123, Ciudad',
            help='Dirección de la sede'
        )
        parser.add_argument(
            '--sede-telefono',
            type=str,
            default='+1-234-567-8900',
            help='Teléfono de la sede'
        )
        parser.add_argument(
            '--sede-email',
            type=str,
            default='sede@iglesia.com',
            help='Email de la sede'
        )

    def handle(self, *args, **options):
        # Crear la sede
        sede, created = Sede.objects.get_or_create(
            nombre=options['sede_nombre'],
            defaults={
                'direccion': options['sede_direccion'],
                'telefono': options['sede_telefono'],
                'email': options['sede_email'],
                'descripcion': f'Sede {options["sede_nombre"]} de la iglesia',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Sede "{sede.nombre}" creada exitosamente')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️  La sede "{sede.nombre}" ya existe')
            )
        
        # Crear rutas de estudio para la sede
        rutas_data = [
            {
                'nombre': 'Fundamentos de la Fe',
                'descripcion': 'Curso básico sobre los fundamentos de la fe cristiana',
                'duracion_semanas': 12,
                'nivel': 'basico'
            },
            {
                'nombre': 'Estudio Bíblico Avanzado',
                'descripcion': 'Estudio profundo de las Escrituras',
                'duracion_semanas': 16,
                'nivel': 'avanzado'
            },
            {
                'nombre': 'Liderazgo Cristiano',
                'descripcion': 'Formación para líderes en la iglesia',
                'duracion_semanas': 14,
                'nivel': 'intermedio'
            }
        ]
        
        rutas_creadas = []
        for ruta_data in rutas_data:
            ruta, created = RutaEstudio.objects.get_or_create(
                sede=sede,
                nombre=ruta_data['nombre'],
                defaults=ruta_data
            )
            if created:
                rutas_creadas.append(ruta)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Ruta de estudio "{ruta.nombre}" creada')
                )
        
        # Crear usuarios de ejemplo
        usuarios_data = [
            {
                'username': f'admin_{sede.nombre.lower().replace(" ", "_")}',
                'email': f'admin@{sede.nombre.lower().replace(" ", "_")}.com',
                'first_name': 'Admin',
                'last_name': sede.nombre,
                'role': 'app_admin',
                'sede': sede
            },
            {
                'username': f'profesor_{sede.nombre.lower().replace(" ", "_")}',
                'email': f'profesor@{sede.nombre.lower().replace(" ", "_")}.com',
                'first_name': 'Profesor',
                'last_name': 'Ejemplo',
                'role': 'user',
                'sede': sede
            },
            {
                'username': f'estudiante_{sede.nombre.lower().replace(" ", "_")}',
                'email': f'estudiante@{sede.nombre.lower().replace(" ", "_")}.com',
                'first_name': 'Estudiante',
                'last_name': 'Ejemplo',
                'role': 'user',
                'sede': sede
            }
        ]
        
        usuarios_creados = []
        for user_data in usuarios_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults=user_data
            )
            if created:
                user.set_password('password123')
                user.save()
                usuarios_creados.append(user)
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Usuario "{user.username}" creado')
                )
        
        # Crear perfiles
        if len(usuarios_creados) >= 3:
            # Admin de escuela
            admin_user = usuarios_creados[0]
            admin_profile, created = AdminEscuela.objects.get_or_create(
                user=admin_user,
                defaults={
                    'sede': sede,
                    'cargo': 'Administrador de Escuela',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Perfil de admin creado para {admin_user.username}')
                )
            
            # Profesor
            profesor_user = usuarios_creados[1]
            profesor_profile, created = Profesor.objects.get_or_create(
                user=profesor_user,
                defaults={
                    'sede': sede,
                    'especialidad': 'Teología',
                    'experiencia_anos': 5,
                    'biografia': 'Profesor con experiencia en enseñanza bíblica',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Perfil de profesor creado para {profesor_user.username}')
                )
            
            # Estudiante
            estudiante_user = usuarios_creados[2]
            estudiante_profile, created = Estudiante.objects.get_or_create(
                user=estudiante_user,
                defaults={
                    'sede': sede,
                    'fecha_nacimiento': '1990-01-01',
                    'direccion': 'Dirección del estudiante',
                    'telefono_emergencia': '+1-234-567-8901',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Perfil de estudiante creado para {estudiante_user.username}')
                )
        
        # Crear cursos
        if rutas_creadas and len(usuarios_creados) >= 2:
            profesor_profile = Profesor.objects.filter(sede=sede).first()
            if profesor_profile:
                cursos_data = [
                    {
                        'ruta_estudio': rutas_creadas[0],
                        'nombre': 'Fundamentos de la Fe - Grupo A',
                        'descripcion': 'Curso básico de fundamentos de la fe',
                        'profesor': profesor_profile,
                        'fecha_inicio': datetime.now().date(),
                        'fecha_fin': (datetime.now() + timedelta(weeks=12)).date(),
                        'horario': 'Lunes y Miércoles 7:00 PM',
                        'aula': 'Aula 1',
                        'capacidad_maxima': 25
                    },
                    {
                        'ruta_estudio': rutas_creadas[1],
                        'nombre': 'Estudio Bíblico Avanzado - Grupo A',
                        'descripcion': 'Estudio profundo de las Escrituras',
                        'profesor': profesor_profile,
                        'fecha_inicio': datetime.now().date(),
                        'fecha_fin': (datetime.now() + timedelta(weeks=16)).date(),
                        'horario': 'Martes y Jueves 7:00 PM',
                        'aula': 'Aula 2',
                        'capacidad_maxima': 20
                    }
                ]
                
                cursos_creados = []
                for curso_data in cursos_data:
                    curso, created = Curso.objects.get_or_create(
                        sede=sede,
                        ruta_estudio=curso_data['ruta_estudio'],
                        nombre=curso_data['nombre'],
                        defaults=curso_data
                    )
                    if created:
                        cursos_creados.append(curso)
                        self.stdout.write(
                            self.style.SUCCESS(f'✅ Curso "{curso.nombre}" creado')
                        )
                
                # Crear matrícula
                if cursos_creados and len(usuarios_creados) >= 3:
                    estudiante_profile = Estudiante.objects.filter(sede=sede).first()
                    if estudiante_profile:
                        for curso in cursos_creados:
                            matricula, created = Matricula.objects.get_or_create(
                                sede=sede,
                                estudiante=estudiante_profile,
                                curso=curso,
                                defaults={
                                    'estado': 'activa',
                                    'is_active': True
                                }
                            )
                            if created:
                                self.stdout.write(
                                    self.style.SUCCESS(f'✅ Matrícula creada para {estudiante_profile.user.get_full_name()} en {curso.nombre}')
                                )
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Proceso completado para la sede "{sede.nombre}"')
        )
        self.stdout.write(
            self.style.SUCCESS(f'📧 Credenciales de acceso:')
        )
        self.stdout.write(
            self.style.SUCCESS(f'   Admin: admin_{sede.nombre.lower().replace(" ", "_")} / password123')
        )
        self.stdout.write(
            self.style.SUCCESS(f'   Profesor: profesor_{sede.nombre.lower().replace(" ", "_")} / password123')
        )
        self.stdout.write(
            self.style.SUCCESS(f'   Estudiante: estudiante_{sede.nombre.lower().replace(" ", "_")} / password123')
        )
