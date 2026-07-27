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
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import json_script as html_json_script

from core.colombia_geo import (
    ciudad_choices_for_departamento,
    departamento_choices,
    nombre_departamento,
)
from core.forms import (
    CoordinadorForm,
    EscuelaProgramaForm,
    EscuelaProgramaPlantillaForm,
    EscuelaProgramaPlantillaEditForm,
    NivelProgramaEditForm,
    NivelProgramaForm,
    NivelProgramaPlantillaEditForm,
    NivelProgramaPlantillaForm,
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
        # El Director solo gestiona el coordinador de sede desde /director/sedes/.
        return [AdminEscuela.TipoCoordinador.SEDE]
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


def _active_coordinadores_sede_qs(sede):
    return AdminEscuela.objects.filter(
        sede=sede,
        is_active=True,
        user__is_active=True,
        tipo_coordinador=AdminEscuela.TipoCoordinador.SEDE,
    )


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


def _coordinador_sede_profile(user):
    """Perfil de coordinador de sede activo (con sede), o None."""
    p = getattr(user, 'admin_escuela_profile', None)
    if (
        p
        and p.is_active
        and p.sede_id
        and p.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE
    ):
        return p
    return None


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
    estado = (request.GET.get('estado') or "activas").strip().casefold()
    if estado not in ("activas", "inactivas"):
        estado = "activas"
    ver_inactivas = estado == "inactivas"
    hay_filtro = bool(ciudad_filtro or dep_filtro or q)

    todas = list(Sede.objects.all())
    todas.sort(key=_sede_ubicacion_sort_key)
    total_activas = sum(1 for s in todas if s.is_active)
    total_inactivas = len(todas) - total_activas

    # Por defecto solo activas; con ?estado=inactivas solo las desactivadas.
    sedes = [s for s in todas if (not s.is_active) is ver_inactivas]

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

    paginator = Paginator(sedes_filtradas, 8)
    page_obj = paginator.get_page(request.GET.get('page'))

    grupos = OrderedDict()
    for sede in page_obj.object_list:
        label = _sede_ubicacion_label(sede)
        item = {'sede': sede}
        grupos.setdefault(label, []).append(item)

    sedes_por_ubicacion = [{'label': label, 'items': items} for label, items in grupos.items()]

    context = {
        'sedes_por_ubicacion': sedes_por_ubicacion,
        'page_obj': page_obj,
        'filters_query': _querystring_without_page(request),
        'ciudades_disponibles': ciudades_disponibles,
        'hay_filtro': hay_filtro,
        'ciudad_filtro': ciudad_filtro,
        'dep_filtro': dep_filtro,
        'q': q,
        'estado': estado,
        'ver_inactivas': ver_inactivas,
        'total_sedes': len(sedes),
        'total_activas': total_activas,
        'total_inactivas': total_inactivas,
        'total_resultados': len(sedes_filtradas),
    }
    return render(request, 'core/director_dashboard.html', context)


def _querystring_without_page(request):
    q = request.GET.copy()
    q.pop("page", None)
    s = q.urlencode()
    return f"&{s}" if s else ""


@login_required
def director_profesores(request):
    if not (request.user.is_super_admin() or _coordinador_sede_profile(request.user)):
        messages.error(request, 'No tienes permisos para ver esta página.')
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
def director_profesor_ficha_fragment(request, profesor_id):
    """HTML parcial: ficha personal de profesor (solo lectura) para el modal del Director."""
    if not (request.user.is_super_admin() or _coordinador_sede_profile(request.user)):
        return HttpResponse("No autorizado", status=403, content_type="text/plain; charset=utf-8")

    profesor = get_object_or_404(
        Profesor.objects.select_related("user", "sede"),
        pk=profesor_id,
    )
    return render(
        request,
        "core/director_profesor_ficha_fragment.html",
        {"profesor": profesor},
    )


@login_required
def director_coordinador_ficha_fragment(request, sede_id, coordinador_id):
    """HTML parcial: ficha personal de coordinador de equipo (solo lectura)."""
    if not _director_required(request):
        return HttpResponse("No autorizado", status=403, content_type="text/plain; charset=utf-8")

    coordinador = get_object_or_404(
        AdminEscuela.objects.select_related("user", "sede"),
        pk=coordinador_id,
        sede_id=sede_id,
        is_active=True,
        user__is_active=True,
    )
    if coordinador.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE:
        return HttpResponse("No autorizado", status=403, content_type="text/plain; charset=utf-8")

    return render(
        request,
        "core/director_coordinador_ficha_fragment.html",
        {"coordinador": coordinador},
    )


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


def _asignar_coordinador_existente(user_id: int, sede: Sede) -> None:
    """Asigna (o mueve) a un usuario ya registrado como coordinador de sede."""
    user = User.objects.filter(pk=user_id).first()
    if not user:
        return
    cargo = AdminEscuela.cargo_para_tipo(AdminEscuela.TipoCoordinador.SEDE, sede.nombre)
    admin_profile = getattr(user, 'admin_escuela_profile', None)
    if admin_profile is None:
        AdminEscuela.objects.create(
            user=user,
            sede=sede,
            tipo_coordinador=AdminEscuela.TipoCoordinador.SEDE,
            cargo=cargo,
            is_active=True,
        )
    else:
        admin_profile.sede = sede
        admin_profile.tipo_coordinador = AdminEscuela.TipoCoordinador.SEDE
        admin_profile.cargo = cargo
        admin_profile.is_active = True
        admin_profile.save()
    user.role = 'app_admin'
    user.is_staff = True
    user.save(update_fields=['role', 'is_staff'])


@login_required
def buscar_persona_coordinador(request):
    """Busca coordinadores y profesores ya registrados (para asignar como coordinador de una sede nueva)."""
    if not _director_required(request):
        return JsonResponse({'results': []}, status=403)

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'results': []})

    filtro = (
        Q(user__first_name__icontains=q)
        | Q(user__last_name__icontains=q)
        | Q(user__documento_identidad__icontains=q)
    )
    personas = {}
    for p in Profesor.objects.filter(filtro).select_related('user', 'sede')[:10]:
        personas[p.user_id] = {
            'user_id': p.user_id,
            'nombre': p.user.get_full_name() or p.user.email or p.user.username,
            'documento': p.user.documento_identidad or '',
            'rol': 'Profesor',
            'sede': p.sede.nombre if p.sede else '—',
        }
    for c in AdminEscuela.objects.filter(filtro).select_related('user', 'sede')[:10]:
        personas[c.user_id] = {
            'user_id': c.user_id,
            'nombre': c.user.get_full_name() or c.user.email or c.user.username,
            'documento': c.user.documento_identidad or '',
            'rol': c.get_tipo_coordinador_display(),
            'sede': c.sede.nombre if c.sede else '—',
        }
    return JsonResponse({'results': list(personas.values())[:10]})


