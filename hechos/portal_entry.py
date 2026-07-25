"""
Un solo criterio para “a dónde te lleva el portal” tras login o al pulsar inicio.
Evita duplicar lógica entre core.views y hechos.views y el bucle core:dashboard <-> hechos:dashboard.
"""
from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import redirect

from core.models import UserAppPermission
from hechos import coordinador_access as ca


def _user_has_hechos_profile(user) -> bool:
    return bool(
        hasattr(user, 'estudiante_profile')
        or hasattr(user, 'profesor_profile')
        or hasattr(user, 'admin_escuela_profile')
    )


def _user_has_sede_in_profile(user) -> bool:
    if hasattr(user, 'estudiante_profile') and user.estudiante_profile.sede_id:
        return True
    if hasattr(user, 'profesor_profile') and user.profesor_profile.sede_id:
        return True
    if hasattr(user, 'admin_escuela_profile') and user.admin_escuela_profile.sede_id:
        return True
    return bool(getattr(user, 'sede_id', None))


def home_redirect_response(user) -> HttpResponse:
    """
    Destino atendiendo: superuser, tareas operativas (sede / finanzas / logística), perfiles Hechos,
    módulos opcionales (UserAppPermission), y cierre en perfil si el rol no mapea a un destino concreto.
    """
    if user.is_super_admin():
        return redirect('core:director_dashboard')

    op = ca.redirect_operational_home_user(user)
    if op is not None:
        return op

    if not _user_has_hechos_profile(user):
        user_permission = (
            UserAppPermission.objects.filter(
                user=user,
                can_view=True,
                app_module__is_active=True,
            )
            .select_related('app_module')
            .order_by('app_module__order')
            .first()
        )
        if user_permission:
            return redirect(user_permission.app_module.url_name)
        return redirect('core:profile')

    p = getattr(user, 'admin_escuela_profile', None)
    if p and ca.has_capacidad(user, 'pedagogico'):
        return redirect('hechos:profesores_list')
    if not _user_has_sede_in_profile(user):
        if hasattr(user, 'estudiante_profile'):
            return redirect('hechos:seleccionar_sede_estudiante')
        return redirect('core:profile')
    if hasattr(user, 'estudiante_profile'):
        return redirect('hechos:escuelas_disponibles')
    if hasattr(user, 'profesor_profile'):
        return redirect('hechos:mis_escuelas_profesor')
    if p and ca.has_capacidad(user, 'academico'):
        return redirect('hechos:estudiantes_list')
    return redirect('core:profile')
