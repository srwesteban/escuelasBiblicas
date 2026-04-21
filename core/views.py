from collections import OrderedDict

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import json_script as html_json_script

from core.colombia_geo import nombre_departamento
from core.forms import (
    CoordinadorForm,
    EscuelaProgramaForm,
    EscuelaProgramaPlantillaForm,
    EscuelaProgramaPlantillaEditForm,
    EscuelaSedeBasicaForm,
    NivelProgramaEditForm,
    NivelProgramaForm,
    NivelProgramaPlantillaEditForm,
    NivelProgramaPlantillaForm,
    PastorSedeFormSet,
    SedeForm,
)
from .models import AppModule, Sede, UserAppPermission
from hechos import coordinador_access as ca
from hechos.models import (
    AdminEscuela,
    Escuela,
    EscuelaPrograma,
    EscuelaProgramaPlantilla,
    NivelPrograma,
    NivelProgramaPlantilla,
    Estudiante,
    NotificacionEstudiante,
    Profesor,
    RutaEstudio,
    Curso,
    EdicionCurso,
    Salon,
)
from hechos.programa_formacion_seed import propagar_catalogo_global_a_todas_las_sedes

User = get_user_model()


def _programa_agrupado_por_nivel(sede, escuelas_programa_qs):
    """
    Lista todos los niveles activos de la sede (orden por número de nivel) y,
    para cada uno, las escuelas del programa asociadas (puede ser ninguna).
    """
    grupos = {}
    for ep in escuelas_programa_qs.select_related("nivel_programa"):
        np_id = ep.nivel_programa_id
        grupos.setdefault(np_id, []).append(ep)
    out = []
    for np in (
        NivelPrograma.objects.filter(sede=sede, is_active=True)
        .order_by("jerarquia", "nombre")
    ):
        out.append(
            {
                "nivel_programa": np,
                "nivel_display": np.titulo_acordeon(),
                "escuelas": grupos.get(np.pk, []),
            }
        )
    return out


def _programa_agrupado_plantillas_global():
    """Agrupa escuelas plantilla por nivel (catálogo global)."""
    escuelas_qs = (
        EscuelaProgramaPlantilla.objects.select_related("nivel_plantilla").order_by(
            "nivel_plantilla__jerarquia",
            "nombre",
        )
    )
    grupos = {}
    for ep in escuelas_qs:
        np = ep.nivel_plantilla
        grupos.setdefault(np.id, []).append(ep)
    out = []
    for np in NivelProgramaPlantilla.objects.order_by("jerarquia", "nombre"):
        out.append(
            {
                "nivel_programa": np,
                "nivel_display": np.titulo_acordeon(),
                "escuelas": grupos.get(np.pk, []),
            }
        )
    return out


def _escuela_programa_plantilla_form_edit(*args, **kwargs):
    return EscuelaProgramaPlantillaEditForm(*args, **kwargs)


def _escuela_programa_form_edit(sede, *args, **kwargs):
    return EscuelaProgramaForm(
        *args,
        sede=sede,
        prefix="programa_edit",
        checkbox_js_class="js-programa-edit-tiene-matricula",
        **kwargs,
    )


