"""
Permisos por tipo de coordinador (AdminEscuela.tipo_coordinador).
"""
from django.contrib import messages
from django.shortcuts import redirect

from hechos.models import AdminEscuela


def admin_tipo(user):
    p = getattr(user, 'admin_escuela_profile', None)
    if not p or not p.is_active:
        return None
    return p.tipo_coordinador


def redirect_operational_home_if_restricted(request):
    """
    Coordinadores de sede, financiero y logístico no usan el dashboard general de Hechos.
    """
    if request.user.is_super_admin() or not hasattr(request.user, 'admin_escuela_profile'):
        return None
    p = request.user.admin_escuela_profile
    if not p.sede_id:
        return None
    sid = p.sede_id
    if p.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
        return redirect('core:coordinador_sede_equipo', sede_id=sid)
    if p.tipo_coordinador == AdminEscuela.TipoCoordinador.FINANCIERO:
        return redirect('hechos:coordinador_recursos')
    if p.tipo_coordinador == AdminEscuela.TipoCoordinador.LOGISTICO:
        return redirect('hechos:coordinador_logistica')
    return None


def require_academico(request):
    if request.user.is_super_admin():
        return None
    if admin_tipo(request.user) == AdminEscuela.TipoCoordinador.ACADEMICO:
        return None
    messages.error(request, 'Solo el coordinador académico puede acceder a esta sección.')
    return redirect('core:dashboard')


def require_pedagogico(request):
    if request.user.is_super_admin():
        return None
    if admin_tipo(request.user) == AdminEscuela.TipoCoordinador.PEDAGOGICO:
        return None
    messages.error(request, 'Solo el coordinador pedagógico puede acceder a esta sección.')
    return redirect('core:dashboard')


def require_academico_o_pedagogico(request):
    if request.user.is_super_admin():
        return None
    t = admin_tipo(request.user)
    if t in (
        AdminEscuela.TipoCoordinador.ACADEMICO,
        AdminEscuela.TipoCoordinador.PEDAGOGICO,
    ):
        return None
    messages.error(request, 'No tienes permisos para esta sección.')
    return redirect('core:dashboard')


def admin_may_access_clases_list(user):
    if user.is_super_admin():
        return True
    if hasattr(user, 'estudiante_profile') or hasattr(user, 'profesor_profile'):
        return True
    t = admin_tipo(user)
    return t in (
        AdminEscuela.TipoCoordinador.ACADEMICO,
        AdminEscuela.TipoCoordinador.PEDAGOGICO,
    )
