from django.core.management.base import BaseCommand
from core.models import AppModule


class Command(BaseCommand):
    help = 'Configurar módulos de aplicación disponibles'

    def handle(self, *args, **options):
        # Crear o actualizar módulos de aplicación
        modules_data = [
            {
                'name': 'hechos',
                'display_name': 'Escuelas Bíblicas',
                'description': 'Gestión de estudiantes, profesores, cursos y calificaciones',
                'url_name': 'hechos:dashboard',
                'icon': 'fas fa-graduation-cap',
                'order': 1,
            },
        ]
        
        for module_data in modules_data:
            module, created = AppModule.objects.get_or_create(
                name=module_data['name'],
                defaults=module_data
            )
            
            if not created:
                # Actualizar datos existentes
                for key, value in module_data.items():
                    setattr(module, key, value)
                module.save()
            
            status = 'creado' if created else 'actualizado'
            self.stdout.write(
                self.style.SUCCESS(f'Módulo {module.display_name} {status}')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Módulos de aplicación configurados exitosamente')
        )
