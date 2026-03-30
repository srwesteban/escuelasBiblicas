from collections import OrderedDict

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.colombia_geo import nombre_departamento
from core.forms import CoordinadorForm, EscuelaSedeForm, PastorSedeFormSet, SedeForm
from .models import AppModule, Sede, UserAppPermission
from hechos.models import (
    AdminEscuela,
    Escuela,
    Estudiante,
    NotificacionEstudiante,
    Profesor,
    RutaEstudio,
    Curso,
    EdicionCurso,
)

User = get_user_model()


def _user_has_hechos_profile(user):
    return (
        hasattr(user, 'estudiante_profile')
        or hasattr(user, 'profesor_profile')
        or hasattr(user, 'admin_escuela_profile')
    )


def _user_has_sede_in_profile(user):
    try:
        if hasattr(user, 'estudiante_profile') and user.estudiante_profile.sede_id:
            return True
    except Exception:
        pass
    try:
        if hasattr(user, 'profesor_profile') and user.profesor_profile.sede_id:
            return True
    except Exception:
        pass
    try:
        if hasattr(user, 'admin_escuela_profile') and user.admin_escuela_profile.sede_id:
            return True
    except Exception:
        pass
    return bool(getattr(user, 'sede_id', None))


def _home_redirect_response(user):
    if user.is_super_admin():
        return redirect('core:director_dashboard')

    if hasattr(user, 'admin_escuela_profile'):
        p = user.admin_escuela_profile
        if p.sede_id:
            if p.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
                return redirect('core:coordinador_sede_equipo', sede_id=p.sede_id)
            if p.tipo_coordinador == AdminEscuela.TipoCoordinador.FINANCIERO:
                return redirect('hechos:coordinador_recursos')
            if p.tipo_coordinador == AdminEscuela.TipoCoordinador.LOGISTICO:
                return redirect('hechos:coordinador_logistica')

    if _user_has_hechos_profile(user):
        p = getattr(user, 'admin_escuela_profile', None)
        if (
            p
            and p.tipo_coordinador == AdminEscuela.TipoCoordinador.PEDAGOGICO
        ):
            return redirect('hechos:profesores_list')
        # Estudiante sin sede: obligar a elegir sede (flujo post-registro).
        if not _user_has_sede_in_profile(user):
            if hasattr(user, 'estudiante_profile'):
                return redirect('hechos:seleccionar_sede_estudiante')
            return redirect('core:profile')
        return redirect('hechos:dashboard')

    user_permission = UserAppPermission.objects.filter(
        user=user,
        can_view=True,
        app_module__is_active=True,
    ).select_related('app_module').order_by('app_module__order').first()
    if user_permission:
        return redirect(user_permission.app_module.url_name)

    return redirect('core:profile')


def _coordinador_sede_may_manage(request, sede):
    if request.user.is_super_admin():
        return True
    p = getattr(request.user, 'admin_escuela_profile', None)
    return bool(
        p
        and p.is_active
        and p.sede_id == sede.id
        and p.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE
    )


def _allowed_tipos_coordinador(request, sede, editing):
    if request.user.is_super_admin():
        return [t[0] for t in AdminEscuela.TipoCoordinador.choices]
    if not _coordinador_sede_may_manage(request, sede):
        return []
    if editing:
        if editing.user_id == request.user.id:
            return [AdminEscuela.TipoCoordinador.SEDE]
        if editing.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
            return []
    return [
        AdminEscuela.TipoCoordinador.ACADEMICO,
        AdminEscuela.TipoCoordinador.PEDAGOGICO,
        AdminEscuela.TipoCoordinador.FINANCIERO,
        AdminEscuela.TipoCoordinador.LOGISTICO,
    ]


def _coordinador_cancel_url(request, sede_id):
    if request.user.is_super_admin():
        return reverse('core:director_sede_detail', args=[sede_id])
    return reverse('core:coordinador_sede_equipo', args=[sede_id])


def _coordinador_post_redirect(request, sede_id):
    if request.user.is_super_admin():
        return redirect('core:director_sede_detail', sede_id=sede_id)
    return redirect('core:coordinador_sede_equipo', sede_id=sede_id)


