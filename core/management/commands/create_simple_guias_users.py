from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede, AppModule, UserAppPermission
from guias.models import PersonaNueva, Ministerio
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Crear usuarios simples para Guias'

    def handle(self, *args, **options):
        # Crear o obtener sedes
        sede_central, created = Sede.objects.get_or_create(
            nombre='Sede Central',
            defaults={
                'direccion': 'Av. Principal 123, Ciudad',
                'telefono': '+1 234 567 8900',
                'email': 'central@iglesia.com',
                'pastor_responsable': 'Pastor Principal',
            }
        )
        
        # Crear usuarios de prueba
        usuarios_data = [
            {
                'email': 'admin@guias.com',
                'first_name': 'Ana',
                'last_name': 'García',
                'role': 'app_admin',
                'sede': sede_central,
            },
            {
                'email': 'coordinador@guias.com',
                'first_name': 'Carlos',
                'last_name': 'López',
                'role': 'app_admin',
                'sede': sede_central,
            },
            {
                'email': 'voluntario@guias.com',
                'first_name': 'María',
                'last_name': 'Rodríguez',
                'role': 'user',
                'sede': sede_central,
            }
        ]
        
        usuarios_creados = []
        for i, user_data in enumerate(usuarios_data):
            # Usar username único
            username = f"guias_user_{i+1}"
            
            try:
                user = User.objects.get(email=user_data['email'])
                self.stdout.write(
                    self.style.WARNING(f'Usuario ya existe: {user.email}')
                )
            except User.DoesNotExist:
                user = User.objects.create(
                    email=user_data['email'],
                    username=username,
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    role=user_data['role'],
                    sede=user_data['sede'],
                    is_verified=True,
                    is_active=True,
                )
                user.set_password('password123')
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Usuario creado: {user.email}')
                )
            
            usuarios_creados.append(user)
        
        # Asignar permisos de Guias
        try:
            guias_module = AppModule.objects.get(name='guias')
            
            for user in usuarios_creados:
                permission, created = UserAppPermission.objects.get_or_create(
                    user=user,
                    app_module=guias_module,
                    defaults={
                        'can_view': True,
                        'can_edit': True,
                        'can_delete': user.role == 'app_admin',
                        'can_manage': user.role == 'app_admin',
                    }
                )
                
                if not created:
                    permission.can_view = True
                    permission.can_edit = True
                    permission.can_delete = user.role == 'app_admin'
                    permission.can_manage = user.role == 'app_admin'
                    permission.save()
                
                status = 'creado' if created else 'actualizado'
                self.stdout.write(
                    self.style.SUCCESS(f'Permisos de Guias {status} para {user.email}')
                )
                
        except AppModule.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Módulo Guias no encontrado. Ejecute setup_app_modules primero.')
            )
            return
        
        # Crear algunas personas de prueba
        nombres = ['Ana', 'Carlos', 'María', 'José', 'Laura', 'Pedro', 'Sofía', 'Miguel']
        apellidos = ['García', 'López', 'Rodríguez', 'Martínez', 'González', 'Pérez', 'Sánchez', 'Ramírez']
        
        for i in range(10):  # Crear 10 personas de prueba
            nombre = random.choice(nombres)
            apellido = random.choice(apellidos)
            estado = random.choice(['nuevo', 'visitante', 'interesado'])
            responsable = random.choice(usuarios_creados)
            
            persona = PersonaNueva.objects.create(
                nombre=nombre,
                apellido=apellido,
                email=f'{nombre.lower()}.{apellido.lower()}@email.com',
                telefono=f'+1 555 {random.randint(100, 999)} {random.randint(1000, 9999)}',
                fecha_nacimiento=datetime.now().date() - timedelta(days=random.randint(18*365, 65*365)),
                genero=random.choice(['M', 'F']),
                direccion=f'Calle {random.randint(1, 999)} #{random.randint(1, 99)}',
                ciudad='Ciudad',
                sede=sede_central,
                estado=estado,
                fecha_primera_visita=datetime.now().date() - timedelta(days=random.randint(1, 30)),
                como_conocio=random.choice(['Redes sociales', 'Amigo', 'Publicidad', 'Evento']),
                intereses=random.choice(['Alabanza', 'Niños', 'Evangelismo', 'Estudio bíblico']),
                responsable_seguimiento=responsable,
                notas=f'Persona de prueba #{i+1}'
            )
        
        self.stdout.write(
            self.style.SUCCESS('\n=== USUARIOS DE PRUEBA CREADOS ===')
        )
        self.stdout.write(
            self.style.SUCCESS('Email: admin@guias.com | Password: password123 | Rol: Admin')
        )
        self.stdout.write(
            self.style.SUCCESS('Email: coordinador@guias.com | Password: password123 | Rol: Admin')
        )
        self.stdout.write(
            self.style.SUCCESS('Email: voluntario@guias.com | Password: password123 | Rol: Usuario')
        )
        self.stdout.write(
            self.style.SUCCESS(f'\nCreadas {PersonaNueva.objects.count()} personas de prueba')
        )
