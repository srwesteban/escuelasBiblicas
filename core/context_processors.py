"""Variables de plantilla globales."""


def sede_actual(request):
    """Sede operativa del usuario (misma lógica que get_user_sede en hechos)."""
    if not request.user.is_authenticated:
        return {}
    from hechos.user_sede import get_user_sede

    s = get_user_sede(request.user)
    return {"sede_actual": s}
