from django.core.management.base import BaseCommand
from django.db import transaction
from hechos.models import Curso, EdicionCurso, Profesor
from core.models import Sede
from datetime import date, timedelta


class Command(BaseCommand):
    help = 'Crear ediciones automáticamente para cursos que no tienen ediciones asignadas a profesores'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sede-id',
            type=int,
            help='ID de la sede específica (opcional)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar qué se haría sin ejecutar cambios',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sede_id = options.get('sede_id')
        
        if sede_id:
            sedes = Sede.objects.filter(id=sede_id)
        else:
            sedes = Sede.objects.all()
        
        if not sedes.exists():
            self.stdout.write(self.style.ERROR('No se encontraron sedes.'))
            return
        
        for sede in sedes:
            self.stdout.write(f'\n=== Procesando sede: {sede.nombre} ===')
            
            # Obtener cursos sin ediciones
            cursos_sin_ediciones = Curso.objects.filter(
                sede=sede,
                is_active=True
            ).exclude(
                ediciones__isnull=False
            )
            
            self.stdout.write(f'Cursos sin ediciones: {cursos_sin_ediciones.count()}')
            
            # Obtener profesores disponibles
            profesores = Profesor.objects.filter(sede=sede, is_active=True)
            self.stdout.write(f'Profesores disponibles: {profesores.count()}')
            
            if not profesores.exists():
                self.stdout.write(self.style.WARNING('  ⚠️  No hay profesores en esta sede'))
                continue
            
            if not cursos_sin_ediciones.exists():
                self.stdout.write('  ✓ Todos los cursos ya tienen ediciones')
                continue
            
            # Crear ediciones para cursos sin ediciones
            with transaction.atomic():
                for i, curso in enumerate(cursos_sin_ediciones):
                    # Asignar profesor rotativamente
                    profesor = profesores[i % len(profesores)]
                    
                    # Crear edición por defecto
                    nombre_edicion = f'Grupo Principal - {curso.nombre}'
                    
                    if dry_run:
                        self.stdout.write(f'  [DRY RUN] Crearía edición: {nombre_edicion} para {profesor.user.get_full_name()}')
                    else:
                        edicion = EdicionCurso.objects.create(
                            curso=curso,
                            nombre_edicion=nombre_edicion,
                            profesor=profesor,
                            fecha_inicio=date.today(),
                            fecha_fin=date.today() + timedelta(weeks=curso.duracion_semanas),
                            horario='Por definir',
                            aula='Por asignar',
                            cupo_maximo=30
                        )
                        self.stdout.write(f'  ✓ Creada edición: {nombre_edicion} para {profesor.user.get_full_name()}')
            
            # Mostrar resumen de ediciones por profesor
            self.stdout.write(f'\n--- Resumen de ediciones por profesor ---')
            for profesor in profesores:
                ediciones_count = EdicionCurso.objects.filter(
                    profesor=profesor,
                    curso__sede=sede,
                    is_active=True
                ).count()
                self.stdout.write(f'  {profesor.user.get_full_name()}: {ediciones_count} ediciones')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Proceso completado'))
