from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Sede
from hechos.models import (
    AdminEscuela,
    AdminEscuelaCapacidad,
    CapacidadCoordinador,
    EscuelaPrograma,
    Estudiante,
    Profesor,
)

User = get_user_model()

PASSWORD = "Prueba2026!"


class Command(BaseCommand):
    help = (
        "Borra TODOS los usuarios y sedes (y todo lo que dependa de ellos en cascada: "
        "escuelas, matriculas, notas, asistencia, actividades, ofrendas...) y crea un "
        "set minimo de cuentas de prueba: 1 director, 1 coordinador de cada tipo, "
        "1 coordinador multi-rol (1000000040), 1 profesor y 1 estudiante, todos en una sede nueva. "
        "El catalogo global (Formacion global / NivelProgramaPlantilla y "
        "EscuelaProgramaPlantilla) NO se toca: no depende de sedes ni usuarios."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirma el borrado sin preguntar de forma interactiva.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            total_sedes = Sede.objects.count()
            total_users = User.objects.count()
            confirm = input(
                f"Esto borra {total_sedes} sede(s) y {total_users} usuario(s) (y todo lo "
                f"que dependa de ellos). Escribe 'si' para continuar: "
            )
            if confirm.strip().lower() != "si":
                self.stdout.write(self.style.WARNING("Cancelado."))
                return

        self.stdout.write("Borrando sedes y usuarios existentes...")
        # EscuelaPrograma.nivel_programa es PROTECT: hay que vaciarlo antes de borrar
        # Sede (que en cascada intentaria borrar NivelPrograma).
        EscuelaPrograma.objects.all().delete()
        Sede.objects.all().delete()
        User.objects.all().delete()

        sede = Sede.objects.create(
            nombre="Sede Principal",
            direccion="Por definir",
            descripcion="Sede de prueba generada por reset_datos_prueba.",
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Sede creada: {sede.nombre}"))

        credenciales = []

        director = self._crear_usuario(
            username="director",
            first_name="Director",
            last_name="Prueba",
            email="director@prueba.test",
            documento="1000000001",
            role="super_admin",
            is_staff=True,
            is_superuser=True,
            sede=None,
        )
        credenciales.append(("Director", director.username, director.documento_identidad, "—"))

        tipos_coordinador = [
            AdminEscuela.TipoCoordinador.SEDE,
            AdminEscuela.TipoCoordinador.ACADEMICO,
            AdminEscuela.TipoCoordinador.PEDAGOGICO,
            AdminEscuela.TipoCoordinador.FINANCIERO,
            AdminEscuela.TipoCoordinador.LOGISTICO,
        ]
        for i, tipo in enumerate(tipos_coordinador, start=1):
            label = dict(AdminEscuela.TipoCoordinador.choices)[tipo]
            u = self._crear_usuario(
                username=f"coord_{tipo}",
                first_name=label,
                last_name="Prueba",
                email=f"coord.{tipo}@prueba.test",
                documento=f"100000001{i}",
                role="app_admin",
                is_staff=True,
                is_superuser=False,
                sede=sede,
            )
            AdminEscuela.objects.create(
                user=u,
                sede=sede,
                cargo=AdminEscuela.cargo_para_tipo(tipo, sede.nombre),
                tipo_coordinador=tipo,
                is_active=True,
            )
            credenciales.append((f"Coordinador ({label})", u.username, u.documento_identidad, "—"))

        profesor_user = self._crear_usuario(
            username="profesor_prueba",
            first_name="Profesor",
            last_name="Prueba",
            email="profesor@prueba.test",
            documento="1000000020",
            role="user",
            is_staff=False,
            is_superuser=False,
            sede=sede,
        )
        Profesor.objects.create(
            user=profesor_user,
            sede=sede,
            is_active=True,
        )
        credenciales.append(("Profesor", profesor_user.username, profesor_user.documento_identidad, "—"))

        estudiante_user = self._crear_usuario(
            username="estudiante_prueba",
            first_name="Estudiante",
            last_name="Prueba",
            email="estudiante@prueba.test",
            documento="1000000030",
            role="user",
            is_staff=False,
            is_superuser=False,
            sede=sede,
        )
        Estudiante.objects.create(
            user=estudiante_user,
            sede=sede,
            numero_documento=estudiante_user.documento_identidad or "",
            is_active=True,
        )
        credenciales.append(("Estudiante", estudiante_user.username, estudiante_user.documento_identidad, "—"))

        multi = self._crear_usuario(
            username="coord_multi",
            first_name="Coordinador",
            last_name="Multi",
            email="coord.multi@prueba.test",
            documento="1000000040",
            role="app_admin",
            is_staff=True,
            is_superuser=False,
            sede=sede,
        )
        admin_multi = AdminEscuela.objects.create(
            user=multi,
            sede=sede,
            cargo=AdminEscuela.cargo_para_capacidades(
                ["academico", "pedagogico", "financiero", "logistico"],
                sede.nombre,
            ),
            tipo_coordinador=AdminEscuela.TipoCoordinador.COMBINADO,
            capacidades_explicitas=True,
            is_active=True,
        )
        for orden, codigo in enumerate(
            ["academico", "pedagogico", "financiero", "logistico"],
            start=1,
        ):
            cap, _ = CapacidadCoordinador.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": codigo.replace("_", " ").title(),
                    "orden": orden,
                },
            )
            AdminEscuelaCapacidad.objects.get_or_create(
                admin_escuela=admin_multi,
                capacidad=cap,
                defaults={"orden": orden},
            )
        credenciales.append(
            ("Coordinador (varios roles)", multi.username, multi.documento_identidad, "—")
        )

        self.stdout.write(self.style.SUCCESS("\nListo. Credenciales (misma contraseña para todos):"))
        self.stdout.write(self.style.WARNING(f"Contraseña: {PASSWORD}\n"))
        ancho = max(len(row[0]) for row in credenciales) + 2
        for rol, username, documento, _ in credenciales:
            self.stdout.write(f"  {rol.ljust(ancho)} usuario: {username.ljust(20)} documento: {documento}")

    def _crear_usuario(self, *, username, first_name, last_name, email, documento, role, is_staff, is_superuser, sede):
        user = User.objects.create(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            documento_identidad=documento,
            role=role,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_verified=True,
            is_active=True,
            sede=sede,
        )
        user.set_password(PASSWORD)
        user.save()
        return user
