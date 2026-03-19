from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede
from hechos.models import Estudiante, Profesor, AdminEscuela

User = get_user_model()


class Command(BaseCommand):
    help = 'Asigna sedes a usuarios existentes que no tienen sede asignada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='ID de la sede a asignar (si no se especifica, se usa la primera sede disponible)'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID del usuario específico a asignar (si no se especifica, se asignan todos)'
        )

    def handle(self, *args, **options):
        # Obtener la sede
        if options['sede_id']:
            try:
                sede = Sede.objects.get(id=options['sede_id'])
            except Sede.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ No se encontró la sede con ID {options["sede_id"]}')
                )
                return
        else:
            sede = Sede.objects.filter(is_active=True).first()
            if not sede:
                self.stdout.write(
                    self.style.ERROR('❌ No hay sedes disponibles. Crea una sede primero.')
                )
                return
        
        self.stdout.write(
            self.style.SUCCESS(f'📍 Usando sede: {sede.nombre}')
        )
        
        # Obtener usuarios a asignar
        if options['user_id']:
            try:
                users = [User.objects.get(id=options['user_id'])]
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'❌ No se encontró el usuario con ID {options["user_id"]}')
                )
                return
        else:
            # Obtener usuarios sin sede asignada
            users = User.objects.filter(sede__isnull=True)
        
        if not users:
            self.stdout.write(
                self.style.WARNING('⚠️  No hay usuarios para asignar')
            )
            return
        
        assigned_count = 0
        
        for user in users:
            # Asignar sede al usuario
            user.sede = sede
            user.save()
            
            # Asignar sede a los perfiles existentes
            if hasattr(user, 'estudiante_profile'):
                user.estudiante_profile.sede = sede
                user.estudiante_profile.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Sede asignada a estudiante: {user.get_full_name()}')
                )
                assigned_count += 1
            
            if hasattr(user, 'profesor_profile'):
                user.profesor_profile.sede = sede
                user.profesor_profile.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Sede asignada a profesor: {user.get_full_name()}')
                )
                assigned_count += 1
            
            if hasattr(user, 'admin_escuela_profile'):
                user.admin_escuela_profile.sede = sede
                user.admin_escuela_profile.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Sede asignada a admin: {user.get_full_name()}')
                )
                assigned_count += 1
            
            if not (hasattr(user, 'estudiante_profile') or 
                   hasattr(user, 'profesor_profile') or 
                   hasattr(user, 'admin_escuela_profile')):
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Sede asignada a usuario: {user.get_full_name()}')
                )
                assigned_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'\n🎉 Se asignaron {assigned_count} usuarios a la sede "{sede.nombre}"')
        )
