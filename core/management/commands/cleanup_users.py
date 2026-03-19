from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from hechos.models import Estudiante, Profesor, AdminEscuela

User = get_user_model()


class Command(BaseCommand):
    help = 'Limpia usuarios que no tienen sede asignada (usuarios de prueba legacy)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué usuarios serían eliminados sin eliminarlos realmente'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Eliminar usuarios sin confirmación'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        # Obtener usuarios sin sede asignada
        users_without_sede = User.objects.filter(sede__isnull=True)
        
        # Filtrar usuarios que no son super admin
        users_to_delete = users_without_sede.exclude(
            username__in=['admin', 'admin@hechoshub.com']
        ).exclude(
            email__in=['admin@hechoshub.com']
        )
        
        if not users_to_delete.exists():
            self.stdout.write(
                self.style.SUCCESS('✅ No hay usuarios para eliminar')
            )
            return
        
        self.stdout.write(
            self.style.WARNING(f'🔍 Encontrados {users_to_delete.count()} usuarios sin sede:')
        )
        
        for user in users_to_delete:
            self.stdout.write(f'  - {user.username} ({user.email}) - {user.get_full_name()}')
        
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS('\n🔍 Modo dry-run: No se eliminaron usuarios')
            )
            return
        
        if not force:
            confirm = input('\n¿Estás seguro de que quieres eliminar estos usuarios? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(
                    self.style.WARNING('❌ Operación cancelada')
                )
                return
        
        # Eliminar usuarios y sus perfiles relacionados
        deleted_count = 0
        
        with transaction.atomic():
            for user in users_to_delete:
                # Eliminar perfiles relacionados primero
                if hasattr(user, 'estudiante_profile'):
                    user.estudiante_profile.delete()
                    self.stdout.write(f'  🗑️  Eliminado perfil de estudiante: {user.username}')
                
                if hasattr(user, 'profesor_profile'):
                    user.profesor_profile.delete()
                    self.stdout.write(f'  🗑️  Eliminado perfil de profesor: {user.username}')
                
                if hasattr(user, 'admin_escuela_profile'):
                    user.admin_escuela_profile.delete()
                    self.stdout.write(f'  🗑️  Eliminado perfil de admin: {user.username}')
                
                # Eliminar el usuario
                username = user.username
                user.delete()
                deleted_count += 1
                self.stdout.write(f'  🗑️  Eliminado usuario: {username}')
        
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Se eliminaron {deleted_count} usuarios sin sede')
        )
        
        # Mostrar usuarios restantes
        remaining_users = User.objects.all()
        self.stdout.write(
            self.style.SUCCESS(f'\n📊 Usuarios restantes: {remaining_users.count()}')
        )
        
        for user in remaining_users:
            sede_info = f" - Sede: {user.sede.nombre}" if user.sede else " - Sin sede"
            self.stdout.write(f'  - {user.username} ({user.email}){sede_info}')