def _sync_cupo_ediciones_escuela(escuela, capacidad: int) -> None:
    """Cupo de ediciones activas alineado a capacidad del salón (0 si no hay)."""
    EdicionCurso.objects.filter(
        curso__ruta_estudio__escuela=escuela,
        is_active=True,
        curso__is_active=True,
    ).update(cupo_maximo=capacidad)


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
            if ca.has_capacidad(user, 'financiero'):
                return redirect('hechos:coordinador_recursos')
            if ca.has_capacidad(user, 'logistico'):
                return redirect('hechos:coordinador_logistica')

    if _user_has_hechos_profile(user):
        p = getattr(user, 'admin_escuela_profile', None)
        if p and ca.has_capacidad(user, 'pedagogico'):
            return redirect('hechos:profesores_list')
        # Estudiante sin sede: obligar a elegir sede (flujo post-registro).
        if not _user_has_sede_in_profile(user):
            if hasattr(user, 'estudiante_profile'):
                return redirect('hechos:seleccionar_sede_estudiante')
            return redirect('core:profile')
        if hasattr(user, 'estudiante_profile'):
            return redirect('hechos:escuelas_disponibles')
        if hasattr(user, 'profesor_profile'):
            return redirect('hechos:mis_escuelas_profesor')
        if p and ca.has_capacidad(user, 'academico'):
            return redirect('hechos:estudiantes_list')
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
        return [
            t[0]
            for t in AdminEscuela.TipoCoordinador.choices
            if t[0] != AdminEscuela.TipoCoordinador.COMBINADO
        ]
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
def director_programa_escuelas(request):
    if not _director_required(request):
        return redirect("core:dashboard")

    form_programa = EscuelaProgramaPlantillaForm()
    form_programa_edit = _escuela_programa_plantilla_form_edit()
    form_nivel = NivelProgramaPlantillaForm(prefix="np_nuevo")
    form_nivel_edit = None
    editar_nivel_id = None
    editar_programa_id = None
    abrir_dialog_editar_nivel = False
    abrir_dialog_editar_programa = False

    if request.method == "POST":
        accion = (request.POST.get("accion") or "").strip()
        if accion == "crear_nivel":
            form_nivel = NivelProgramaPlantillaForm(
                data=request.POST, prefix="np_nuevo"
            )
            form_programa = EscuelaProgramaPlantillaForm()
            form_programa_edit = _escuela_programa_plantilla_form_edit()
            if form_nivel.is_valid():
                NivelProgramaPlantilla.objects.create(
                    jerarquia=form_nivel.cleaned_data["jerarquia"],
                    nombre=form_nivel.cleaned_data["nombre"],
                    descripcion=form_nivel.cleaned_data.get("descripcion") or "",
                )
                propagar_catalogo_global_a_todas_las_sedes()
                messages.success(request, "Nivel del programa global creado y replicado en las sedes.")
                return redirect("core:director_programa_escuelas")
        elif accion == "editar_nivel":
            nid = (request.POST.get("nivel_id") or "").strip()
            form_programa = EscuelaProgramaPlantillaForm()
            form_programa_edit = _escuela_programa_plantilla_form_edit()
            form_nivel = NivelProgramaPlantillaForm(prefix="np_nuevo")
            np_obj = None
            if nid.isdigit():
                np_obj = NivelProgramaPlantilla.objects.filter(id=int(nid)).first()
            if np_obj is None:
                messages.error(request, "Nivel no encontrado.")
                return redirect("core:director_programa_escuelas")
            editar_nivel_id = np_obj.id
            form_nivel_edit = NivelProgramaPlantillaEditForm(
                data=request.POST,
                prefix="np_edit",
                nivel_plantilla_pk=np_obj.pk,
            )
            if form_nivel_edit.is_valid():
                np_obj.jerarquia = form_nivel_edit.cleaned_data["jerarquia"]
                np_obj.nombre = form_nivel_edit.cleaned_data["nombre"]
                np_obj.descripcion = form_nivel_edit.cleaned_data.get("descripcion") or ""
                np_obj.save(
                    update_fields=["jerarquia", "nombre", "descripcion", "updated_at"],
                )
                propagar_catalogo_global_a_todas_las_sedes()
                messages.success(request, "Nivel actualizado y replicado en las sedes.")
                return redirect("core:director_programa_escuelas")
            abrir_dialog_editar_nivel = True
        elif accion == "eliminar_nivel":
            nid = (request.POST.get("nivel_id") or "").strip()
            if nid.isdigit():
                np_obj = NivelProgramaPlantilla.objects.filter(id=int(nid)).first()
                if np_obj is None:
                    messages.error(request, "Nivel no encontrado.")
                elif np_obj.escuelas.exists():
                    messages.error(
                        request,
                        "No puedes eliminar este nivel: tiene escuelas del programa asignadas. "
                        "Elimínalas primero.",
                    )
                else:
                    np_obj.delete()
                    propagar_catalogo_global_a_todas_las_sedes()
                    messages.success(request, "Nivel eliminado.")
            return redirect("core:director_programa_escuelas")
        elif accion == "crear_programa":
            form_programa = EscuelaProgramaPlantillaForm(data=request.POST)
            form_programa_edit = _escuela_programa_plantilla_form_edit()
            form_nivel = NivelProgramaPlantillaForm(prefix="np_nuevo")
            form_nivel_edit = None
            if form_programa.is_valid():
                try:
                    EscuelaProgramaPlantilla.objects.create(
                        nivel_plantilla=form_programa.cleaned_data["nivel_plantilla"],
                        nombre=form_programa.cleaned_data["nombre"],
                        descripcion=form_programa.cleaned_data.get("descripcion") or "",
                        tiene_matricula=bool(
                            form_programa.cleaned_data.get("tiene_matricula")
                        ),
                        costo_matricula_cop=form_programa.cleaned_data.get(
                            "costo_matricula_cop"
                        ),
                    )
                    propagar_catalogo_global_a_todas_las_sedes()
                    messages.success(
                        request,
                        "Escuela del programa global registrada y replicada en las sedes.",
                    )
                    return redirect("core:director_programa_escuelas")
                except IntegrityError:
                    form_programa.add_error(
                        None,
                        "Ya existe una escuela con este nivel y nombre en el programa global.",
                    )
        elif accion == "editar_programa":
            form_programa = EscuelaProgramaPlantillaForm()
            pid = (request.POST.get("programa_id") or "").strip()
            ep = None
            if pid.isdigit():
                ep = EscuelaProgramaPlantilla.objects.filter(id=int(pid)).first()
            if ep is None:
                messages.error(request, "Escuela del programa no encontrada.")
                return redirect("core:director_programa_escuelas")
            form_programa_edit = _escuela_programa_plantilla_form_edit(
                request.POST,
                escuela_plantilla_pk=ep.pk,
            )
            form_nivel = NivelProgramaPlantillaForm(prefix="np_nuevo")
            form_nivel_edit = None
            editar_programa_id = ep.id
            if form_programa_edit.is_valid():
                np = form_programa_edit.cleaned_data["nivel_plantilla"]
                new_nombre = form_programa_edit.cleaned_data["nombre"]
                if (
                    EscuelaProgramaPlantilla.objects.filter(
                        nivel_plantilla=np,
                        nombre=new_nombre,
                    )
                    .exclude(pk=ep.pk)
                    .exists()
                ):
                    form_programa_edit.add_error(
                        None,
                        "Ya existe una escuela con este nivel y nombre en el programa global.",
                    )
                    abrir_dialog_editar_programa = True
                else:
                    ep.nivel_plantilla = np
                    ep.nombre = new_nombre
                    ep.descripcion = form_programa_edit.cleaned_data.get("descripcion") or ""
                    ep.tiene_matricula = bool(
                        form_programa_edit.cleaned_data.get("tiene_matricula")
                    )
                    ep.costo_matricula_cop = form_programa_edit.cleaned_data.get(
                        "costo_matricula_cop"
                    )
                    ep.save()
                    propagar_catalogo_global_a_todas_las_sedes()
                    messages.success(
                        request,
                        "Escuela del programa global actualizada y replicada en las sedes.",
                    )
                    return redirect("core:director_programa_escuelas")
            else:
                abrir_dialog_editar_programa = True
        elif accion == "eliminar_programa":
            pid = request.POST.get("programa_id")
            if pid and pid.isdigit():
                EscuelaProgramaPlantilla.objects.filter(id=int(pid)).delete()
                propagar_catalogo_global_a_todas_las_sedes()
                messages.success(request, "Escuela del programa global eliminada.")
            return redirect("core:director_programa_escuelas")

    niveles_programa = NivelProgramaPlantilla.objects.annotate(
        num_escuelas=Count("escuelas"),
    ).order_by("jerarquia", "nombre")

    escuelas_programa = EscuelaProgramaPlantilla.objects.select_related(
        "nivel_plantilla"
    ).order_by("nivel_plantilla__jerarquia", "nombre")

    if form_nivel_edit is None:
        form_nivel_edit = NivelProgramaPlantillaEditForm(
            nivel_plantilla_pk=None,
            prefix="np_edit",
        )

    niveles_edit_data = [
        {
            "id": np.id,
            "jerarquia": np.jerarquia,
            "nombre": np.nombre or "",
            "descripcion": np.descripcion or "",
        }
        for np in niveles_programa
    ]
    niveles_edit_script = html_json_script(
        niveles_edit_data, element_id="niveles-edit-payload"
    )

    escuelas_programa_edit_data = [
        {
            "id": ep.id,
            "nivel_plantilla_id": ep.nivel_plantilla_id,
            "nombre": ep.nombre,
            "descripcion": ep.descripcion or "",
            "tiene_matricula": ep.tiene_matricula,
            "costo_matricula_cop": ep.costo_matricula_cop,
        }
        for ep in escuelas_programa
    ]
    escuelas_programa_edit_script = html_json_script(
        escuelas_programa_edit_data,
        element_id="escuelas-programa-edit-payload",
    )

    return render(
        request,
        "core/director_programa_escuelas.html",
        {
            "programa_por_nivel": _programa_agrupado_plantillas_global(),
            "form_programa": form_programa,
            "form_programa_edit": form_programa_edit,
            "form_nivel": form_nivel,
            "form_nivel_edit": form_nivel_edit,
            "editar_nivel_id": editar_nivel_id,
            "niveles_edit_script": niveles_edit_script,
            "abrir_dialog_editar_nivel": abrir_dialog_editar_nivel,
            "escuelas_programa_edit_script": escuelas_programa_edit_script,
            "abrir_dialog_editar_programa": abrir_dialog_editar_programa,
            "niveles_programa": niveles_programa,
            "editar_programa_id": editar_programa_id,
        },
    )


