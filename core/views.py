import unicodedata
from collections import OrderedDict

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import json_script as html_json_script

from core.colombia_geo import nombre_departamento
from core.forms import (
    CoordinadorForm,
    DirectorProfesorEditForm,
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
from hechos.portal_entry import home_redirect_response
from hechos.models import (
    AdminEscuela,
    Escuela,
    EscuelaProgramaPlantilla,
    NivelProgramaPlantilla,
    Estudiante,
    NotificacionEstudiante,
    Profesor,
    RutaEstudio,
    Curso,
    Salon,
)
from hechos import seguimiento_import as seg_imp
from hechos.seguimiento_import import (
    SeguimientoImportError,
    analyze_seguimiento_preview_against_bd,
    build_seguimiento_preview,
    execute_seguimiento_import,
)

User = get_user_model()


def _programa_agrupado_plantillas_global(escuelas_qs, niveles_plantilla_qs):
    """
    Agrupa escuelas plantilla por nivel (catálogo global).
    Usa querysets ya materializados (p. ej. tras list()) para no repetir consultas.
    """
    grupos = {}
    for ep in escuelas_qs:
        grupos.setdefault(ep.nivel_plantilla_id, []).append(ep)
    out = []
    for np in niveles_plantilla_qs:
        out.append(
            {
                "nivel_programa": np,
                "nivel_display": np.titulo_acordeon(),
                "escuelas": grupos.get(np.pk, []),
            }
        )
    return out


def _escuela_programa_plantilla_form_edit(*args, nivel_plantilla_queryset=None, **kwargs):
    if nivel_plantilla_queryset is not None:
        kwargs.setdefault("nivel_plantilla_queryset", nivel_plantilla_queryset)
    return EscuelaProgramaPlantillaEditForm(*args, **kwargs)


def _escuela_programa_form_edit(sede, *args, **kwargs):
    return EscuelaProgramaForm(
        *args,
        sede=sede,
        prefix="programa_edit",
        checkbox_js_class="js-programa-edit-tiene-matricula",
        **kwargs,
    )


def _sync_cupo_escuela_desde_salon(escuela, capacidad: int) -> None:
    """Cupo de la escuela operativa alineado a la capacidad del salón."""
    escuela.cupo_maximo = max(0, int(capacidad or 0))
    escuela.save(update_fields=['cupo_maximo', 'updated_at'])


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
        return home_redirect_response(request.user)

    return render(request, 'core/inicio.html')


@login_required
def dashboard(request):
    """
    Redirección al inicio real según el usuario.
    """
    return home_redirect_response(request.user)


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


def _normaliza_texto(valor):
    """Minúsculas sin tildes ni espacios extremos, para comparar ubicaciones libres."""
    base = unicodedata.normalize("NFKD", (valor or "").strip())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return base.casefold()


@login_required
def director_dashboard(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    dep_filtro = (request.GET.get('dep') or "").strip()
    ciudad_filtro = (request.GET.get('ciudad') or "").strip()
    q = (request.GET.get('q') or "").strip()
    hay_filtro = bool(ciudad_filtro or dep_filtro or q)

    sedes = list(Sede.objects.all())
    sedes.sort(key=_sede_ubicacion_sort_key)

    ciudades = OrderedDict()
    for sede in sedes:
        ciu = (sede.ciudad or "").strip()
        if not ciu:
            continue
        dep = (sede.departamento or "").strip()
        clave = (dep.casefold(), _normaliza_texto(ciu))
        chip = ciudades.get(clave)
        if chip is None:
            ciudades[clave] = {
                'label': _sede_ubicacion_label(sede),
                'dep': dep,
                'ciudad': ciu,
                'total': 1,
            }
        else:
            chip['total'] += 1
    ciudades_disponibles = list(ciudades.values())
    for chip in ciudades_disponibles:
        chip['activo'] = (
            chip['dep'].casefold() == dep_filtro.casefold()
            and _normaliza_texto(chip['ciudad']) == _normaliza_texto(ciudad_filtro)
        )

    sedes_filtradas = sedes
    if ciudad_filtro:
        objetivo = _normaliza_texto(ciudad_filtro)
        sedes_filtradas = [
            s for s in sedes_filtradas
            if _normaliza_texto(s.ciudad) == objetivo
            and (not dep_filtro or (s.departamento or "").strip().casefold() == dep_filtro.casefold())
        ]
    if q:
        objetivo = _normaliza_texto(q)
        sedes_filtradas = [
            s for s in sedes_filtradas
            if objetivo in _normaliza_texto(s.nombre) or objetivo in _normaliza_texto(s.direccion)
        ]

    grupos = OrderedDict()
    if hay_filtro:
        for sede in sedes_filtradas:
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
        'ciudades_disponibles': ciudades_disponibles,
        'hay_filtro': hay_filtro,
        'ciudad_filtro': ciudad_filtro,
        'dep_filtro': dep_filtro,
        'q': q,
        'total_sedes': len(sedes),
        'total_resultados': len(sedes_filtradas) if hay_filtro else 0,
    }
    return render(request, 'core/director_dashboard.html', context)


def _querystring_without_page(request):
    q = request.GET.copy()
    q.pop("page", None)
    s = q.urlencode()
    return f"&{s}" if s else ""


@login_required
def director_profesores(request):
    if not _director_required(request):
        return redirect("core:dashboard")

    qs = Profesor.objects.select_related("user", "sede").order_by(
        "user__first_name", "user__last_name", "id"
    )
    q = (request.GET.get("q") or "").strip()
    sede_id = _parse_pk(request.GET.get("sede"))
    if sede_id is not None:
        qs = qs.filter(sede_id=sede_id)
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__documento_identidad__icontains=q)
            | Q(codigo_profesor__icontains=q)
        )

    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    sedes_fil = Sede.objects.filter(is_active=True).order_by("nombre").only("id", "nombre")

    context = {
        "page_obj": page_obj,
        "search_q": q,
        "sede_filter": sede_id,
        "sedes_fil": sedes_fil,
        "filters_query": _querystring_without_page(request),
    }
    return render(request, "core/director_profesores.html", context)


