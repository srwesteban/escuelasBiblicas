from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from core.models import AppModule, UserAppPermission
from hechos.models import RutaEstudio, Estudiante, Profesor, AdminEscuela

User = get_user_model()


class Command(BaseCommand):
    help = 'Inicializa datos básicos del sistema HechosHub'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando configuración de datos básicos...'))
        
        # Configurar Site para django-allauth
        self.setup_site()
        
        # Crear módulo Hechos
        self.create_hechos_module()
        
        # Crear rutas de estudio básicas
        self.create_rutas_estudio()
        
        # Crear superusuario si no existe
        self.create_superuser()
        
        self.stdout.write(self.style.SUCCESS('¡Configuración completada exitosamente!'))
        self.stdout.write(self.style.WARNING('Puedes acceder al admin en: http://localhost:8000/admin/'))
        self.stdout.write(self.style.WARNING('Usuario: admin, Contraseña: admin123'))

    def setup_site(self):
        """Configurar el Site para django-allauth"""
        try:
            site = Site.objects.get(id=1)
            site.domain = 'localhost:8000'
            site.name = 'HechosHub'
            site.save()
            self.stdout.write('✓ Site configurado correctamente')
        except Site.DoesNotExist:
            Site.objects.create(
                id=1,
                domain='localhost:8000',
                name='HechosHub'
            )
            self.stdout.write('✓ Site creado correctamente')

    def create_hechos_module(self):
        """Crear el módulo Hechos en el sistema"""
        module, created = AppModule.objects.get_or_create(
            name='hechos',
            defaults={
                'display_name': 'Hechos (Escuelas Bíblicas)',
                'description': 'Módulo para gestión de escuelas bíblicas, estudiantes, profesores y cursos',
                'url_name': 'hechos:dashboard',
                'icon': 'fas fa-bible',
                'is_active': True,
                'order': 1
            }
        )
        
        if created:
            self.stdout.write('✓ Módulo Hechos creado')
        else:
            self.stdout.write('✓ Módulo Hechos ya existe')
        
        # Crear permisos para el superusuario
        try:
            superuser = User.objects.get(email='admin@hechoshub.com')
            UserAppPermission.objects.get_or_create(
                user=superuser,
                app_module=module,
                defaults={
                    'can_view': True,
                    'can_edit': True,
                    'can_delete': True,
                    'can_manage': True
                }
            )
            self.stdout.write('✓ Permisos del módulo Hechos configurados para superusuario')
        except User.DoesNotExist:
            pass

    def create_rutas_estudio(self):
        """Crear rutas de estudio básicas"""
        rutas_data = [
            {
                'nombre': 'Fundamentos de la Fe',
                'descripcion': 'Curso básico para nuevos creyentes',
                'duracion_semanas': 12,
                'nivel': 'basico'
            },
            {
                'nombre': 'Doctrina Bíblica',
                'descripcion': 'Estudio profundo de las doctrinas fundamentales',
                'duracion_semanas': 16,
                'nivel': 'intermedio'
            },
            {
                'nombre': 'Liderazgo Cristiano',
                'descripcion': 'Formación para líderes y pastores',
                'duracion_semanas': 20,
                'nivel': 'avanzado'
            },
            {
                'nombre': 'Historia de la Iglesia',
                'descripcion': 'Estudio de la historia del cristianismo',
                'duracion_semanas': 14,
                'nivel': 'intermedio'
            }
        ]
        
        created_count = 0
        for ruta_data in rutas_data:
            ruta, created = RutaEstudio.objects.get_or_create(
                nombre=ruta_data['nombre'],
                defaults=ruta_data
            )
            if created:
                created_count += 1
        
        if created_count > 0:
            self.stdout.write(f'✓ {created_count} rutas de estudio creadas')
        else:
            self.stdout.write('✓ Rutas de estudio ya existen')

    def create_superuser(self):
        """Crear superusuario si no existe"""
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                email='admin@hechoshub.com',
                username='admin',
                first_name='Administrador',
                last_name='Sistema',
                password='admin123',
                role='super_admin'
            )
            self.stdout.write('✓ Superusuario creado (admin@hechoshub.com / admin123)')
        else:
            self.stdout.write('✓ Superusuario ya existe')
