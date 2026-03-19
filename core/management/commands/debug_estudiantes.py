from django.core.management.base import BaseCommand
from hechos.models import Estudiante, AdminEscuela
from core.models import Sede, User


class Command(BaseCommand):
    help = 'Diagnostica problemas con el módulo de estudiantes'

    def handle(self, *args, **options):
        self.stdout.write("=== DIAGNÓSTICO DEL MÓDULO DE ESTUDIANTES ===\n")
        
        # Verificar sedes
        sedes = Sede.objects.all()
        self.stdout.write(f"📊 Sedes encontradas: {sedes.count()}")
        for sede in sedes:
            self.stdout.write(f"  - {sede.nombre} (ID: {sede.id})")
        
        # Verificar usuarios admin
        admins = AdminEscuela.objects.all()
        self.stdout.write(f"\n👨‍💼 Admins de escuela: {admins.count()}")
        for admin in admins:
            self.stdout.write(f"  - {admin.user.get_full_name()} (Sede: {admin.sede.nombre if admin.sede else 'Sin sede'})")
        
        # Verificar estudiantes
        estudiantes = Estudiante.objects.all()
        self.stdout.write(f"\n👨‍🎓 Estudiantes: {estudiantes.count()}")
        for estudiante in estudiantes:
            self.stdout.write(f"  - {estudiante.user.get_full_name()} (Sede: {estudiante.sede.nombre if estudiante.sede else 'Sin sede'})")
        
        # Verificar estudiantes por sede
        for sede in sedes:
            estudiantes_sede = Estudiante.objects.filter(sede=sede, is_active=True)
            self.stdout.write(f"\n📚 Estudiantes en {sede.nombre}: {estudiantes_sede.count()}")
            for estudiante in estudiantes_sede:
                self.stdout.write(f"  - {estudiante.user.get_full_name()} ({estudiante.codigo_estudiante})")
        
        # Verificar usuarios sin sede
        usuarios_sin_sede = User.objects.filter(sede__isnull=True)
        self.stdout.write(f"\n⚠️ Usuarios sin sede: {usuarios_sin_sede.count()}")
        for usuario in usuarios_sin_sede[:5]:  # Solo mostrar los primeros 5
            self.stdout.write(f"  - {usuario.get_full_name()} ({usuario.email})")
        
        self.stdout.write("\n=== FIN DEL DIAGNÓSTICO ===")