@login_required
def director_profesor_edit(request, profesor_id):
    if not _director_required(request):
        return redirect("core:dashboard")

    profesor = get_object_or_404(
        Profesor.objects.select_related("user"),
        pk=profesor_id,
    )
    u = profesor.user

    if request.method == "POST":
        form = DirectorProfesorEditForm(request.POST, user_instance=u)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.apply_to(profesor)
                messages.success(
                    request,
                    f"Se actualizó el profesor «{profesor.user.get_full_name() or profesor.user.username}».",
                )
                return redirect("core:director_profesores")
            except IntegrityError as exc:
                messages.error(request, f"No se pudo guardar (dato duplicado): {exc}")
    else:
        td = (u.tipo_documento or "").strip()
        form = DirectorProfesorEditForm(
            user_instance=u,
            initial={
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email or "",
                "phone": u.phone or "",
                "tipo_documento": td if any(td == c[0] for c in User.TipoDocumento.choices) else "",
                "documento_identidad": u.documento_identidad or "",
                "sede": profesor.sede_id,
                "especialidad": profesor.especialidad,
                "experiencia_anos": profesor.experiencia_anos,
                "biografia": profesor.biografia,
                "is_active": profesor.is_active,
            },
        )

    context = {
        "profesor": profesor,
        "form": form,
    }
    return render(request, "core/director_profesor_edit.html", context)


def _parse_pk(raw):
    if raw in (None, ''):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


