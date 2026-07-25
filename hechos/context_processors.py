"""Variables de plantilla para hechos."""


def profesor_entregas_pendientes(request):
    """
    Conteo de entregas con evidencia pendientes de calificar (solo docentes).
    """
    if not request.user.is_authenticated or not hasattr(request.user, 'profesor_profile'):
        return {
            'profesor_entregas_pendientes_count': 0,
            'profesor_solicitudes_matricula_pendientes_count': 0,
        }

    from hechos.user_sede import get_user_sede
    from hechos.profesor_entregas import entregas_pendientes_calificacion_qs
    from hechos.models import SolicitudMatricula

    user_sede = get_user_sede(request.user)
    qs = entregas_pendientes_calificacion_qs(request.user, user_sede)
    prof = request.user.profesor_profile
    sol_count = (
        SolicitudMatricula.objects.filter(
            sede=user_sede,
            estado='pendiente',
            escuela__maestro=prof,
        ).count()
        if user_sede
        else 0
    )
    return {
        'profesor_entregas_pendientes_count': qs.count(),
        'profesor_solicitudes_matricula_pendientes_count': sol_count,
    }
