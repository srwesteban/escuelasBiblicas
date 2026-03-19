from datetime import datetime, date
from django.utils import timezone


def get_current_period():
    """
    Determina el período académico actual basado en la fecha
    Retorna formato: YYYY-S (donde S es 1 para primer semestre, 2 para segundo)
    """
    now = timezone.now().date()
    year = now.year
    month = now.month
    
    # Primer semestre: Enero a Junio (1-6)
    # Segundo semestre: Julio a Diciembre (7-12)
    if month <= 6:
        semester = 1
    else:
        semester = 2
    
    return f"{year}-{semester}"


def get_period_from_date(date_obj):
    """
    Determina el período académico basado en una fecha específica
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    
    year = date_obj.year
    month = date_obj.month
    
    # Primer semestre: Enero a Junio (1-6)
    # Segundo semestre: Julio a Diciembre (7-12)
    if month <= 6:
        semester = 1
    else:
        semester = 2
    
    return f"{year}-{semester}"


def get_period_display(period):
    """
    Convierte el período de formato YYYY-S a texto legible
    Ej: 2025-1 -> "Primer Semestre 2025"
    """
    try:
        year, semester = period.split('-')
        semester_num = int(semester)
        
        if semester_num == 1:
            return f"Primer Semestre {year}"
        elif semester_num == 2:
            return f"Segundo Semestre {year}"
        else:
            return period
    except (ValueError, IndexError):
        return period


def get_period_choices():
    """
    Genera opciones de períodos para formularios
    Incluye el período actual y los últimos 2 años
    """
    current_year = timezone.now().year
    choices = []
    
    # Generar opciones para los últimos 3 años
    for year in range(current_year - 1, current_year + 2):
        for semester in [1, 2]:
            period = f"{year}-{semester}"
            display = get_period_display(period)
            choices.append((period, display))
    
    return choices


def get_period_stats():
    """
    Retorna estadísticas de períodos para el dashboard
    """
    current_period = get_current_period()
    current_year = timezone.now().year
    
    return {
        'current_period': current_period,
        'current_period_display': get_period_display(current_period),
        'current_year': current_year,
        'available_periods': get_period_choices()
    }

