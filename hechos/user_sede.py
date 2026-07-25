"""
Sede operativa del usuario (un solo lugar; misma lógica en toda la app).
"""


def get_user_sede(user):
    """
    Obtiene la sede del usuario basada en su perfil o en User.sede.
    """
    if hasattr(user, 'estudiante_profile') and user.estudiante_profile.sede:
        return user.estudiante_profile.sede
    if hasattr(user, 'profesor_profile') and user.profesor_profile.sede:
        return user.profesor_profile.sede
    if hasattr(user, 'admin_escuela_profile') and user.admin_escuela_profile.sede:
        return user.admin_escuela_profile.sede
    if user.sede:
        return user.sede
    return None
