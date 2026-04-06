"""Variables de plantilla para hechos."""


def profesor_entregas_pendientes(request):
    """
    Conteo de entregas con evidencia pendientes de calificar (solo docentes).
    """
    if not request.user.is_authenticated or not hasattr(request.user, 'profesor_profile'):
        return {'profesor_entregas_pendientes_count': 0}

    from hechos.views import get_user_sede
    from hechos.profesor_entregas import entregas_pendientes_calificacion_qs

    qs = entregas_pendientes_calificacion_qs(request.user, get_user_sede(request.user))
    return {'profesor_entregas_pendientes_count': qs.count()}