@login_required
def coordinador_sede_escuelas(request, sede_id):
    sede = get_object_or_404(Sede, id=sede_id)
    p = getattr(request.user, "admin_escuela_profile", None)
    if (
        not p
        or p.sede_id != sede.id
        or p.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ):
        messages.error(request, "Solo el coordinador de sede puede ver esta sección.")
        return redirect("core:dashboard")

    escuelas_programa = (
        EscuelaPrograma.objects.filter(sede=sede, is_active=True)
        .select_related("nivel_programa")
        .order_by("nivel_programa__jerarquia", "nombre")
    )

    return render(
        request,
        "core/coordinador_sede_escuelas.html",
        {
            "sede": sede,
            "programa_por_nivel": _programa_agrupado_por_nivel(sede, escuelas_programa),
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
        form = EscuelaSedeBasicaForm(sede, request.POST, instance=escuela)
        if form.is_valid():
            escuela = form.save()

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
                ed.profesor = escuela.maestro
                ed.save(update_fields=["profesor"])
                sal = Salon.objects.filter(sede=sede, escuela=escuela, is_active=True).first()
                if sal:
                    _sync_cupo_ediciones_escuela(escuela, sal.capacidad_plazas)
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
                    nombre="Ruta base",
                    descripcion="",
                    duracion_semanas=12,
                    nivel="basico",
                    is_active=True,
                )
                curso = Curso.objects.create(
                    sede=sede,
                    ruta_estudio=ruta,
                    nombre="Módulo 1",
                    descripcion="",
                    orden=1,
                    duracion_semanas=curso_duracion_semanas,
                    is_active=True,
                )
                EdicionCurso.objects.create(
                    curso=curso,
                    nombre_edicion="Principal",
                    profesor=escuela.maestro,
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    horario="Horario por definir",
                    aula="",
                    cupo_maximo=0,
                    is_active=True,
                )
                sal = Salon.objects.filter(sede=sede, escuela=escuela, is_active=True).first()
                if sal:
                    _sync_cupo_ediciones_escuela(escuela, sal.capacidad_plazas)

            messages.success(request, 'Escuela actualizada correctamente.')
            return redirect('core:coordinador_sede_escuelas', sede_id=sede.id)
    else:
        form = EscuelaSedeBasicaForm(sede, instance=escuela)

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
                'tipo_documento': getattr(
                    admin_profile.user, 'tipo_documento', None
                )
                or User.TipoDocumento.CC,
                'documento_identidad': getattr(admin_profile.user, 'documento_identidad', None) or '',
                'celular': (getattr(admin_profile.user, 'phone', None) or '').strip(),
                'email': admin_profile.user.email,
                'tipo_coordinador': admin_profile.tipo_coordinador,
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
        if request.POST.get("profile_contact"):
            request.user.phone = (request.POST.get("phone") or "").strip() or None
            direccion = (request.POST.get("direccion") or "").strip()
            request.user.direccion = direccion
            request.user.save(update_fields=["phone", "direccion", "updated_at"])
            if estudiante_profile:
                estudiante_profile.direccion = direccion
                estudiante_profile.save(update_fields=["direccion", "updated_at"])
            messages.success(request, "Celular y dirección actualizados.")
            return redirect("core:profile")

        avatar = request.FILES.get('avatar')
        if avatar:
            request.user.avatar = avatar
            request.user.save(update_fields=['avatar'])
            messages.success(request, 'Foto de perfil actualizada.')
            return redirect('core:profile')
        messages.warning(request, 'Selecciona una imagen para actualizar tu foto.')
        return redirect('core:profile')

    direccion_perfil = (request.user.direccion or "").strip()
    if not direccion_perfil and estudiante_profile:
        direccion_perfil = (estudiante_profile.direccion or "").strip()

    context = {
        'estudiante_profile': estudiante_profile,
        'profesor_profile': profesor_profile,
        'admin_escuela_profile': admin_escuela_profile,
        'notificaciones_estudiante': notificaciones_estudiante,
        'direccion_perfil': direccion_perfil,
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
