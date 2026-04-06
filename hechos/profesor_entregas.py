"""Consultas de entregas de actividades para el docente (evita import circular views ↔ context_processor)."""

from django.db.models import Q

from hechos.models import EntregaActividad


def entregas_pendientes_calificacion_qs(user, user_sede):
    """
    Entregas con evidencia (texto o archivo) que aún no tienen evaluado_en,
    de actividades de escuelas donde el usuario es maestro asignado.
    """
    if user_sede is None or not getattr(user, 'profesor_profile', None):
        return EntregaActividad.objects.none()
    prof = user.profesor_profile
    return (
        EntregaActividad.objects.filter(
            sede=user_sede,
            evaluado_en__isnull=True,
            actividad__is_active=True,
            actividad__escuela__maestro=prof,
            actividad__escuela__is_active=True,
        )
        .filter(Q(texto__gt='') | Q(archivo__gt=''))
        .select_related('actividad__escuela', 'estudiante__user')
        .order_by('-actualizado_en')
    )
