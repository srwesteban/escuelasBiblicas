"""
Acceso de coordinadores: capacidades asignadas (AdminEscuelaCapacidad)
con respaldo por tipo_coordinador si no hay filas asignadas (datos antiguos).
"""
from django.contrib import messages
from django.shortcuts import redirect

from hechos.models import AdminEscuela


def _legacy_codigos_por_tipo(tipo: str) -> frozenset:
    if tipo == AdminEscuela.TipoCoordinador.ACADEMICO:
        return frozenset({'academico'})
    if tipo == AdminEscuela.TipoCoordinador.PEDAGOGICO:
        return frozenset({'pedagogico'})
    if tipo == AdminEscuela.TipoCoordinador.FINANCIERO:
        return frozenset({'financiero'})
    if tipo == AdminEscuela.TipoCoordinador.LOGISTICO:
        return frozenset({'logistico'})
    if tipo == AdminEscuela.TipoCoordinador.COMBINADO:
        return frozenset()
    return frozenset()


def capacidades_codigos_usuario(user) -> frozenset:
    """Conjunto de códigos de capacidad efectivos para el usuario."""
    if getattr(user, 'is_super_admin', lambda: False)():
        return frozenset({'academico', 'pedagogico', 'financiero', 'logistico'})
    p = getattr(user, 'admin_escuela_profile', None)
    if not p or not p.is_active:
        return frozenset()
    rows = p.capacidad_asignaciones.select_related('capacidad')
    if rows.exists():
        return frozenset(a.capacidad.codigo for a in rows)
    if getattr(p, 'capacidades_explicitas', False):
        return frozenset()
    return _legacy_codigos_por_tipo(p.tipo_coordinador)


def admin_tipo(user):
    """Compatibilidad: tipo de perfil (etiqueta), o None."""
    p = getattr(user, 'admin_escuela_profile', None)
    if not p or not p.is_active:
        return None
    return p.tipo_coordinador


def has_capacidad(user, codigo: str) -> bool:
    if getattr(user, 'is_super_admin', lambda: False)():
        return True
    return codigo in capacidades_codigos_usuario(user)


def has_any_capacidad(user, codigos) -> bool:
    if getattr(user, 'is_super_admin', lambda: False)():
        return True
    mine = capacidades_codigos_usuario(user)
    return bool(mine.intersection(frozenset(codigos)))


def redirect_operational_home_user(user):
    """
    Coordinadores de sede, financiero y logístico: destino de trabajo operativo
    (no el dashboard general de Hechos). Misma lógica que redirect_operational_home_if_restricted.
    """
    if user.is_super_admin() or not hasattr(user, 'admin_escuela_profile'):
        return None
    p = user.admin_escuela_profile
    if not p.sede_id:
        return None
    sid = p.sede_id
    if p.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
        return redirect('core:coordinador_sede_equipo', sede_id=sid)
    if has_capacidad(user, 'financiero'):
        return redirect('hechos:coordinador_recursos')
    if has_capacidad(user, 'logistico'):
        return redirect('hechos:coordinador_logistica')
    return None


def redirect_operational_home_if_restricted(request):
    """
    Coordinadores de sede, financiero y logístico no usan el dashboard general de Hechos.
    """
    return redirect_operational_home_user(request.user)


def require_capacidad(request, codigo: str, mensaje: str | None = None):
    if request.user.is_super_admin():
        return None
    if has_capacidad(request.user, codigo):
        return None
    messages.error(
        request,
        mensaje or 'No tienes permiso para acceder a esta sección.',
    )
    return redirect('core:dashboard')


def require_any_capacidad(request, codigos, mensaje: str | None = None):
    if request.user.is_super_admin():
        return None
    if has_any_capacidad(request.user, codigos):
        return None
    messages.error(
        request,
        mensaje or 'No tienes permisos para esta sección.',
    )
    return redirect('core:dashboard')


def require_academico(request):
    return require_capacidad(
        request,
        'academico',
        'Necesitas la función académica para acceder a esta sección.',
    )


def require_pedagogico(request):
    return require_capacidad(
        request,
        'pedagogico',
        'Necesitas la función pedagógica para acceder a esta sección.',
    )


def require_academico_o_pedagogico(request):
    return require_any_capacidad(
        request,
        ('academico', 'pedagogico'),
        'Necesitas la función académica o pedagógica para acceder a esta sección.',
    )


def admin_may_access_clases_list(user):
    if user.is_super_admin():
        return True
    if hasattr(user, 'estudiante_profile') or hasattr(user, 'profesor_profile'):
        return True
    return has_any_capacidad(user, ('academico', 'pedagogico'))