@login_required
def sede_create(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    hechos_module = AppModule.objects.filter(name='hechos').first()
    coordinador_form = None

    if request.method == 'POST':
        form = SedeForm(request.POST, request.FILES)
        coordinador_modo = (request.POST.get('coordinador_modo') or '').strip()
        coordinador_user_id = (request.POST.get('coordinador_user_id') or '').strip()

        coordinador_valido = True
        if coordinador_modo == 'nuevo':
            coordinador_form = CoordinadorForm(
                request.POST,
                request.FILES,
                allowed_tipos=[AdminEscuela.TipoCoordinador.SEDE],
                prefix='coord',
            )
            coordinador_valido = coordinador_form.is_valid()
        elif coordinador_modo == 'existente':
            coordinador_valido = coordinador_user_id.isdigit()
            if not coordinador_valido:
                messages.error(request, 'Selecciona una persona de la lista o agrega una nueva.')

        if form.is_valid() and coordinador_valido:
            with transaction.atomic():
                sede = form.save()
                if coordinador_modo == 'nuevo' and coordinador_form:
                    coordinador_form.save(User, sede, hechos_module)
                elif coordinador_modo == 'existente' and coordinador_user_id:
                    _asignar_coordinador_existente(int(coordinador_user_id), sede)
            messages.success(request, f'Sede {sede.nombre} creada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm()

    if coordinador_form is None:
        coordinador_form = CoordinadorForm(allowed_tipos=[AdminEscuela.TipoCoordinador.SEDE], prefix='coord')

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
            'coordinador_form': coordinador_form,
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
        if form.is_valid():
            sede = form.save()
            messages.success(request, f'Sede {sede.nombre} actualizada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm(instance=sede)

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
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
            messages.error(request, 'Contraseña incorrecta. La sede no se desactivó.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
        sede.is_active = False
        sede.save(update_fields=['is_active'])
        messages.success(request, f'Sede {sede.nombre} desactivada correctamente.')
        return redirect('core:director_dashboard')
    return redirect('core:director_dashboard')


@login_required
def sede_reactivate(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    if request.method == 'POST':
        sede.is_active = True
        sede.save(update_fields=['is_active'])
        messages.success(request, f'Sede {sede.nombre} reactivada correctamente.')
    return redirect('core:director_sede_detail', sede_id=sede.id)


@login_required
def director_sede_detail(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    coordinadores = list(
        AdminEscuela.objects.filter(
            sede=sede,
            is_active=True,
            user__is_active=True,
        ).select_related('user')
        .prefetch_related('capacidad_asignaciones__capacidad')
        .order_by(
            'user__first_name', 'user__last_name'
        )
    )
    coordinadores_sede = [
        c for c in coordinadores
        if c.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE
    ]
    coordinadores_otros = [
        c for c in coordinadores
        if c.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ]

    context = {
        'sede': sede,
        'coordinadores_sede': coordinadores_sede,
        'coordinadores_otros': coordinadores_otros,
    }
    return render(request, 'core/director_sede_detail.html', context)


@login_required
def coordinador_sede_info(request, sede_id):
    """Panorama de la sede: datos, equipo, escuelas y qué falta por completar."""
    sede = get_object_or_404(Sede, id=sede_id)
    p = _coordinador_sede_profile(request.user)
    if not request.user.is_super_admin() and (not p or p.sede_id != sede.id):
        messages.error(request, 'Solo el coordinador de sede puede ver esta sección.')
        return redirect('core:dashboard')

    coordinadores = list(
        AdminEscuela.objects.filter(sede=sede, is_active=True, user__is_active=True)
        .select_related('user')
        .prefetch_related('capacidad_asignaciones__capacidad')
        .order_by('user__first_name', 'user__last_name')
    )
    coordinador_sede = next(
        (c for c in coordinadores if c.tipo_coordinador == AdminEscuela.TipoCoordinador.SEDE),
        None,
    )
    equipo = [
        c for c in coordinadores
        if c.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ]

    capacidades_cubiertas = set()
    for c in equipo:
        capacidades_cubiertas.update(c.roles_codigos())

    areas = [
        ('academico', 'Académico', 'Estudiantes, matrículas y solicitudes'),
        ('pedagogico', 'Pedagógico', 'Profesores y estructura de escuelas'),
        ('financiero', 'Financiero', 'Recursos, ofrendas y presupuestos'),
        ('logistico', 'Logístico', 'Salones y espacios'),
    ]
    areas_estado = [
        {
            'codigo': codigo,
            'nombre': nombre,
            'detalle': detalle,
            'cubierta': codigo in capacidades_cubiertas,
            'responsables': [
                c for c in equipo if codigo in c.roles_codigos()
            ],
        }
        for codigo, nombre, detalle in areas
    ]

    escuelas = list(
        Escuela.objects.filter(sede=sede, is_active=True)
        .select_related('maestro__user')
        .order_by('-anio', 'ciclo', 'nombre')
    )
    escuelas_sin_maestro = [e for e in escuelas if e.maestro_id is None]
    escuelas_sin_fechas = [e for e in escuelas if not e.fecha_inicio or not e.fecha_fin]
    escuelas_sin_horario = [e for e in escuelas if not (e.horario or '').strip()]

    total_profesores = Profesor.objects.filter(sede=sede, is_active=True).count()
    total_estudiantes = Estudiante.objects.filter(sede=sede, is_active=True).count()
    total_salones = Salon.objects.filter(sede=sede, is_active=True).count()

    # Cada pendiente lleva su acción para que el coordinador sepa qué hacer.
    pendientes = []
    if not (sede.direccion or '').strip():
        pendientes.append({'texto': 'La sede no tiene dirección registrada.', 'accion': None})
    if not (sede.ciudad or '').strip():
        pendientes.append({'texto': 'La sede no tiene ciudad registrada.', 'accion': None})
    if not (sede.telefono or '').strip():
        pendientes.append({'texto': 'Falta el teléfono de contacto.', 'accion': None})
    if not (sede.email or '').strip():
        pendientes.append({'texto': 'Falta el correo de contacto.', 'accion': None})
    if coordinador_sede is None:
        pendientes.append({'texto': 'La sede no tiene coordinador de sede asignado.', 'accion': None})
    for area in areas_estado:
        if not area['cubierta']:
            pendientes.append({
                'texto': f"Sin responsable {area['nombre'].lower()} en el equipo.",
                'accion': reverse('core:coordinador_create', args=[sede.id]),
                'accion_texto': 'Agregar coordinador',
            })
    if not escuelas:
        pendientes.append({'texto': 'La sede todavía no tiene escuelas activas.', 'accion': None})
    if escuelas_sin_maestro:
        pendientes.append({
            'texto': f'{len(escuelas_sin_maestro)} escuela(s) sin maestro asignado.',
            'accion': None,
        })
    if escuelas_sin_fechas:
        pendientes.append({
            'texto': f'{len(escuelas_sin_fechas)} escuela(s) sin fechas de inicio o fin.',
            'accion': None,
        })
    if escuelas_sin_horario:
        pendientes.append({
            'texto': f'{len(escuelas_sin_horario)} escuela(s) sin horario definido.',
            'accion': None,
        })
    if total_salones == 0:
        pendientes.append({'texto': 'No hay salones registrados en la sede.', 'accion': None})
    if total_profesores == 0:
        pendientes.append({'texto': 'La sede no tiene profesores activos.', 'accion': None})

    return render(
        request,
        'core/coordinador_sede_info.html',
        {
            'sede': sede,
            'coordinador_sede': coordinador_sede,
            'equipo': equipo,
            'areas_estado': areas_estado,
            'escuelas': escuelas,
            'total_escuelas': len(escuelas),
            'total_profesores': total_profesores,
            'total_estudiantes': total_estudiantes,
            'total_salones': total_salones,
            'pendientes': pendientes,
        },
    )


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
        .prefetch_related('capacidad_asignaciones__capacidad')
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
                else:
                    n_escuelas = np_obj.escuelas.count()
                    titulo = np_obj.titulo_acordeon()
                    np_obj.delete()
                    if n_escuelas:
                        messages.success(
                            request,
                            f"Nivel «{titulo}» eliminado junto con {n_escuelas} "
                            f"escuela{'s' if n_escuelas != 1 else ''} del catálogo global.",
                        )
                    else:
                        messages.success(request, f"Nivel «{titulo}» eliminado.")
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
        'page_title': (
            'Crear coordinador de sede'
            if request.user.is_super_admin()
            else 'Crear coordinador'
        ),
        'submit_label': (
            'Crear coordinador de sede'
            if request.user.is_super_admin()
            else 'Crear coordinador'
        ),
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

    if (
        request.user.is_super_admin()
        and admin_profile.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE
    ):
        messages.error(
            request,
            'Desde Dirección solo se edita el coordinador de sede. El resto lo gestiona el equipo de la sede.',
        )
        return redirect('core:director_sede_detail', sede_id=sede.id)

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
        'page_title': (
            'Editar coordinador de sede'
            if request.user.is_super_admin()
            else 'Editar coordinador'
        ),
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

    if request.user.is_super_admin():
        if admin_profile.tipo_coordinador != AdminEscuela.TipoCoordinador.SEDE:
            messages.error(
                request,
                'Desde Dirección no se eliminan coordinadores de equipo. Eso lo gestiona el coordinador de sede.',
            )
            return redirect('core:director_sede_detail', sede_id=sede.id)
        if _active_coordinadores_sede_qs(sede).count() <= 1:
            messages.error(
                request,
                'La sede no puede quedar sin un coordinador de sede.',
            )
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
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
    inp = "profile-field w-full pr-10"
    for name, auto in (
        ("old_password", "current-password"),
        ("new_password1", "new-password"),
        ("new_password2", "new-password"),
    ):
        if name in form.fields:
            form.fields[name].widget.attrs.update({"class": inp, "autocomplete": auto})
            form.fields[name].widget.attrs.pop("autofocus", None)
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

    password_form = _password_change_form_styled(request.user)

    if request.method == 'POST':
        if request.POST.get("profile_password"):
            password_form = _password_change_form_styled(request.user, data=request.POST)
            if password_form.is_valid():
                u = password_form.save()
                update_session_auth_hash(request, u)
                messages.success(request, "Contraseña actualizada correctamente.")
                return redirect("core:profile")
        elif request.POST.get("profile_account") or request.POST.get("profile_contact"):
            # Correo puede venir solo (legacy profile_account) o junto con contacto.
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
                    return redirect("core:profile")
                request.user.email = email_raw
            else:
                request.user.email = None

            update_fields = ["email", "updated_at"]
            if request.POST.get("profile_contact"):
                phone_raw = (request.POST.get("phone") or "").strip()
                phone_digits = "".join(c for c in phone_raw if c.isdigit())[:15] or None
                direccion = (request.POST.get("direccion") or "").strip()
                barrio = (request.POST.get("barrio") or "").strip()
                departamento = (request.POST.get("departamento") or "").strip()
                ciudad = (request.POST.get("ciudad") or "").strip()
                if departamento and ciudad:
                    permitidas = {
                        c for c, _ in ciudad_choices_for_departamento(departamento)
                    }
                    if ciudad not in permitidas:
                        messages.error(
                            request,
                            "Elige un municipio válido para el departamento seleccionado.",
                        )
                        return redirect("core:profile")
                request.user.phone = phone_digits
                request.user.direccion = direccion
                request.user.barrio = barrio
                request.user.departamento = departamento
                request.user.ciudad = ciudad
                update_fields.extend(
                    ["phone", "direccion", "barrio", "departamento", "ciudad"]
                )
                if estudiante_profile:
                    estudiante_profile.direccion = direccion
                    estudiante_profile.save(update_fields=["direccion", "updated_at"])

            try:
                request.user.save(update_fields=update_fields)
            except IntegrityError:
                messages.error(
                    request,
                    "No se pudo guardar el correo (duplicado u otro error).",
                )
                return redirect("core:profile")

            if request.POST.get("profile_contact"):
                messages.success(request, "Datos de contacto actualizados.")
            elif email_raw:
                messages.success(request, "Correo actualizado.")
            else:
                messages.success(request, "Correo quitado. Puedes añadir uno nuevo cuando quieras.")
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

    dep_id = (request.user.departamento or "").strip()
    dept_choices = [("", "Seleccione departamento")] + departamento_choices()
    if dep_id:
        city_choices = [("", "Seleccione ciudad o municipio")] + ciudad_choices_for_departamento(
            dep_id
        )
    else:
        city_choices = [("", "Primero seleccione departamento")]

    context = {
        "estudiante_profile": estudiante_profile,
        "profesor_profile": profesor_profile,
        "admin_escuela_profile": admin_escuela_profile,
        "direccion_perfil": direccion_perfil,
        "barrio_perfil": (request.user.barrio or "").strip(),
        "departamento_perfil": dep_id,
        "ciudad_perfil": (request.user.ciudad or "").strip(),
        "departamento_choices": dept_choices,
        "ciudad_choices": city_choices,
        "password_form": password_form,
    }

    return render(request, "core/profile_modern.html", context)


@login_required
def mis_notificaciones(request):
    """Listado de notificaciones del estudiante (página propia)."""
    estudiante_profile = None
    try:
        estudiante_profile = request.user.estudiante_profile
    except Exception:
        pass
    if estudiante_profile is None:
        messages.info(request, "Las notificaciones están disponibles para cuentas de estudiante.")
        return redirect("core:profile")

    qs = NotificacionEstudiante.objects.filter(estudiante=estudiante_profile).order_by(
        "-created_at"
    )
    no_leidas = qs.filter(leida=False).count()
    if no_leidas:
        qs.filter(leida=False).update(leida=True)

    return render(
        request,
        "core/mis_notificaciones.html",
        {
            "notificaciones": list(qs[:50]),
            "no_leidas_marcadas": no_leidas,
        },
    )


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


def signup_check_documento(request):
    """
    Consulta pública (signup): ¿este documento ya tiene cuenta?
    No revela datos personales; solo exists=true/false.
    """
    from django import forms as djforms

    from core.forms import (
        MSG_DOCUMENTO_YA_EXISTE,
        _normalize_and_validate_documento_plausible,
        documento_ya_registrado,
    )

    raw = (request.GET.get("doc") or "").strip()
    tipo = (request.GET.get("tipo") or Estudiante.TipoDocumento.CC).strip()
    if not raw:
        return JsonResponse({"exists": False, "ok": False})
    try:
        normalized = _normalize_and_validate_documento_plausible(raw, tipo)
    except djforms.ValidationError:
        # Documento incompleto o con formato inválido: no marcar como existente.
        return JsonResponse({"exists": False, "ok": False})

    exists = documento_ya_registrado(normalized)
    payload = {"exists": exists, "ok": True, "doc": normalized}
    if exists:
        payload["message"] = MSG_DOCUMENTO_YA_EXISTE
        payload["login_url"] = reverse("account_login")
    return JsonResponse(payload)