@login_required
def director_import_seguimiento(request):
    """
    Importación de seguimiento (Excel): elegir sede, subir archivo; el texto de oferta por fila
    se cruza con las escuelas operativas activas de esa sede (sin elegir escuela a mano).
    """
    if not _director_required(request):
        return redirect('core:dashboard')

    sedes = Sede.objects.filter(is_active=True).order_by('ciudad', 'nombre')
    errors: list[str] = []
    preview = None
    match_report = None
    import_exec_report = None

    if request.method == 'POST':
        raw_sede = request.POST.get('sede')
    else:
        raw_sede = request.GET.get('sede')

    selected_sede_id = _parse_pk(raw_sede)
    if raw_sede not in (None, '') and selected_sede_id is None:
        errors.append('El valor de sede no es válido.')

    sede_valida = False
    if selected_sede_id is not None:
        if Sede.objects.filter(pk=selected_sede_id, is_active=True).exists():
            sede_valida = True
        else:
            errors.append('La sede indicada no existe o está inactiva.')

    escuelas_operativas_sede_count = 0
    if sede_valida and selected_sede_id:
        escuelas_operativas_sede_count = Escuela.objects.filter(
            sede_id=selected_sede_id,
            is_active=True,
        ).count()

    if request.method == 'POST':
        if raw_sede in (None, ''):
            errors.append(
                'Selecciona una sede y pulsa «Continuar» antes de subir el archivo.'
            )

        archivo = request.FILES.get('archivo')
        if not archivo:
            errors.append('Selecciona un archivo Excel (.xlsx).')
        elif not archivo.name.lower().endswith('.xlsx'):
            errors.append('Solo se admiten archivos con extensión .xlsx.')
        elif getattr(archivo, 'size', 0) and archivo.size > seg_imp.MAX_UPLOAD_BYTES:
            max_mb = max(1, seg_imp.MAX_UPLOAD_BYTES // (1024 * 1024))
            errors.append(
                f'El archivo pesa demasiado (máximo aprox. {max_mb} MB). Reduce el tamaño o divide el libro.'
            )

        if not errors and archivo and sede_valida and selected_sede_id:
            try:
                preview = build_seguimiento_preview(archivo)
            except SeguimientoImportError as exc:
                errors.append(str(exc))
            else:
                sede_obj = get_object_or_404(Sede, pk=selected_sede_id, is_active=True)
                match_report = analyze_seguimiento_preview_against_bd(preview, sede_obj)
                ejecutar = request.POST.get('ejecutar_importacion') == '1'
                if ejecutar:
                    crear_ofertas = request.POST.get('crear_ediciones_faltantes') == '1'
                    import_exec_report = execute_seguimiento_import(
                        preview,
                        sede_obj,
                        match_report=match_report,
                        crear_ediciones_faltantes=crear_ofertas,
                    )
                    sc = import_exec_report.status_counts()
                    messages.success(
                        request,
                        'Importación aplicada: '
                        f'{sc.get("created", 0)} con credenciales nuevas (revisa la tabla), '
                        f'{sc.get("matricula_ok", 0)} con matrícula asegurada u omitida por duplicado, '
                        f'{sc.get("skipped", 0)} filas sin escuela operativa, '
                        f'{sc.get("error", 0)} errores. '
                        'Las contraseñas solo aparecen en esta pantalla: guárdalas o comunícalas con cuidado.',
                    )
                else:
                    messages.success(
                        request,
                        'Vista previa y análisis listos. Para crear usuarios y matrículas, marca la casilla correspondiente y vuelve a enviar el mismo archivo.',
                    )

    context = {
        'sedes': sedes,
        'sede_valida': sede_valida,
        'selected_sede_id': selected_sede_id,
        'escuelas_operativas_sede_count': escuelas_operativas_sede_count,
        'errors': errors,
        'preview': preview,
        'match_report': match_report,
        'import_exec_report': import_exec_report,
        'import_max_file_mb': max(1, seg_imp.MAX_UPLOAD_BYTES // (1024 * 1024)),
        'import_preview_rows': seg_imp.DEFAULT_PREVIEW_MAX_ROWS,
    }
    return render(request, 'core/director_import_seguimiento.html', context)


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

    niveles_programa = (
        NivelProgramaPlantilla.objects.annotate(num_escuelas=Count("escuelas"))
        .order_by("jerarquia", "nombre")
    )
    escuelas_programa = (
        EscuelaProgramaPlantilla.objects.select_related("nivel_plantilla")
        .order_by("nivel_plantilla__jerarquia", "nombre")
    )
    list(niveles_programa)
    list(escuelas_programa)

    form_programa = EscuelaProgramaPlantillaForm(
        nivel_plantilla_queryset=niveles_programa,
    )
    form_programa_edit = _escuela_programa_plantilla_form_edit(
        nivel_plantilla_queryset=niveles_programa,
    )
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
            form_programa = EscuelaProgramaPlantillaForm(
                nivel_plantilla_queryset=niveles_programa,
            )
            form_programa_edit = _escuela_programa_plantilla_form_edit(
                nivel_plantilla_queryset=niveles_programa,
            )
            if form_nivel.is_valid():
                NivelProgramaPlantilla.objects.create(
                    jerarquia=form_nivel.cleaned_data["jerarquia"],
                    nombre=form_nivel.cleaned_data["nombre"],
                    descripcion=form_nivel.cleaned_data.get("descripcion") or "",
                )
                messages.success(request, "Nivel del programa global creado.")
                return redirect("core:director_programa_escuelas")
        elif accion == "editar_nivel":
            nid = (request.POST.get("nivel_id") or "").strip()
            form_programa = EscuelaProgramaPlantillaForm(
                nivel_plantilla_queryset=niveles_programa,
            )
            form_programa_edit = _escuela_programa_plantilla_form_edit(
                nivel_plantilla_queryset=niveles_programa,
            )
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
                messages.success(request, "Nivel actualizado.")
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
                    messages.success(request, "Nivel eliminado.")
            return redirect("core:director_programa_escuelas")
        elif accion == "crear_programa":
            form_programa = EscuelaProgramaPlantillaForm(
                data=request.POST,
                nivel_plantilla_queryset=niveles_programa,
            )
            form_programa_edit = _escuela_programa_plantilla_form_edit(
                nivel_plantilla_queryset=niveles_programa,
            )
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
                    messages.success(
                        request,
                        "Escuela del programa global registrada.",
                    )
                    return redirect("core:director_programa_escuelas")
                except IntegrityError:
                    form_programa.add_error(
                        None,
                        "Ya existe una escuela con este nivel y nombre en el programa global.",
                    )
        elif accion == "editar_programa":
            form_programa = EscuelaProgramaPlantillaForm(
                nivel_plantilla_queryset=niveles_programa,
            )
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
                nivel_plantilla_queryset=niveles_programa,
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
                    messages.success(
                        request,
                        "Escuela del programa global actualizada.",
                    )
                    return redirect("core:director_programa_escuelas")
            else:
                abrir_dialog_editar_programa = True
        elif accion == "eliminar_programa":
            pid = request.POST.get("programa_id")
            if pid and pid.isdigit():
                EscuelaProgramaPlantilla.objects.filter(id=int(pid)).delete()
                messages.success(request, "Escuela del programa global eliminada.")
            return redirect("core:director_programa_escuelas")

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
            "programa_por_nivel": _programa_agrupado_plantillas_global(
                escuelas_programa,
                niveles_programa,
            ),
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

    niveles_plantilla = NivelProgramaPlantilla.objects.order_by("jerarquia", "nombre")
    escuelas_plantilla = EscuelaProgramaPlantilla.objects.select_related(
        "nivel_plantilla"
    ).order_by("nivel_plantilla__jerarquia", "nombre")

    return render(
        request,
        "core/coordinador_sede_escuelas.html",
        {
            "sede": sede,
            "programa_por_nivel": _programa_agrupado_plantillas_global(
                escuelas_plantilla,
                niveles_plantilla,
            ),
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

            sal = Salon.objects.filter(sede=sede, escuela=escuela, is_active=True).first()
            if sal:
                _sync_cupo_escuela_desde_salon(escuela, sal.capacidad_plazas)

            if not RutaEstudio.objects.filter(escuela=escuela, is_active=True).exists():
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

                en = (escuela.nombre or '').strip() or 'Escuela'
                ruta = RutaEstudio.objects.create(
                    sede=sede,
                    escuela=escuela,
                    nombre=en,
                    descripcion="",
                    duracion_semanas=12,
                    nivel="basico",
                    is_active=True,
                )
                Curso.objects.create(
                    sede=sede,
                    ruta_estudio=ruta,
                    nombre=en,
                    descripcion="",
                    orden=1,
                    duracion_semanas=curso_duracion_semanas,
                    is_active=True,
                )
                escuela.fecha_inicio = fecha_inicio
                escuela.fecha_fin = fecha_fin
                if not (escuela.horario or '').strip():
                    escuela.horario = 'Horario por definir'
                escuela.save(
                    update_fields=['fecha_inicio', 'fecha_fin', 'horario', 'updated_at'],
                )
                if sal:
                    _sync_cupo_escuela_desde_salon(escuela, sal.capacidad_plazas)

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


def _password_change_form_styled(user, data=None):
    if data is not None:
        form = PasswordChangeForm(user=user, data=data)
    else:
        form = PasswordChangeForm(user=user)
    inp = "profile-field w-full"
    for name, auto in (
        ("old_password", "current-password"),
        ("new_password1", "new-password"),
        ("new_password2", "new-password"),
    ):
        if name in form.fields:
            form.fields[name].widget.attrs.update({"class": inp, "autocomplete": auto})
            form.fields[name].help_text = ""
    return form


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

    password_form = _password_change_form_styled(request.user)

    if request.method == 'POST':
        if request.POST.get("profile_password"):
            password_form = _password_change_form_styled(request.user, data=request.POST)
            if password_form.is_valid():
                u = password_form.save()
                update_session_auth_hash(request, u)
                messages.success(request, "Contraseña actualizada correctamente.")
                return redirect("core:profile")
        elif request.POST.get("profile_account"):
            email_raw = (request.POST.get("email") or "").strip().lower()
            if email_raw:
                try:
                    validate_email(email_raw)
                except ValidationError:
                    messages.error(request, "El correo no tiene un formato válido.")
                    return redirect("core:profile")
                if (
                    User.objects.filter(email__iexact=email_raw)
                    .exclude(pk=request.user.pk)
                    .exists()
                ):
                    messages.error(
                        request,
                        "Ese correo ya está en uso en otra cuenta. Prueba con otro o inicia sesión con esa cuenta.",
                    )
                else:
                    request.user.email = email_raw
                    try:
                        request.user.save(update_fields=["email", "updated_at"])
                    except IntegrityError:
                        messages.error(
                            request,
                            "No se pudo guardar el correo (duplicado u otro error).",
                        )
                        return redirect("core:profile")
                    messages.success(request, "Correo actualizado.")
            else:
                request.user.email = None
                request.user.save(update_fields=["email", "updated_at"])
                messages.success(request, "Correo quitado. Puedes añadir uno nuevo cuando quieras.")
            return redirect("core:profile")
        elif request.POST.get("profile_contact"):
            request.user.phone = (request.POST.get("phone") or "").strip() or None
            direccion = (request.POST.get("direccion") or "").strip()
            request.user.direccion = direccion
            request.user.save(update_fields=["phone", "direccion", "updated_at"])
            if estudiante_profile:
                estudiante_profile.direccion = direccion
                estudiante_profile.save(update_fields=["direccion", "updated_at"])
            messages.success(request, "Celular y dirección actualizados.")
            return redirect("core:profile")

        avatar = request.FILES.get("avatar")
        if avatar:
            request.user.avatar = avatar
            request.user.save(update_fields=["avatar"])
            messages.success(request, "Foto de perfil actualizada.")
            return redirect("core:profile")
        if not request.POST.get("profile_password"):
            messages.warning(request, "Selecciona una imagen para actualizar tu foto.")
            return redirect("core:profile")

    direccion_perfil = (request.user.direccion or "").strip()
    if not direccion_perfil and estudiante_profile:
        direccion_perfil = (estudiante_profile.direccion or "").strip()

    context = {
        "estudiante_profile": estudiante_profile,
        "profesor_profile": profesor_profile,
        "admin_escuela_profile": admin_escuela_profile,
        "notificaciones_estudiante": notificaciones_estudiante,
        "direccion_perfil": direccion_perfil,
        "password_form": password_form,
    }

    return render(request, "core/profile_modern.html", context)


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
