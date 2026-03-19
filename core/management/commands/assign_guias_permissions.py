from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import AppModule, UserAppPermission

User = get_user_model()


class Command(BaseCommand):
    help = 'Asignar permisos de Guias a usuarios específicos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-email',
            type=str,
            help='Email del usuario al que asignar permisos',
        )
        parser.add_argument(
            '--all-admins',
            action='store_true',
            help='Asignar permisos a todos los admins de aplicación',
        )

    def handle(self, *args, **options):
        # Obtener el módulo de Guias
        try:
            guias_module = AppModule.objects.get(name='guias')
        except AppModule.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Módulo Guias no encontrado. Ejecute setup_app_modules primero.')
            )
            return

        if options['all_admins']:
            # Asignar permisos a todos los admins de aplicación
            admin_users = User.objects.filter(role='app_admin', is_active=True)
            
            for user in admin_users:
                permission, created = UserAppPermission.objects.get_or_create(
                    user=user,
                    app_module=guias_module,
                    defaults={
                        'can_view': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_manage': True,
                    }
                )
                
                if not created:
                    # Actualizar permisos existentes
                    permission.can_view = True
                    permission.can_edit = True
                    permission.can_delete = True
                    permission.can_manage = True
                    permission.save()
                
                status = 'creado' if created else 'actualizado'
                self.stdout.write(
                    self.style.SUCCESS(f'Permisos de Guias {status} para {user.email}')
                )
        
        elif options['user_email']:
            # Asignar permisos a un usuario específico
            try:
                user = User.objects.get(email=options['user_email'])
                
                permission, created = UserAppPermission.objects.get_or_create(
                    user=user,
                    app_module=guias_module,
                    defaults={
                        'can_view': True,
                        'can_edit': True,
                        'can_delete': True,
                        'can_manage': True,
                    }
                )
                
                if not created:
                    # Actualizar permisos existentes
                    permission.can_view = True
                    permission.can_edit = True
                    permission.can_delete = True
                    permission.can_manage = True
                    permission.save()
                
                status = 'creado' if created else 'actualizado'
                self.stdout.write(
                    self.style.SUCCESS(f'Permisos de Guias {status} para {user.email}')
                )
                
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Usuario con email {options["user_email"]} no encontrado')
                )
        
        else:
            self.stdout.write(
                self.style.ERROR('Debe especificar --user-email o --all-admins')
            )