def inicio(request):
    """
    Landing pública del sistema.
    """
    if request.user.is_authenticated:
        return _home_redirect_response(request.user)

    return render(request, 'core/inicio.html')


@login_required
def dashboard(request):
    """
    Redirección al inicio real según el usuario.
    """
    return _home_redirect_response(request.user)


def _director_required(request):
    if not request.user.is_super_admin():
        messages.error(request, 'Solo el director puede acceder a esta sección.')
        return False
    return True


def _sede_ubicacion_label(sede):
    ciu = (sede.ciudad or "").strip()
    dep = (sede.departamento or "").strip()
    if dep and ciu:
        return f"{ciu}, {nombre_departamento(dep)}"
    if ciu:
        return ciu
    return "Sin ubicación"


def _sede_ubicacion_sort_key(sede):
    dep_name = nombre_departamento(sede.departamento) if (sede.departamento or "").strip() else ""
    ciu = (sede.ciudad or "").strip()
    return (dep_name.casefold(), ciu.casefold(), sede.nombre.casefold())


@login_required
def director_dashboard(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    sedes = list(Sede.objects.all())
    sedes.sort(key=_sede_ubicacion_sort_key)

    grupos = OrderedDict()
    for sede in sedes:
        label = _sede_ubicacion_label(sede)
        coordinadores = AdminEscuela.objects.filter(sede=sede, is_active=True).select_related('user')
        item = {
            'sede': sede,
            'coordinadores_count': coordinadores.count(),
            'coordinadores': coordinadores[:3],
        }
        grupos.setdefault(label, []).append(item)

    sedes_por_ubicacion = [{'label': label, 'items': items} for label, items in grupos.items()]

    context = {
        'sedes_por_ubicacion': sedes_por_ubicacion,
    }
    return render(request, 'core/director_dashboard.html', context)


@login_required
def sede_create(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = SedeForm(request.POST, request.FILES)
        pastores_formset = PastorSedeFormSet(request.POST, request.FILES, prefix='pastores')
        if form.is_valid() and pastores_formset.is_valid():
            sede = form.save()
            pastores_formset.instance = sede
            pastores_formset.save()
            messages.success(request, f'Sede {sede.nombre} creada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm()
        pastores_formset = PastorSedeFormSet(prefix='pastores')

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
            'pastores_formset': pastores_formset,
            'page_title': 'Crear sede',
        },
    )


@login_required
def sede_edit(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)

    if request.method == 'POST':
        form = SedeForm(request.POST, request.FILES, instance=sede)
        pastores_formset = PastorSedeFormSet(request.POST, request.FILES, instance=sede, prefix='pastores')
        if form.is_valid() and pastores_formset.is_valid():
            sede = form.save()
            pastores_formset.instance = sede
            pastores_formset.save()
            messages.success(request, f'Sede {sede.nombre} actualizada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm(instance=sede)
        pastores_formset = PastorSedeFormSet(instance=sede, prefix='pastores')

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
            'pastores_formset': pastores_formset,
            'page_title': 'Editar sede',
            'sede': sede,
        },
    )


