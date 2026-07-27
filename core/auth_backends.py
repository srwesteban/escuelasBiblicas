import re

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


def _login_identifier_variants(login: str) -> list[str]:
    raw = (login or "").strip()
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    add(raw)
    digits = re.sub(r"[\s.\-]", "", raw)
    if digits.isdigit() and digits != raw:
        add(digits)
    return out


class EmailOrDocumentBackend(ModelBackend):
    """
    Login solo con número de documento (username, User.documento_identidad o
    Estudiante.numero_documento). El correo ya no se acepta como identificador.
    Debe ir antes que ModelBackend / AuthenticationBackend de allauth.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not password:
            return None
        login = (username or kwargs.get("email") or "").strip()
        if not login or "@" in login:
            return None

        User = get_user_model()
        user = None

        for candidate in _login_identifier_variants(login):
            user = User.objects.filter(username__iexact=candidate).first()
            if user:
                break
        if user is None:
            # Documento en el propio User (director, coordinador, profesor o
            # estudiante): cubre a cualquier rol, no solo estudiantes.
            for candidate in _login_identifier_variants(login):
                user = User.objects.filter(documento_identidad__iexact=candidate).first()
                if user:
                    break
        if user is None:
            from hechos.models import Estudiante

            for candidate in _login_identifier_variants(login):
                est = (
                    Estudiante.objects.filter(numero_documento__iexact=candidate)
                    .select_related("user")
                    .first()
                )
                if est:
                    user = est.user
                    break

        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
