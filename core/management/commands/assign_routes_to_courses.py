from django.core.management.base import BaseCommand
from hechos.models import Curso, RutaEstudio
from core.models import Sede


class Command(BaseCommand):
    help = 'Asigna rutas de estudio a cursos existentes que no tienen ruta asignada'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede',
            type=str,
            help='ID o nombre de la sede específica (opcional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué cursos serían actualizados sin hacer cambios',
        )

    def handle(self, *args, **options):
        sede_filter = options.get('sede')
        dry_run = options.get('dry_run', False)
        
        # Filtrar por sede si se especifica
        if sede_filter:
            try:
                if sede_filter.isdigit():
                    sede = Sede.objects.get(id=sede_filter)
                else:
                    sede = Sede.objects.get(nombre__icontains=sede_filter)
                sedes = [sede]
                self.stdout.write(f"Procesando solo la sede: {sede.nombre}")
            except Sede.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Sede '{sede_filter}' no encontrada"))
                return
        else:
            sedes = Sede.objects.filter(is_active=True)
            self.stdout.write("Procesando todas las sedes activas")
        
        total_courses_updated = 0
        
        for sede in sedes:
            self.stdout.write(f"\n--- Procesando sede: {sede.nombre} ---")
            
            # Obtener cursos sin ruta asignada
            cursos_sin_ruta = Curso.objects.filter(
                sede=sede,
                ruta_estudio__isnull=True,
                is_active=True
            )
            
            if not cursos_sin_ruta.exists():
                self.stdout.write(f"  No hay cursos sin ruta en {sede.nombre}")
                continue
            
            # Obtener rutas disponibles
            rutas_disponibles = RutaEstudio.objects.filter(
                sede=sede,
                is_active=True
            ).order_by('nivel', 'nombre')
            
            if not rutas_disponibles.exists():
                self.stdout.write(f"  No hay rutas disponibles en {sede.nombre}")
                continue
            
            self.stdout.write(f"  Cursos sin ruta: {cursos_sin_ruta.count()}")
            self.stdout.write(f"  Rutas disponibles: {rutas_disponibles.count()}")
            
            # Asignar rutas a cursos
            for i, curso in enumerate(cursos_sin_ruta):
                # Seleccionar ruta basada en el índice (distribución circular)
                ruta_seleccionada = rutas_disponibles[i % len(rutas_disponibles)]
                
                if dry_run:
                    self.stdout.write(
                        f"  [DRY RUN] Curso '{curso.nombre}' sería asignado a ruta '{ruta_seleccionada.nombre}'"
                    )
                else:
                    curso.ruta_estudio = ruta_seleccionada
                    curso.orden = 1  # Orden por defecto
                    curso.save()
                    self.stdout.write(
                        f"  ✓ Curso '{curso.nombre}' asignado a ruta '{ruta_seleccionada.nombre}'"
                    )
                
                total_courses_updated += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"\n[DRY RUN] Se actualizarían {total_courses_updated} cursos")
            )
            self.stdout.write("Ejecuta sin --dry-run para aplicar los cambios")
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n✓ Se actualizaron {total_courses_updated} cursos")
            )