@login_required
def sede_delete(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    if request.method == 'POST':
        password = (request.POST.get('confirm_password') or '').strip()
        if not request.user.check_password(password):
            messages.error(request, 'Contraseña incorrecta. La sede no se eliminó.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
        sede.is_active = False
        sede.save(update_fields=['is_active'])
        messages.success(request, f'Sede {sede.nombre} eliminada correctamente.')
        return redirect('core:director_dashboard')
    return redirect('core:director_dashboard')


@login_required
def director_sede_detail(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    coordinadores = AdminEscuela.objects.filter(
        sede=sede,
        is_active=True,
        user__is_active=True,
    ).select_related('user').order_by(
        'user__first_name', 'user__last_name'
    )

    context = {
        'sede': sede,
        'coordinadores': coordinadores,
        'pastores_adicionales': sede.pastores_adicionales.all(),
    }
    return render(request, 'core/director_sede_detail.html', context)


@login_required
def coordinador_sede_equipo(request, sede_id):
    sede = get_object_or_404(Sede, id=sede_id)
    p = getattr(request.user, 'admin_escuela_profile', None)
    if (
        not p
        or p.sede_id != sede.id
        or p.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ):
        messages.error(request, 'Solo el coordinador de sede puede gestionar el equipo.')
        return redirect('core:dashboard')

    coordinadores = (
        AdminEscuela.objects.filter(
            sede=sede,
            is_active=True,
            user__is_active=True,
        )
        .exclude(user=request.user)
        .select_related('user')
        .order_by('user__first_name', 'user__last_name')
    )

    return render(
        request,
        'core/coordinador_sede_equipo.html',
        {
            'sede': sede,
            'coordinadores': coordinadores,
        },
    )


@login_required
def coordinador_sede_escuelas(request, sede_id):
    sede = get_object_or_404(Sede, id=sede_id)
    p = getattr(request.user, 'admin_escuela_profile', None)
    if (
        not p
        or p.sede_id != sede.id
        or p.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ):
        messages.error(request, 'Solo el coordinador de sede puede gestionar las escuelas.')
        return redirect('core:dashboard')

    if request.method == 'POST' and request.POST.get('accion') == 'crear_escuela':
        form = EscuelaSedeForm(sede, request.POST)
        if form.is_valid():
            escuela = form.save()
            cupo_maximo = int(form.cleaned_data["cupo_maximo"])

            # Creamos la estructura mínima para que el sistema tenga cupos
            # visibles en "Escuelas disponibles" (se calcula desde EdicionCurso.cupo_maximo).
            from datetime import date, timedelta
            from django.utils import timezone

            today = timezone.localdate()
            anio = int(escuela.anio or today.year)

            # Evita errores si el día no existe en el año destino (ej. 29 feb).
            try:
                fecha_base = today.replace(year=anio)
            except ValueError:
                fecha_base = date(anio, today.month, 28)

            fecha_inicio = (
                fecha_base if escuela.ciclo == "A" else fecha_base + timedelta(weeks=12)
            )
            # Por ahora usamos la duración por defecto del modelo de Curso.
            curso_duracion_semanas = 4
            fecha_fin = fecha_inicio + timedelta(weeks=curso_duracion_semanas)

            ruta = RutaEstudio.objects.create(
                sede=sede,
                escuela=escuela,
                nombre=f"Nivel {escuela.ciclo} · Grupo {escuela.grupo}",
                descripcion="",
                duracion_semanas=12,
                nivel="basico",
                is_active=True,
            )

            curso = Curso.objects.create(
                sede=sede,
                ruta_estudio=ruta,
                nombre=f"Curso {escuela.ciclo} · Grupo {escuela.grupo}",
                descripcion="",
                orden=1,
                duracion_semanas=curso_duracion_semanas,
                is_active=True,
            )

            EdicionCurso.objects.create(
                curso=curso,
                nombre_edicion=f"Grupo {escuela.grupo}",
                profesor=escuela.maestro,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                horario="Horario por definir",
                aula="",
                cupo_maximo=cupo_maximo,
                is_active=True,
            )

            messages.success(request, 'Escuela creada correctamente.')
            return redirect('core:coordinador_sede_escuelas', sede_id=sede.id)
    else:
        form = EscuelaSedeForm(sede)

    escuelas = (
        Escuela.objects.filter(sede=sede, is_active=True)
        .select_related('maestro__user')
        .order_by('-anio', 'ciclo', 'grupo', 'nombre')
    )

    # Para mostrar cupos en las tarjetas, calculamos cupo máximo desde la edición base.
    escuela_ids = list(escuelas.values_list("id", flat=True))
    cupos_por_escuela = {}
    if escuela_ids:
        ediciones = (
            EdicionCurso.objects.filter(
                is_active=True,
                curso__is_active=True,
                curso__ruta_estudio__is_active=True,
                curso__ruta_estudio__escuela_id__in=escuela_ids,
            )
            .select_related("curso__ruta_estudio__escuela")
            .order_by("id")
        )
        for ed in ediciones:
            cupos_por_escuela[ed.curso.ruta_estudio.escuela_id] = ed.cupo_maximo

    for e in escuelas:
        e.cupo_maximo = cupos_por_escuela.get(e.id)

    return render(
        request,
        'core/coordinador_sede_escuelas.html',
        {
            'sede': sede,
            'escuelas': escuelas,
            'form': form,
        },
    )


def _require_coordinador_sede_for_sede(request, sede):
    p = getattr(request.user, 'admin_escuela_profile', None)
    if (
        not p
        or p.sede_id != sede.id
        or p.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ):
        messages.error(request, 'Solo el coordinador de sede puede gestionar las escuelas.')
        return None
    return p


@login_required
def coordinador_sede_escuela_edit(request, sede_id, escuela_id):
    sede = get_object_or_404(Sede, id=sede_id)
    if not _require_coordinador_sede_for_sede(request, sede):
        return redirect('core:dashboard')

    escuela = get_object_or_404(Escuela, id=escuela_id, sede=sede, is_active=True)

    if request.method == 'POST':
        form = EscuelaSedeForm(sede, request.POST, instance=escuela)
        if form.is_valid():
            escuela = form.save()
            cupo_maximo = int(form.cleaned_data["cupo_maximo"])

            # Actualizar edición base si existe; si no, crearla.
            ed = (
                EdicionCurso.objects.filter(
                    curso__ruta_estudio__escuela=escuela,
                    is_active=True,
                    curso__is_active=True,
                )
                .order_by("id")
                .select_related("curso__ruta_estudio")
                .first()
            )
            if ed:
                ed.cupo_maximo = cupo_maximo
                ed.profesor = escuela.maestro
                ed.nombre_edicion = f"Grupo {escuela.grupo}"
                ed.save(update_fields=["cupo_maximo", "profesor", "nombre_edicion"])
            else:
                # Reutilizamos la misma lógica mínima que en creación.
                from datetime import date, timedelta
                from django.utils import timezone

                today = timezone.localdate()
                anio = int(escuela.anio or today.year)
                try:
                    fecha_base = today.replace(year=anio)
                except ValueError:
                    fecha_base = date(anio, today.month, 28)

                fecha_inicio = (
                    fecha_base if escuela.ciclo == "A" else fecha_base + timedelta(weeks=12)
                )
                curso_duracion_semanas = 4
                fecha_fin = fecha_inicio + timedelta(weeks=curso_duracion_semanas)

                ruta = RutaEstudio.objects.create(
                    sede=sede,
                    escuela=escuela,
                    nombre=f"Nivel {escuela.ciclo} · Grupo {escuela.grupo}",
                    descripcion="",
                    duracion_semanas=12,
                    nivel="basico",
                    is_active=True,
                )
                curso = Curso.objects.create(
                    sede=sede,
                    ruta_estudio=ruta,
                    nombre=f"Curso {escuela.ciclo} · Grupo {escuela.grupo}",
                    descripcion="",
                    orden=1,
                    duracion_semanas=curso_duracion_semanas,
                    is_active=True,
                )
                EdicionCurso.objects.create(
                    curso=curso,
                    nombre_edicion=f"Grupo {escuela.grupo}",
                    profesor=escuela.maestro,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    horario="Horario por definir",
                    aula="",
                    cupo_maximo=cupo_maximo,
                    is_active=True,
                )

            messages.success(request, 'Escuela actualizada correctamente.')
            return redirect('core:coordinador_sede_escuelas', sede_id=sede.id)
    else:
        form = EscuelaSedeForm(sede, instance=escuela)

    return render(
        request,
        'core/coordinador_sede_escuela_form.html',
        {
            'sede': sede,
            'escuela': escuela,
            'form': form,
        },
    )


@login_required
def coordinador_sede_escuela_delete(request, sede_id, escuela_id):
    sede = get_object_or_404(Sede, id=sede_id)
    if not _require_coordinador_sede_for_sede(request, sede):
        return redirect('core:dashboard')

    escuela = get_object_or_404(Escuela, id=escuela_id, sede=sede, is_active=True)
    if request.method != 'POST':
        return redirect('core:coordinador_sede_escuelas', sede_id=sede.id)

    escuela.is_active = False
    escuela.save(update_fields=['is_active'])

    # Ocultar también la estructura académica asociada para que no aparezca en escuelas disponibles.
    RutaEstudio.objects.filter(escuela=escuela, is_active=True).update(is_active=False)
    Curso.objects.filter(ruta_estudio__escuela=escuela, is_active=True).update(is_active=False)
    EdicionCurso.objects.filter(curso__ruta_estudio__escuela=escuela, is_active=True).update(is_active=False)

    messages.success(request, 'Escuela eliminada correctamente.')
    return redirect('core:coordinador_sede_escuelas', sede_id=sede.id)


@login_required
def coordinador_create(request, sede_id):
    sede = get_object_or_404(Sede, id=sede_id)
    if not _coordinador_sede_may_manage(request, sede):
        messages.error(request, 'No tienes permisos para crear coordinadores en esta sede.')
        return redirect('core:dashboard')

    allowed_tipos = _allowed_tipos_coordinador(request, sede, editing=None)
    if not allowed_tipos:
        messages.error(request, 'No puedes crear coordinadores en este contexto.')
        return redirect('core:dashboard')

    hechos_module = AppModule.objects.filter(name='hechos').first()

    if request.method == 'POST':
        form = CoordinadorForm(
            request.POST,
            request.FILES,
            allowed_tipos=allowed_tipos,
        )
        if form.is_valid():
            form.save(User, sede, hechos_module)
            messages.success(request, 'Coordinador creado correctamente.')
            return _coordinador_post_redirect(request, sede.id)
    else:
        form = CoordinadorForm(allowed_tipos=allowed_tipos)

    context = {
        'form': form,
        'sede': sede,
        'page_title': 'Crear coordinador',
        'submit_label': 'Crear coordinador',
        'cancel_url': _coordinador_cancel_url(request, sede.id),
    }
    return render(request, 'core/coordinador_form.html', context)


@login_required
def coordinador_edit(request, sede_id, coordinador_id):
    sede = get_object_or_404(Sede, id=sede_id)
    admin_profile = get_object_or_404(
        AdminEscuela,
        id=coordinador_id,
        sede=sede,
        is_active=True,
        user__is_active=True,
    )

    if not request.user.is_super_admin() and not _coordinador_sede_may_manage(request, sede):
        messages.error(request, 'No tienes permisos para editar coordinadores de esta sede.')
        return redirect('core:dashboard')

    perfil_coordinador = getattr(request.user, 'admin_escuela_profile', None)
    if (
        not request.user.is_super_admin()
        and perfil_coordinador
        and perfil_coordinador.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE
        and admin_profile.user_id == request.user.id
    ):
        messages.info(
            request,
            'Tu nombre, correo y foto se actualizan en Mi perfil. Desde el equipo solo gestionas a los demás coordinadores.',
        )
        return redirect('core:profile')

    if (
        not request.user.is_super_admin()
        and admin_profile.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE
        and admin_profile.user_id != request.user.id
    ):
        messages.error(request, 'No puedes editar a otro coordinador de sede.')
        return redirect('core:coordinador_sede_equipo', sede_id=sede.id)

    allowed_tipos = _allowed_tipos_coordinador(request, sede, editing=admin_profile)
    if not allowed_tipos:
        messages.error(request, 'No puedes editar este coordinador.')
        return redirect(_coordinador_cancel_url(request, sede.id))

    hechos_module = AppModule.objects.filter(name='hechos').first()

    if request.method == 'POST':
        form = CoordinadorForm(
            request.POST,
            request.FILES,
            admin_profile=admin_profile,
            allowed_tipos=allowed_tipos,
        )
        if form.is_valid():
            form.save(User, sede, hechos_module)
            messages.success(request, 'Coordinador actualizado correctamente.')
            return _coordinador_post_redirect(request, sede.id)
    else:
        form = CoordinadorForm(
            admin_profile=admin_profile,
            allowed_tipos=allowed_tipos,
            initial={
                'nombres': admin_profile.user.first_name,
                'apellidos': admin_profile.user.last_name,
                'email': admin_profile.user.email,
                'tipo_coordinador': admin_profile.tipo_coordinador,
                'is_active': admin_profile.is_active and admin_profile.user.is_active,
            },
        )

    context = {
        'form': form,
        'sede': sede,
        'coordinador': admin_profile,
        'page_title': 'Editar coordinador',
        'submit_label': 'Guardar cambios',
        'cancel_url': _coordinador_cancel_url(request, sede.id),
    }
    return render(request, 'core/coordinador_form.html', context)


@login_required
def coordinador_delete(request, sede_id, coordinador_id):
    sede = get_object_or_404(Sede, id=sede_id)
    admin_profile = get_object_or_404(
        AdminEscuela,
        id=coordinador_id,
        sede=sede,
        is_active=True,
        user__is_active=True,
    )

    if not request.user.is_super_admin() and not _coordinador_sede_may_manage(request, sede):
        messages.error(request, 'No tienes permisos para eliminar coordinadores de esta sede.')
        return redirect('core:dashboard')

    if not request.user.is_super_admin():
        if admin_profile.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
            messages.error(request, 'No se puede eliminar al coordinador de sede desde el equipo.')
            return _coordinador_post_redirect(request, sede.id)
        if admin_profile.user_id == request.user.id:
            messages.error(request, 'No puedes eliminar tu propio usuario desde aquí.')
            return _coordinador_post_redirect(request, sede.id)

    if request.method == 'POST':
        admin_profile.is_active = False
        admin_profile.save(update_fields=['is_active'])
        admin_profile.user.is_active = False
        admin_profile.user.save(update_fields=['is_active'])
        messages.success(request, 'Coordinador eliminado correctamente.')

    return _coordinador_post_redirect(request, sede.id)


@login_required
def profile(request):
    """
    Vista del perfil del usuario
    """
    estudiante_profile = None
    profesor_profile = None
    admin_escuela_profile = None

    try:
        estudiante_profile = request.user.estudiante_profile
    except Exception:
        pass

    try:
        profesor_profile = request.user.profesor_profile
    except Exception:
        pass

    try:
        admin_escuela_profile = request.user.admin_escuela_profile
    except Exception:
        pass

    notificaciones_estudiante = []
    if estudiante_profile:
        notificaciones_estudiante = list(
            NotificacionEstudiante.objects.filter(estudiante=estudiante_profile).order_by('-created_at')[:15]
        )

    if request.method == 'POST':
        avatar = request.FILES.get('avatar')
        if avatar:
            request.user.avatar = avatar
            request.user.save(update_fields=['avatar'])
            messages.success(request, 'Foto de perfil actualizada.')
            return redirect('core:profile')
        messages.warning(request, 'Selecciona una imagen para actualizar tu foto.')
        return redirect('core:profile')

    context = {
        'estudiante_profile': estudiante_profile,
        'profesor_profile': profesor_profile,
        'admin_escuela_profile': admin_escuela_profile,
        'notificaciones_estudiante': notificaciones_estudiante,
    }

    return render(request, 'core/profile_modern.html', context)


def get_user_modules(request):
    """
    API endpoint para obtener módulos del usuario
    """
    if not request.user.is_authenticated:
        return JsonResponse({'modules': []})
    
    modules = []
    
    if request.user.is_super_admin():
        modules = list(AppModule.objects.filter(is_active=True).values(
            'name', 'display_name', 'description', 'icon', 'url_name'
        ).order_by('order'))
    else:
        user_permissions = UserAppPermission.objects.filter(
            user=request.user,
            can_view=True
        ).select_related('app_module')
        
        modules = [{
            'name': perm.app_module.name,
            'display_name': perm.app_module.display_name,
            'description': perm.app_module.description,
            'icon': perm.app_module.icon,
            'url_name': perm.app_module.url_name,
        } for perm in user_permissions if perm.app_module.is_active]
    
    return JsonResponse({'modules': modules})
