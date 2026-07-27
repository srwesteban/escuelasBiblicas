from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand

from django.utils import timezone

from core.models import AppModule, Sede, UserAppPermission
from hechos.models import AdminEscuela, Escuela, Estudiante, Profesor, RutaEstudio

User = get_user_model()


class Command(BaseCommand):
    help = "Crea datos locales base y usuarios de prueba por rol"

    default_password = "local12345"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Preparando base local de desarrollo..."))

        self.setup_site()
        modules = self.setup_modules()
        sede = self.setup_sede()
        self.setup_escuelas_y_niveles(sede)
        self.create_demo_users(sede, modules)

        self.stdout.write(self.style.SUCCESS("\nBase local lista."))
        self.stdout.write(self.style.WARNING("Contraseña por defecto para todos los usuarios: local12345"))

    def setup_site(self):
        site, _ = Site.objects.update_or_create(
            id=1,
            defaults={
                "domain": "localhost:8000",
                "name": "HechosHub Local",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Site configurado: {site.domain}"))

    def setup_modules(self):
        modules = {}
        modules_data = [
            {
                "name": "hechos",
                "display_name": "Escuelas Biblicas",
                "description": "Gestion de estudiantes, profesores y cursos",
                "url_name": "hechos:dashboard",
                "icon": "fas fa-graduation-cap",
                "order": 1,
            },
        ]

        for module_data in modules_data:
            module, _ = AppModule.objects.update_or_create(
                name=module_data["name"],
                defaults=module_data,
            )
            modules[module.name] = module
            self.stdout.write(self.style.SUCCESS(f"Modulo listo: {module.display_name}"))

        return modules

    def setup_sede(self):
        sede, _ = Sede.objects.update_or_create(
            nombre="Sede Local",
            defaults={
                "direccion": "Av. Desarrollo 123",
                "telefono": "+52 555 000 0000",
                "email": "local@hechoshub.test",
                "descripcion": "Sede local para desarrollo y pruebas",
                "is_active": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Sede lista: {sede.nombre}"))
        return sede

    def setup_escuelas_y_niveles(self, sede):
        escuelas = [
            {
                "nombre": "Escuela de Fundamentos",
                "descripcion": "Escuela base para nuevos creyentes y estudiantes iniciales.",
                "niveles": [
                    {
                        "nombre": "Nivel 1",
                        "descripcion": "Nivel inicial para usuarios de prueba",
                        "duracion_semanas": 12,
                        "nivel": "basico",
                    },
                    {
                        "nombre": "Nivel 2",
                        "descripcion": "Continuidad para estudiantes en desarrollo",
                        "duracion_semanas": 12,
                        "nivel": "intermedio",
                    },
                ],
            },
            {
                "nombre": "Escuela de Liderazgo",
                "descripcion": "Escuela avanzada para escenarios de prueba",
                "niveles": [
                    {
                        "nombre": "Nivel Liderazgo",
                        "descripcion": "Nivel avanzado para escenarios de prueba",
                        "duracion_semanas": 16,
                        "nivel": "avanzado",
                    },
                ],
            },
        ]

        for escuela_data in escuelas:
            escuela, _ = Escuela.objects.update_or_create(
                sede=sede,
                nombre=escuela_data["nombre"],
                anio=timezone.now().year,
                ciclo=Escuela.Ciclo.A,
                grupo=1,
                defaults={
                    "descripcion": escuela_data["descripcion"],
                    "is_active": True,
                },
            )
            for nivel_data in escuela_data["niveles"]:
                RutaEstudio.objects.update_or_create(
                    sede=sede,
                    escuela=escuela,
                    nombre=nivel_data["nombre"],
                    defaults=nivel_data,
                )

        self.stdout.write(self.style.SUCCESS("Escuelas y niveles base asegurados"))

    def create_demo_users(self, sede, modules):
        users_data = [
            {
                "email": "super1@local.test",
                "username": "super1",
                "first_name": "Super",
                "last_name": "Uno",
                "role": "super_admin",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "email": "super2@local.test",
                "username": "super2",
                "first_name": "Super",
                "last_name": "Dos",
                "role": "super_admin",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "email": "hechos.admin1@local.test",
                "username": "hechos_admin1",
                "first_name": "Admin",
                "last_name": "Hechos Uno",
                "role": "app_admin",
                "module": "hechos",
                "profile": "admin_escuela",
                "profile_defaults": {"cargo": "Coordinador General", "sede": sede},
            },
            {
                "email": "hechos.admin2@local.test",
                "username": "hechos_admin2",
                "first_name": "Admin",
                "last_name": "Hechos Dos",
                "role": "app_admin",
                "module": "hechos",
                "profile": "admin_escuela",
                "profile_defaults": {"cargo": "Director Academico", "sede": sede},
            },
            {
                "email": "profesor1@local.test",
                "username": "profesor1",
                "first_name": "Profesor",
                "last_name": "Uno",
                "role": "user",
                "module": "hechos",
                "profile": "profesor",
                "profile_defaults": {
                    "sede": sede,
                    "especialidad": "Teologia Basica",
                    "experiencia_anos": 5,
                    "biografia": "Perfil de prueba para desarrollo local.",
                },
            },
            {
                "email": "profesor2@local.test",
                "username": "profesor2",
                "first_name": "Profesor",
                "last_name": "Dos",
                "role": "user",
                "module": "hechos",
                "profile": "profesor",
                "profile_defaults": {
                    "sede": sede,
                    "especialidad": "Liderazgo",
                    "experiencia_anos": 8,
                    "biografia": "Perfil de prueba para desarrollo local.",
                },
            },
            {
                "email": "estudiante1@local.test",
                "username": "estudiante1",
                "first_name": "Estudiante",
                "last_name": "Uno",
                "role": "user",
                "module": "hechos",
                "profile": "estudiante",
                "profile_defaults": {
                    "sede": sede,
                    "telefono_emergencia": "555-1001",
                },
            },
            {
                "email": "estudiante2@local.test",
                "username": "estudiante2",
                "first_name": "Estudiante",
                "last_name": "Dos",
                "role": "user",
                "module": "hechos",
                "profile": "estudiante",
                "profile_defaults": {
                    "sede": sede,
                    "telefono_emergencia": "555-1002",
                },
            },
        ]

        profile_models = {
            "admin_escuela": AdminEscuela,
            "profesor": Profesor,
            "estudiante": Estudiante,
        }

        for user_data in users_data:
            module_name = user_data.get("module")
            user_defaults = {
                "username": user_data["username"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "role": user_data["role"],
                "sede": sede if user_data["role"] != "super_admin" else None,
                "is_verified": True,
                "is_active": True,
                "is_staff": user_data.get("is_staff", user_data["role"] in {"super_admin", "app_admin"}),
                "is_superuser": user_data.get("is_superuser", False),
            }

            user, created = User.objects.update_or_create(
                email=user_data["email"],
                defaults=user_defaults,
            )
            user.set_password(self.default_password)
            user.save()

            status = "creado" if created else "actualizado"
            self.stdout.write(self.style.SUCCESS(f"Usuario {status}: {user.email} ({user.role})"))

            if module_name:
                self.assign_module_permission(user, modules[module_name])

            profile_name = user_data.get("profile")
            if profile_name:
                profile_model = profile_models[profile_name]
                profile, profile_created = profile_model.objects.update_or_create(
                    user=user,
                    defaults=user_data["profile_defaults"],
                )
                profile_status = "creado" if profile_created else "actualizado"
                self.stdout.write(self.style.SUCCESS(f"Perfil {profile_name} {profile_status}: {profile}"))

    def assign_module_permission(self, user, module):
        can_manage = user.role == "app_admin"
        permission, created = UserAppPermission.objects.update_or_create(
            user=user,
            app_module=module,
            defaults={
                "can_view": True,
                "can_edit": True,
                "can_delete": can_manage,
                "can_manage": can_manage,
            },
        )
        status = "creado" if created else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Permiso {status}: {user.email} -> {module.name}"))
