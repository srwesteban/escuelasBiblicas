from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Sede, AppModule, UserAppPermission
from guias.models import PersonaNueva, Ministerio, EventoEspecial
from datetime import datetime, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Crear usuarios de prueba para la app Guias'

    def handle(self, *args, **options):
        # Crear sedes si no existen
        sede_central, created = Sede.objects.get_or_create(
            nombre='Sede Central',
            defaults={
                'direccion': 'Av. Principal 123, Ciudad',
                'telefono': '+1 234 567 8900',
                'email': 'central@iglesia.com',
                'pastor_responsable': 'Pastor Principal',
                'descripcion': 'Sede principal de la iglesia'
            }
        )
        
        sede_norte, created = Sede.objects.get_or_create(
            nombre='Sede Norte',
            defaults={
                'direccion': 'Calle Norte 456, Ciudad',
                'telefono': '+1 234 567 8901',
                'email': 'norte@iglesia.com',
                'pastor_responsable': 'Pastor Norte',
                'descripcion': 'Sede norte de la iglesia'
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
                'is_verified': True,
            },
            {
                'email': 'coordinador@guias.com',
                'first_name': 'Carlos',
                'last_name': 'López',
                'role': 'app_admin',
                'sede': sede_norte,
                'is_verified': True,
            },
            {
                'email': 'voluntario@guias.com',
                'first_name': 'María',
                'last_name': 'Rodríguez',
                'role': 'user',
                'sede': sede_central,
                'is_verified': True,
            },
            {
                'email': 'seguimiento@guias.com',
                'first_name': 'José',
                'last_name': 'Martínez',
                'role': 'user',
                'sede': sede_norte,
                'is_verified': True,
            }
        ]
        
        usuarios_creados = []
        for user_data in usuarios_data:
            try:
                user = User.objects.get(email=user_data['email'])
                self.stdout.write(
                    self.style.WARNING(f'Usuario ya existe: {user.email}')
                )
            except User.DoesNotExist:
                user = User.objects.create(
                    email=user_data['email'],
                    username=user_data['email'].split('@')[0],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    role=user_data['role'],
                    sede=user_data['sede'],
                    is_verified=user_data['is_verified'],
                    is_active=True,
                )
                user.set_password('password123')
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Usuario creado: {user.email}')
                )
            
            
            usuarios_creados.append(user)
        
        # Asignar permisos de Guias a los usuarios
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
        
        # Crear ministerios de prueba
        ministerios_data = [
            {
                'nombre': 'Ministerio de Alabanza',
                'descripcion': 'Grupo de alabanza y adoración',
                'sede': sede_central,
                'responsable': usuarios_creados[0],
            },
            {
                'nombre': 'Ministerio de Niños',
                'descripcion': 'Cuidado y enseñanza de niños',
                'sede': sede_central,
                'responsable': usuarios_creados[1],
            },
            {
                'nombre': 'Ministerio de Jóvenes',
                'descripcion': 'Actividades y enseñanza para jóvenes',
                'sede': sede_norte,
                'responsable': usuarios_creados[2],
            },
            {
                'nombre': 'Ministerio de Evangelismo',
                'descripcion': 'Evangelización y alcance comunitario',
                'sede': sede_norte,
                'responsable': usuarios_creados[3],
            }
        ]
        
        for ministerio_data in ministerios_data:
            ministerio, created = Ministerio.objects.get_or_create(
                nombre=ministerio_data['nombre'],
                defaults=ministerio_data
            )
            
            status = 'creado' if created else 'ya existe'
            self.stdout.write(
                self.style.SUCCESS(f'Ministerio {ministerio.nombre} {status}')
            )
        
        # Crear personas nuevas de prueba
        nombres = ['Ana', 'Carlos', 'María', 'José', 'Laura', 'Pedro', 'Sofía', 'Miguel', 'Elena', 'David']
        apellidos = ['García', 'López', 'Rodríguez', 'Martínez', 'González', 'Pérez', 'Sánchez', 'Ramírez', 'Torres', 'Flores']
        estados = ['nuevo', 'visitante', 'interesado', 'miembro']
        
        personas_creadas = []
        for i in range(20):  # Crear 20 personas de prueba
            nombre = random.choice(nombres)
            apellido = random.choice(apellidos)
            estado = random.choice(estados)
            sede = random.choice([sede_central, sede_norte])
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
                codigo_postal=f'{random.randint(10000, 99999)}',
                sede=sede,
                estado=estado,
                fecha_primera_visita=datetime.now().date() - timedelta(days=random.randint(1, 90)),
                como_conocio=random.choice([
                    'Redes sociales', 'Amigo', 'Publicidad', 'Evento', 'Familia', 'Trabajo'
                ]),
                intereses=random.choice([
                    'Alabanza y adoración', 'Ministerio de niños', 'Evangelismo', 'Estudio bíblico',
                    'Servicio comunitario', 'Jóvenes', 'Familias', 'Misiones'
                ]),
                referido_por=random.choice(['Juan Pérez', 'María García', 'Carlos López', 'Ana Martínez', '']),
                responsable_seguimiento=responsable,
                notas=f'Persona de prueba #{i+1}'
            )
            
            personas_creadas.append(persona)
        
        self.stdout.write(
            self.style.SUCCESS(f'Creadas {len(personas_creadas)} personas de prueba')
        )
        
        # Crear eventos de prueba
        eventos_data = [
            {
                'nombre': 'Clase de Nuevos Miembros',
                'tipo': 'clase_nuevos',
                'descripcion': 'Clase para nuevos miembros de la iglesia',
                'fecha_evento': datetime.now() + timedelta(days=7),
                'lugar': 'Salón Principal',
                'sede': sede_central,
                'responsable': usuarios_creados[0],
            },
            {
                'nombre': 'Bautismo de Primavera',
                'tipo': 'bautismo',
                'descripcion': 'Ceremonia de bautismo para nuevos creyentes',
                'fecha_evento': datetime.now() + timedelta(days=14),
                'lugar': 'Piscina Bautismal',
                'sede': sede_central,
                'responsable': usuarios_creados[1],
            },
            {
                'nombre': 'Retiro de Jóvenes',
                'tipo': 'retiro',
                'descripcion': 'Retiro espiritual para jóvenes',
                'fecha_evento': datetime.now() + timedelta(days=21),
                'lugar': 'Centro de Retiros',
                'sede': sede_norte,
                'responsable': usuarios_creados[2],
            }
        ]
        
        for evento_data in eventos_data:
            evento = EventoEspecial.objects.create(**evento_data)
            
            # Invitar algunas personas al evento
            personas_invitadas = random.sample(personas_creadas, random.randint(3, 8))
            evento.personas_invitadas.set(personas_invitadas)
            
            self.stdout.write(
                self.style.SUCCESS(f'Evento creado: {evento.nombre}')
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
            self.style.SUCCESS('Email: seguimiento@guias.com | Password: password123 | Rol: Usuario')
        )
        self.stdout.write(
            self.style.SUCCESS('\n=== DATOS DE PRUEBA CREADOS ===')
        )
        self.stdout.write(
            self.style.SUCCESS(f'• {len(personas_creadas)} personas nuevas')
        )
        self.stdout.write(
            self.style.SUCCESS(f'• {len(ministerios_data)} ministerios')
        )
        self.stdout.write(
            self.style.SUCCESS(f'• {len(eventos_data)} eventos especiales')
        )
        self.stdout.write(
            self.style.SUCCESS(f'• {len(usuarios_creados)} usuarios con permisos')
        )
