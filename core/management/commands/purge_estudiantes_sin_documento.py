"""
Elimina estudiantes cuyo número de documento está vacío (datos previos al flujo por documento).
Borra el User asociado para evitar cuentas huérfanas; CASCADE limpia Matricula, asistencias, etc.
No toca usuarios con perfil de profesor o admin de escuela, ni superusuarios.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from hechos.models import Estudiante

User = get_user_model()


def _sin_documento_valido(est: Estudiante) -> bool:
    return not (est.numero_documento or "").strip()


class Command(BaseCommand):
    help = "Elimina estudiantes sin número de documento (solo perfil estudiante; no staff ni otros perfiles)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo listar cuentas afectadas, sin borrar.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ejecutar borrado sin pedir confirmación.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        candidatos = []
        for est in Estudiante.objects.select_related("user").iterator():
            if not _sin_documento_valido(est):
                continue
            u = est.user
            if u.is_superuser:
                self.stdout.write(self.style.WARNING(f"Omitido (superuser): {u.username}"))
                continue
            if hasattr(u, "profesor_profile"):
                self.stdout.write(self.style.WARNING(f"Omitido (también profesor): {u.username}"))
                continue
            if hasattr(u, "admin_escuela_profile"):
                self.stdout.write(self.style.WARNING(f"Omitido (también admin escuela): {u.username}"))
                continue
            candidatos.append(est)

        if not candidatos:
            self.stdout.write(self.style.SUCCESS("No hay estudiantes sin documento para eliminar."))
            return

        self.stdout.write(
            self.style.WARNING(f"Encontrados {len(candidatos)} estudiante(s) sin documento:")
        )
        for est in candidatos:
            u = est.user
            self.stdout.write(f"  - id={est.id} user={u.username!r} {u.get_full_name()!r}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run: no se eliminó nada."))
            return

        if not force:
            confirm = input("¿Eliminar estos usuarios y sus datos de estudiante? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("Cancelado."))
                return

        deleted = 0
        with transaction.atomic():
            for est in candidatos:
                uid = est.user_id
                username = est.user.username
                # Borrar User: CASCADE elimina Estudiante y lo que cuelga del estudiante.
                User.objects.filter(pk=uid).delete()
                deleted += 1
                self.stdout.write(self.style.SUCCESS(f"Eliminado: {username!r} (user id={uid})"))

        self.stdout.write(self.style.SUCCESS(f"Listo. Usuarios eliminados: {deleted}"))
