from django.core.management.base import BaseCommand
from core.models import User
from hechos.models import AdminEscuela


class Command(BaseCommand):
    help = 'Crea un usuario admin de escuelas para pruebas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='directora@hechoshub.com',
            help='Email del admin de escuelas'
        )
        parser.add_argument(
            '--password',
            type=str,
            default='admin123',
            help='Contraseña del admin de escuelas'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        
        # Crear usuario admin de escuelas
        admin_escuela_user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email.split('@')[0],
                'first_name': 'María',
                'last_name': 'González',
                'role': 'app_admin',
                'is_verified': True
            }
        )
        
        if created:
            admin_escuela_user.set_password(password)
            admin_escuela_user.save()
            
            # Crear perfil de admin de escuelas
            AdminEscuela.objects.create(
                user=admin_escuela_user,
                escuela='Escuela Bíblica Central',
                cargo='Directora'
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Usuario admin de escuelas creado:')
            )
            self.stdout.write(f'Email: {email}')
            self.stdout.write(f'Contraseña: {password}')
            self.stdout.write(f'Escuela: Escuela Bíblica Central')
            self.stdout.write(f'Cargo: Directora')
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠️ El usuario {email} ya existe')
            )
