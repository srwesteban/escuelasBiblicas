from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import UserAppPermission
from hechos.models import AdminEscuela, Estudiante, Profesor

User = get_user_model()

ROLE_ORDER = ("super_admin", "app_admin", "user")


class Command(BaseCommand):
    help = (
        "Escribe un listado de usuarios desde la BD: correo, User.role, "
        "perfil Hechos (si existe) y módulos con permiso."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--output",
            default="USUARIOS_CORREOS_POR_ROL.md",
            help="Ruta del archivo markdown (relativa al directorio actual).",
        )

    def handle(self, *args, **options):
        out_path = options["output"]

        admin_by_user = {a.user_id: a for a in AdminEscuela.objects.select_related("user")}
        prof_users = set(Profesor.objects.values_list("user_id", flat=True))
        est_users = set(Estudiante.objects.values_list("user_id", flat=True))

        perm_by_user = {}
        for p in UserAppPermission.objects.filter(can_view=True).select_related("app_module"):
            perm_by_user.setdefault(p.user_id, []).append(p.app_module.name)

        users = list(User.objects.all().order_by("-date_joined"))
        by_role = {}
        for u in users:
            by_role.setdefault(u.role, []).append(u)

        lines = [
            "# Usuarios desde la base de datos",
            "",
            f"Generado: {timezone.now().isoformat(timespec='seconds')}",
            f"Total usuarios: {len(users)}",
            "",
            "Actualizar este archivo:",
            "",
            "```bash",
            "python manage.py export_usuarios_roles",
            "```",
            "",
            "**Rol** = campo `User.role` en `core`. **Perfil Hechos** = `AdminEscuela`, `Profesor` o `Estudiante` si existe.",
            "",
        ]

        for role in ROLE_ORDER:
            bucket = by_role.get(role) or []
            if not bucket:
                continue
            lines.append(f"## `{role}`")
            lines.append("")
            lines.append("| Correo | Activo | staff | superuser | Perfil Hechos | Módulos (vista) |")
            lines.append("|--------|--------|-------|-----------|---------------|-----------------|")
            for u in sorted(bucket, key=lambda x: (-x.date_joined.timestamp(), (x.email or "").lower())):
                hechos = ""
                if u.id in admin_by_user:
                    ae = admin_by_user[u.id]
                    hechos = f"AdminEscuela ({ae.get_tipo_coordinador_display()})"
                elif u.id in prof_users:
                    hechos = "Profesor"
                elif u.id in est_users:
                    hechos = "Estudiante"
                mods = ", ".join(sorted(perm_by_user.get(u.id, []))) or "—"
                lines.append(
                    f"| {u.email} | {u.is_active} | {u.is_staff} | {u.is_superuser} | {hechos or '—'} | {mods} |"
                )
            lines.append("")

        extra_roles = [r for r in by_role if r not in ROLE_ORDER and by_role[r]]
        for role in sorted(extra_roles):
            lines.append(f"## `{role}` (valor en BD fuera de choices estándar)")
            lines.append("")
            for u in sorted(by_role[role], key=lambda x: (x.email or "").lower()):
                lines.append(f"- {u.email}")
            lines.append("")

        text = "\n".join(lines).rstrip() + "\n"

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)

        self.stdout.write(self.style.SUCCESS(f"Escrito: {out_path} ({len(users)} usuarios)"))
