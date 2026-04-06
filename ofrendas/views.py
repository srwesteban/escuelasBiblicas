from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from hechos.forms import OfrendaForm
from hechos.models import Escuela, Ofrenda


def _get_user_sede(user):
    if hasattr(user, "estudiante_profile") and user.estudiante_profile.sede:
        return user.estudiante_profile.sede
    if hasattr(user, "profesor_profile") and user.profesor_profile.sede:
        return user.profesor_profile.sede
    if hasattr(user, "admin_escuela_profile") and user.admin_escuela_profile.sede:
        return user.admin_escuela_profile.sede
    if user.sede:
        return user.sede
    return None


@login_required
def list_profesor(request):
    if not hasattr(request.user, "profesor_profile"):
        messages.error(request, "Solo los profesores pueden acceder a esta página.")
        return redirect("core:dashboard")

    user_sede = _get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, "No tienes una sede asignada. Contacta al administrador.")
        return redirect("core:dashboard")

    profesor = request.user.profesor_profile
    escuelas_qs = Escuela.objects.filter(
        sede=user_sede,
        maestro=profesor,
        is_active=True,
    ).order_by("nombre")

    ofrendas = (
        Ofrenda.objects.filter(sede=user_sede, escuela__in=escuelas_qs)
        .select_related("escuela", "registrado_por")
        .order_by("-fecha", "-id")
    )

    return render(
        request,
        "ofrendas/ofrendas_list.html",
        {
            "user_sede": user_sede,
            "profesor": profesor,
            "escuelas": escuelas_qs,
            "ofrendas": ofrendas,
        },
    )


@login_required
def registrar(request):
    if not hasattr(request.user, "profesor_profile"):
        messages.error(request, "Solo los profesores pueden acceder a esta página.")
        return redirect("core:dashboard")

    user_sede = _get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, "No tienes una sede asignada. Contacta al administrador.")
        return redirect("core:dashboard")

    profesor = request.user.profesor_profile
    escuelas_qs = Escuela.objects.filter(
        sede=user_sede,
        maestro=profesor,
        is_active=True,
    ).order_by("-updated_at", "-id")

    if not escuelas_qs.exists():
        messages.warning(
            request,
            "Aún no tienes escuelas asignadas como maestro, por eso no puedes registrar ofrendas.",
        )
        return redirect("ofrendas:list")

    varias_escuelas = escuelas_qs.count() > 1

    if request.method == "POST":
        form = OfrendaForm(request.POST, escuelas_qs=escuelas_qs, include_escuela=varias_escuelas)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.sede = user_sede
            obj.escuela = form.cleaned_data["escuela"] if varias_escuelas else escuelas_qs.first()
            obj.fecha = timezone.now().date()
            obj.descripcion = ""
            obj.registrado_por = request.user
            obj.save()
            messages.success(request, "Ofrenda registrada correctamente.")
            return redirect("ofrendas:list")
    else:
        form = OfrendaForm(escuelas_qs=escuelas_qs, include_escuela=varias_escuelas)

    return render(
        request,
        "ofrendas/ofrenda_form.html",
        {
            "user_sede": user_sede,
            "profesor": profesor,
            "escuela_auto": None if varias_escuelas else escuelas_qs.first(),
            "varias_escuelas": varias_escuelas,
            "form": form,
        },
    )
