from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from core.models import Sede
from hechos.models import Estudiante, Profesor, AdminEscuela, RutaEstudio, Curso, Matricula, Clase, Asistencia, Nota

User = get_user_model()


class Command(BaseCommand):
    help = 'Limpia todos los datos y deja solo Sede Central con usuarios de prueba'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Eliminar datos sin confirmación'
        )

    def handle(self, *args, **options):
        force = options['force']
        
        if not force:
            confirm = input('⚠️  ¿Estás seguro de que quieres eliminar TODOS los datos? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(
                    self.style.WARNING('❌ Operación cancelada')
                )
                return
        
        with transaction.atomic():
            # Eliminar todos los datos de hechos
            self.stdout.write('🗑️  Eliminando datos de hechos...')
            
            # Eliminar en orden para evitar problemas de foreign key
            Asistencia.objects.all().delete()
            Nota.objects.all().delete()
            Clase.objects.all().delete()
            Matricula.objects.all().delete()
            Curso.objects.all().delete()
            RutaEstudio.objects.all().delete()
            AdminEscuela.objects.all().delete()
            Profesor.objects.all().delete()
            Estudiante.objects.all().delete()
            
            self.stdout.write('  ✅ Datos de hechos eliminados')
            
            # Eliminar todas las sedes
            self.stdout.write('🗑️  Eliminando sedes...')
            Sede.objects.all().delete()
            self.stdout.write('  ✅ Sedes eliminadas')
            
            # Eliminar todos los usuarios excepto super admin
            self.stdout.write('🗑️  Eliminando usuarios...')
            User.objects.exclude(username='admin').exclude(email='admin@hechoshub.com').delete()
            self.stdout.write('  ✅ Usuarios eliminados')
        
        self.stdout.write(
            self.style.SUCCESS('\n✅ Limpieza completa realizada')
        )
        
        # Mostrar usuarios restantes
        remaining_users = User.objects.all()
        self.stdout.write(
            self.style.SUCCESS(f'\n📊 Usuarios restantes: {remaining_users.count()}')
        )
        
        for user in remaining_users:
            self.stdout.write(f'  - {user.username} ({user.email})')
