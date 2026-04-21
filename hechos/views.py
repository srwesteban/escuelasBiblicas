from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import os

from django.http import FileResponse, Http404, JsonResponse, HttpResponse
from django.db.models import Q, Count, Avg, Exists, OuterRef, Sum
from django.db import IntegrityError
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from .models import (
    Estudiante, Profesor, AdminEscuela, Escuela, RutaEstudio, Curso,
    Matricula, Clase, Asistencia, Nota, EdicionCurso, SolicitudMatricula, NotificacionEstudiante,
    SolicitudEspecialEstudiante, EdicionCursoHorario, QuejaReclamo, Ofrenda, PresupuestoEvento,
    RecaudoOcasional, Salon, ActividadEscuela, EntregaActividad, ArchivoRecursoEscuela,
)
from .utils import (
    get_current_period,
    get_period_from_date,
    get_period_display,
    get_period_stats,
    sesiones_agrupadas_por_mes,
)
from core.models import Sede, generate_unique_username
from hechos import coordinador_access as ca
from .profesor_entregas import entregas_pendientes_calificacion_qs
from .forms import (
    ActividadEscuelaForm,
    ArchivoRecursoEscuelaForm,
    EntregaActividadTextoForm,
    entrega_evidencia_archivo_validator,
    normalizar_archivo_entrega,
    PresupuestoEventoForm,
    ProfesorEvaluaEntregaForm,
    QuejaReclamoForm,
    RecaudoOcasionalForm,
    SalonForm,
    ingresos_totales_sede,
)

from collections import defaultdict
from datetime import datetime, timedelta, date, time as dt_time
from decimal import Decimal
from urllib.parse import quote
from django.utils.text import slugify

User = get_user_model()


def _whatsapp_me_url(phone_raw):
    """Devuelve URL base https://wa.me/... o None si no hay número válido."""
    if not phone_raw:
        return None
    digits = "".join(c for c in str(phone_raw) if c.isdigit())
    if not digits:
        return None
    if len(digits) == 10:
        digits = "57" + digits
    return f"https://wa.me/{digits}"


def get_user_sede(user):
    """
    Obtiene la sede del usuario basada en su perfil
    """
    if hasattr(user, 'estudiante_profile') and user.estudiante_profile.sede:
        return user.estudiante_profile.sede
    elif hasattr(user, 'profesor_profile') and user.profesor_profile.sede:
        return user.profesor_profile.sede
    elif hasattr(user, 'admin_escuela_profile') and user.admin_escuela_profile.sede:
        return user.admin_escuela_profile.sede
    elif user.sede:
        return user.sede
    return None


def _redirect_coordinador_logistica(*, tab='salones', escuela_id=None):
    base = reverse('hechos:coordinador_logistica')
    q = [f'tab={tab}']
    if escuela_id is not None:
        q.append(f'escuela={int(escuela_id)}')
    return redirect(f'{base}?{"&".join(q)}')


@login_required
def hechos_dashboard(request):
    """
    Punto de entrada legado de /hechos/dashboard/: redirige según el rol.
    El registro de ofrendas vive en la app ``ofrendas`` (/ofrendas/).
    """
    redir = ca.redirect_operational_home_if_restricted(request)
    if redir:
        return redir

    if (
        hasattr(request.user, 'admin_escuela_profile')
        and ca.has_capacidad(request.user, 'pedagogico')
    ):
        return redirect('hechos:profesores_list')

    if (
        not hasattr(request.user, 'estudiante_profile')
        and not hasattr(request.user, 'profesor_profile')
        and not hasattr(request.user, 'admin_escuela_profile')
    ):
        messages.warning(request, 'No tienes acceso al módulo Hechos.')
        return redirect('core:dashboard')

    user_sede = get_user_sede(request.user)
    if not user_sede and hasattr(request.user, 'estudiante_profile'):
        return redirect('hechos:seleccionar_sede_estudiante')
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    if hasattr(request.user, 'estudiante_profile'):
        return redirect('hechos:escuelas_disponibles')
    if hasattr(request.user, 'profesor_profile'):
        return redirect('hechos:mis_escuelas_profesor')
    if hasattr(request.user, 'admin_escuela_profile'):
        if ca.has_capacidad(request.user, 'academico'):
            return redirect('hechos:estudiantes_list')
    return redirect('core:dashboard')


@login_required
def seleccionar_sede_estudiante(request):
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden seleccionar sede.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    sedes_qs = Sede.objects.filter(is_active=True).order_by('ciudad', 'nombre')
    next_url = request.GET.get('next') or request.POST.get('next') or ''

    if request.method == 'POST':
        sede_id = request.POST.get('sede_id')
        sede = get_object_or_404(sedes_qs, id=sede_id)
        estudiante.sede = sede
        estudiante.save(update_fields=['sede'])
        if request.user.sede_id != sede.id:
            request.user.sede = sede
            request.user.save(update_fields=['sede'])
        messages.success(request, f'Sede asignada: {sede.titulo_con_ciudad()}.')

        if next_url and next_url.startswith('/'):
            return redirect(next_url)
        return redirect('hechos:escuelas_disponibles')

    sedes_con_ciudad = (
        Sede.objects.filter(is_active=True)
        .exclude(ciudad__exact='')
        .order_by('ciudad', 'nombre')
    )
    por_ciudad = {}
    for s in sedes_con_ciudad:
        c = (s.ciudad or '').strip()
        if not c:
            continue
        por_ciudad.setdefault(c, []).append(
            {'id': s.id, 'label': s.titulo_con_ciudad()}
        )
    ciudades = sorted(por_ciudad.keys(), key=str.casefold)

    sedes_sin_ciudad = [
        {'id': s.id, 'label': s.nombre}
        for s in Sede.objects.filter(is_active=True)
        .filter(Q(ciudad='') | Q(ciudad__isnull=True))
        .order_by('nombre')
    ]

    sede_actual = estudiante.sede if estudiante.sede_id else None
    ciudad_inicial = ''
    usar_bucket_otras = False
    if sede_actual:
        c0 = (sede_actual.ciudad or '').strip()
        if c0:
            ciudad_inicial = c0
        elif sedes_sin_ciudad:
            usar_bucket_otras = True

    return render(
        request,
        'hechos/seleccionar_sede_estudiante.html',
        {
            'sedes_todas': sedes_qs,
            'por_ciudad': por_ciudad,
            'sedes_sin_ciudad_data': sedes_sin_ciudad,
            'ciudades': ciudades,
            'tiene_cascada_ciudad': bool(ciudades),
            'sede_actual_id': estudiante.sede_id or request.user.sede_id,
            'sede_actual': sede_actual,
            'ciudad_inicial': ciudad_inicial,
            'usar_bucket_otras': usar_bucket_otras,
            'is_change': bool(estudiante.sede_id),
            'next_url': next_url,
        },
    )


@login_required
def estudiantes_list(request):
    """
    Lista de estudiantes (para admins y profesores)
    """
    allowed = (
        request.user.is_super_admin()
        or hasattr(request.user, 'profesor_profile')
        or (
            hasattr(request.user, 'admin_escuela_profile')
            and ca.has_capacidad(request.user, 'academico')
        )
    )
    if not allowed:
        messages.error(request, 'No tienes permisos para ver esta página.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    # Filtrar estudiantes según el perfil del usuario
    if hasattr(request.user, 'profesor_profile'):
        # Profesor ve solo estudiantes de sus cursos
        estudiantes = Estudiante.objects.filter(
            matriculas__edicion_curso__profesor=request.user.profesor_profile,
            matriculas__sede=user_sede,
            matriculas__is_active=True,
            sede=user_sede,
            is_active=True
        ).distinct().select_related('user').prefetch_related('matriculas')
    else:
        # Admin ve todos los estudiantes
        estudiantes = Estudiante.objects.filter(sede=user_sede, is_active=True).select_related('user').prefetch_related('matriculas')

    busqueda = (request.GET.get('busqueda') or '').strip()
    filtro_estado = (request.GET.get('estado') or '').strip()
    if busqueda:
        estudiantes = estudiantes.filter(
            Q(user__first_name__icontains=busqueda)
            | Q(user__last_name__icontains=busqueda)
            | Q(user__email__icontains=busqueda)
            | Q(codigo_estudiante__icontains=busqueda)
            | Q(iglesia__icontains=busqueda)
        ).distinct()
    if filtro_estado == 'matriculados':
        estudiantes = estudiantes.filter(
            matriculas__is_active=True,
            matriculas__sede=user_sede,
        ).distinct()
    elif filtro_estado == 'no_matriculados':
        matricula_activa = Matricula.objects.filter(
            estudiante_id=OuterRef('pk'),
            is_active=True,
            sede=user_sede,
        )
        estudiantes = estudiantes.filter(~Exists(matricula_activa))

    # Estadísticas
    estudiantes_activos = estudiantes.filter(is_active=True)
    estudiantes_matriculados = estudiantes.filter(
        matriculas__is_active=True
    ).distinct()
    
    # Calcular promedio general
    from django.db.models import Avg
    promedio_general = estudiantes.aggregate(
        promedio=Avg('notas__puntaje_obtenido')
    )['promedio'] or 0
    
    # Calcular estadísticas por estudiante
    estudiantes_con_estadisticas = []
    for estudiante in estudiantes:
        matriculas_activas = estudiante.matriculas.filter(is_active=True).count()
        total_matriculas = estudiante.matriculas.count()
        estudiantes_con_estadisticas.append({
            'estudiante': estudiante,
            'matriculas_activas': matriculas_activas,
            'total_matriculas': total_matriculas
        })
    
    context = {
        'estudiantes_con_estadisticas': estudiantes_con_estadisticas,
        'estudiantes_activos': estudiantes_activos,
        'estudiantes_matriculados': estudiantes_matriculados,
        'promedio_general': round(promedio_general, 1),
        'user_sede': user_sede,
        'busqueda': busqueda,
        'filtro_estado': filtro_estado,
    }
    
    return render(request, 'hechos/estudiantes_list_modern.html', context)


@login_required
def profesores_list(request):
    """
    Lista de profesores (director o coordinador pedagógico)
    """
    allowed = (
        request.user.is_super_admin()
        or (
            hasattr(request.user, 'admin_escuela_profile')
            and ca.has_capacidad(request.user, 'pedagogico')
        )
    )
    if not allowed:
        messages.error(request, 'No tienes permisos para ver esta página.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    base_qs = Profesor.objects.filter(sede=user_sede, is_active=True)
    experiencia_promedio = base_qs.aggregate(avg=Avg('experiencia_anos'))['avg'] or 0
    edicion_asignada = EdicionCurso.objects.filter(
        profesor_id=OuterRef('pk'),
        is_active=True,
        curso__sede=user_sede,
        curso__is_active=True,
    )
    profesores_con_asignacion = (
        base_qs.annotate(_tiene_edicion=Exists(edicion_asignada)).filter(_tiene_edicion=True).count()
    )
    total_ediciones_en_sede = EdicionCurso.objects.filter(
        curso__sede=user_sede,
        is_active=True,
        curso__is_active=True,
        profesor__isnull=False,
    ).count()

    profesores = (
        base_qs.select_related('user')
        .annotate(
            num_ediciones_activas=Count(
                'ediciones_curso',
                filter=Q(
                    ediciones_curso__is_active=True,
                    ediciones_curso__curso__is_active=True,
                    ediciones_curso__curso__sede=user_sede,
                ),
            )
        )
        .order_by('user__first_name', 'user__last_name')
    )

    es_pedagogico = ca.has_capacidad(request.user, 'pedagogico')

    context = {
        'profesores': profesores,
        'user_sede': user_sede,
        'total_profesores': base_qs.count(),
        'profesores_con_asignacion': profesores_con_asignacion,
        'profesores_sin_asignacion': max(0, base_qs.count() - profesores_con_asignacion),
        'total_ediciones_en_sede': total_ediciones_en_sede,
        'experiencia_promedio': round(float(experiencia_promedio), 1),
        'es_coordinador_pedagogico': bool(es_pedagogico and not request.user.is_super_admin()),
    }
    
    return render(request, 'hechos/profesores_list_modern.html', context)


def _dias_horarios_to_string(rows):
    """
    rows: iterable de (dia_semana:int, hora:datetime.time)
    """
    by_day = {d: h for d, h in rows}
    ordered_days = [d for d in range(0, 7) if d in by_day]
    day_labels = {
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo",
    }
    parts = []
    for d in ordered_days:
        h = by_day[d]
        parts.append(f"{day_labels.get(d, str(d))} {h.strftime('%I:%M %p').lstrip('0')}")
    return " · ".join(parts)


def _calcular_fechas_clase(fecha_inicio, fecha_fin, dias):
    """
    dias: set[int] (0=Lunes .. 6=Domingo) usando weekday() estándar.
    """
    if not fecha_inicio or not fecha_fin or not dias:
        return []
    if fecha_fin < fecha_inicio:
        return []
    fechas = []
    d = fecha_inicio
    while d <= fecha_fin:
        if d.weekday() in dias:
            fechas.append(d)
        d += timedelta(days=1)
    return fechas


def _crear_clases_si_vacias_desde_estructura(edicion, sede, profesor_para_clase):
    """
    Si la edición ya tiene días/horarios guardados y aún no hay sesiones (Clase),
    genera una fila por cada fecha entre fecha_inicio y fecha_fin que coincida
    con esos días (misma lógica que el resumen del asistente).
    """
    if Clase.objects.filter(edicion_curso=edicion, is_active=True).exists():
        return 0
    horarios = list(
        EdicionCursoHorario.objects.filter(edicion=edicion).order_by("dia_semana", "hora")
    )
    if not horarios:
        return 0
    by_weekday = {h.dia_semana: h.hora for h in horarios}
    dias_set = set(by_weekday.keys())
    fechas = _calcular_fechas_clase(edicion.fecha_inicio, edicion.fecha_fin, dias_set)
    if not fechas:
        return 0
    tz = timezone.get_current_timezone()
    to_create = []
    n = 0
    for d in sorted(fechas):
        hh = by_weekday.get(d.weekday())
        if hh is None:
            continue
        n += 1
        naive = datetime.combine(d, hh)
        aware = timezone.make_aware(naive, tz)
        to_create.append(
            Clase(
                sede=sede,
                edicion_curso=edicion,
                numero_clase=n,
                titulo=f"Sesión {n}",
                descripcion="",
                fecha_clase=aware,
                duracion_minutos=90,
                profesor=profesor_para_clase,
                aula="",
                is_active=True,
            )
        )
    if not to_create:
        return 0
    Clase.objects.bulk_create(to_create)
    return len(to_create)


def _profesor_puede_gestionar_clase(clase, profesor):
    """Titular de la sesión, profesor de la edición o maestro de la escuela."""
    if clase.profesor_id and clase.profesor_id == profesor.id:
        return True
    if clase.edicion_curso_id and clase.edicion_curso.profesor_id == profesor.id:
        return True
    esc = None
    try:
        esc = clase.curso.ruta_estudio.escuela
    except Exception:
        return False
    return bool(esc and esc.maestro_id == profesor.id)


def _estructura_wizard_session_key(edicion_id: int) -> str:
    return f"estructura_wiz_{edicion_id}"


def _parse_iso_date(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _time_from_12h(hour_12: int, minute: int, ampm: str) -> dt_time:
    ampm = (ampm or "").strip().upper()
    if hour_12 < 1 or hour_12 > 12 or minute < 0 or minute > 59:
        raise ValueError("Hora fuera de rango")
    if ampm not in ("AM", "PM"):
        raise ValueError("Indica AM o PM")
    if hour_12 == 12:
        h24 = 0 if ampm == "AM" else 12
    else:
        h24 = hour_12 if ampm == "AM" else hour_12 + 12
    return dt_time(hour=h24, minute=minute)


def _time_to_display_12h(t: dt_time) -> str:
    h = t.hour % 12
    if h == 0:
        h = 12
    suf = "a. m." if t.hour < 12 else "p. m."
    return f"{h}:{t.minute:02d} {suf}"


def _parse_session_time(s: str) -> dt_time:
    parts = (s or "").strip().split(":")
    hh = int(parts[0])
    mm = int(parts[1]) if len(parts) > 1 else 0
    return dt_time(hour=hh, minute=mm)


def _time_to_sel_parts(tt: dt_time):
    h12 = tt.hour % 12
    if h12 == 0:
        h12 = 12
    return h12, tt.minute, "AM" if tt.hour < 12 else "PM"


def _minutos_opts_for(sel_mm: int):
    base = [0, 15, 30, 45]
    if sel_mm not in base:
        return sorted(set(base + [sel_mm]))
    return base


def _build_dias_horario_rows_paso2(dias, day_labels, horas_por_dia, legacy_hora, existing_by_day):
    """
    Una fila por día con selectores 12h. horas_por_dia: dict str(día)->'HH:MM:SS'.
    """
    rows = []
    for d in sorted(dias):
        label = day_labels[d]
        tt = None
        if horas_por_dia and str(d) in horas_por_dia:
            try:
                tt = _parse_session_time(horas_por_dia[str(d)])
            except (ValueError, TypeError, IndexError):
                tt = None
        if tt is None and legacy_hora:
            try:
                tt = _parse_session_time(legacy_hora)
            except (ValueError, TypeError, IndexError):
                tt = None
        if tt is None and d in existing_by_day:
            tt = existing_by_day[d]
        if tt is None:
            tt = dt_time(19, 0)
        h12, mm, ampm = _time_to_sel_parts(tt)
        rows.append(
            {
                "dia_int": d,
                "label": label,
                "sel_h12": h12,
                "sel_mm": mm,
                "sel_ampm": ampm,
                "minutos_opts": _minutos_opts_for(mm),
            }
        )
    return rows


@login_required
def estructura_ediciones(request):
    """
    Coordinador pedagógico: escuelas de la sede; cada una se configura con el asistente (por edición).
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, "No tienes una sede asignada. Contacta al administrador.")
        return redirect("core:dashboard")

    escuelas = Escuela.objects.filter(sede=user_sede, is_active=True).order_by(
        "nombre", "-anio", "ciclo", "grupo"
    )

    escuelas_feed = []
    for escuela in escuelas:
        n_ed = EdicionCurso.objects.filter(
            curso__ruta_estudio__escuela=escuela,
            curso__sede=user_sede,
            is_active=True,
            curso__is_active=True,
        ).count()
        escuelas_feed.append(
            {
                "escuela": escuela,
                "num_ediciones": n_ed,
            }
        )

    return render(
        request,
        "hechos/estructura_escuelas_list.html",
        {"user_sede": user_sede, "escuelas_feed": escuelas_feed},
    )


@login_required
def estructura_escuela_portal(request, escuela_id):
    """
    Si la escuela tiene una sola edición activa, entra directo al asistente; si varias, elige cuál configurar.
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, "No tienes una sede asignada. Contacta al administrador.")
        return redirect("core:dashboard")

    escuela = get_object_or_404(Escuela, id=escuela_id, sede=user_sede, is_active=True)

    ediciones = (
        EdicionCurso.objects.filter(
            curso__ruta_estudio__escuela=escuela,
            curso__sede=user_sede,
            is_active=True,
            curso__is_active=True,
        )
        .select_related("curso")
        .annotate(nh=models.Count("estructura_horarios"))
        .order_by("curso__nombre", "nombre_edicion")
    )

    if not ediciones.exists():
        messages.warning(
            request,
            "Esta escuela aún no tiene ediciones activas. Crea ediciones antes de configurar días y horario.",
        )
        return redirect("hechos:estructura_ediciones")

    if ediciones.count() == 1:
        ed = ediciones.first()
        return redirect("hechos:estructura_configurar", edicion_id=ed.id, step=1)

    ediciones_feed = []
    for ed in ediciones:
        horarios = list(
            EdicionCursoHorario.objects.filter(edicion=ed).order_by("dia_semana", "hora")
        )
        rows = [(h.dia_semana, h.hora) for h in horarios]
        ediciones_feed.append(
            {
                "edicion": ed,
                "listo": ed.nh > 0,
                "estructura_str": _dias_horarios_to_string(rows) if rows else "Sin estructura",
            }
        )

    return render(
        request,
        "hechos/estructura_escuela_portal.html",
        {
            "user_sede": user_sede,
            "escuela": escuela,
            "ediciones_feed": ediciones_feed,
        },
    )


@login_required
def estructura_configurar_paso(request, edicion_id, step):
    """
    Asistente: 1) fechas + ciclo + grupo → 2) días → 3) horario → 4) profesor → 5) resumen y guardar.
    """
    if step not in (1, 2, 3, 4, 5):
        raise Http404

    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, "No tienes una sede asignada. Contacta al administrador.")
        return redirect("core:dashboard")

    edicion = get_object_or_404(
        EdicionCurso.objects.select_related("curso__ruta_estudio__escuela"),
        id=edicion_id,
        curso__sede=user_sede,
        curso__is_active=True,
        is_active=True,
    )

    escuela = edicion.curso.escuela
    if escuela is None:
        messages.error(
            request,
            "Esta edición no está vinculada a una escuela; no se puede usar el asistente de estructura.",
        )
        return redirect("hechos:estructura_ediciones")

    sk = _estructura_wizard_session_key(edicion_id)
    data = dict(request.session.get(sk, {}))

    day_labels = {int(k): v for k, v in EdicionCursoHorario.DiaSemana.choices}
    total_steps = 5

    wizard_ctx = {
        "user_sede": user_sede,
        "edicion": edicion,
        "escuela": escuela,
        "total_steps": total_steps,
    }

    if step == 1:
        if request.method == "POST":
            fi = _parse_iso_date(request.POST.get("fecha_inicio"))
            ff = _parse_iso_date(request.POST.get("fecha_fin"))
            ciclo = (request.POST.get("ciclo") or "").strip().upper()
            try:
                grupo = int(request.POST.get("grupo") or 0)
            except (TypeError, ValueError):
                grupo = 0

            errores = []
            if not fi:
                errores.append("Indica la fecha de inicio del ciclo.")
            if not ff:
                errores.append("Indica la fecha de fin del ciclo.")
            if fi and ff and ff < fi:
                errores.append("La fecha de fin debe ser igual o posterior a la de inicio.")
            if ciclo not in ("A", "B"):
                errores.append("Elige ciclo A o B.")
            if grupo < 1:
                errores.append("El número de grupo debe ser 1 o mayor.")

            anio_ref = fi.year if fi else None
            if not errores and anio_ref is not None:
                dup = Escuela.objects.filter(
                    sede=escuela.sede,
                    nombre__iexact=(escuela.nombre or "").strip(),
                    anio=anio_ref,
                    ciclo=ciclo,
                    grupo=grupo,
                    is_active=True,
                ).exclude(pk=escuela.pk)
                if dup.exists():
                    errores.append(
                        "Ya existe otra escuela en esta sede con el mismo nombre, año, ciclo y grupo. "
                        "Ajusta ciclo, grupo o el nombre de la escuela desde coordinación."
                    )

            if errores:
                for e in errores:
                    messages.error(request, e)
                return render(
                    request,
                    "hechos/estructura_wizard_paso1.html",
                    {
                        **wizard_ctx,
                        "step": 1,
                        "w_fecha_inicio": request.POST.get("fecha_inicio") or "",
                        "w_fecha_fin": request.POST.get("fecha_fin") or "",
                        "w_ciclo": ciclo if ciclo in ("A", "B") else "A",
                        "w_grupo": grupo if grupo >= 1 else 1,
                    },
                )

            escuela.anio = anio_ref
            escuela.ciclo = ciclo
            escuela.grupo = grupo
            escuela.save(update_fields=["anio", "ciclo", "grupo", "updated_at"])
            edicion.fecha_inicio = fi
            edicion.fecha_fin = ff
            edicion.save(update_fields=["fecha_inicio", "fecha_fin", "updated_at"])
            messages.success(request, "Período y ciclo guardados. Sigue con los días de clase.")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=2)

        return render(
            request,
            "hechos/estructura_wizard_paso1.html",
            {
                **wizard_ctx,
                "step": 1,
                "w_fecha_inicio": edicion.fecha_inicio.strftime("%Y-%m-%d"),
                "w_fecha_fin": edicion.fecha_fin.strftime("%Y-%m-%d"),
                "w_ciclo": escuela.ciclo,
                "w_grupo": escuela.grupo,
            },
        )

    if step == 2:
        existing_days = sorted(
            EdicionCursoHorario.objects.filter(edicion=edicion).values_list(
                "dia_semana", flat=True
            )
        )
        checked_vals = existing_days
        if request.method == "POST":
            dias_sel = []
            for val, _lbl in EdicionCursoHorario.DiaSemana.choices:
                if request.POST.get(f"dia_{val}") == "on":
                    dias_sel.append(int(val))
            dias_sel = sorted(set(dias_sel))
            if not dias_sel:
                messages.error(request, "Selecciona al menos un día en que se darán clases.")
                checked_vals = []
            else:
                request.session[sk] = {"dias": dias_sel}
                request.session.modified = True
                return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=3)
        elif "dias" in data:
            checked_vals = data["dias"]
        day_checks = []
        for val, label in EdicionCursoHorario.DiaSemana.choices:
            day_checks.append(
                {"value": val, "label": label, "checked": int(val) in checked_vals}
            )
        return render(
            request,
            "hechos/estructura_wizard_paso2.html",
            {
                **wizard_ctx,
                "step": 2,
                "day_checks": day_checks,
            },
        )

    if step == 3:
        dias = data.get("dias")
        if not dias:
            messages.warning(request, "Primero elige los días en que se darán clases.")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=2)

        dias_sorted = sorted(dias)
        horas_por_dia = data.get("horas_por_dia") or {}
        legacy_hora = data.get("hora")
        existing_by_day = {
            h.dia_semana: h.hora
            for h in EdicionCursoHorario.objects.filter(edicion=edicion)
        }

        if request.method == "POST":
            nuevas = {}
            errores = []
            for d in dias_sorted:
                try:
                    h12 = int(request.POST.get(f"hora_12_{d}") or 0)
                    mm = int(request.POST.get(f"minuto_{d}") or 0)
                    ampm = request.POST.get(f"ampm_{d}") or ""
                    tt = _time_from_12h(h12, mm, ampm)
                    nuevas[str(d)] = tt.strftime("%H:%M:%S")
                except (ValueError, TypeError):
                    errores.append(
                        f"Horario inválido para {day_labels.get(d, d)} (usa 12 h con a. m. / p. m.)."
                    )
            if errores:
                for e in errores:
                    messages.error(request, e)
                dias_rows = []
                for d in dias_sorted:
                    try:
                        h12 = int(request.POST.get(f"hora_12_{d}") or 7)
                    except (TypeError, ValueError):
                        h12 = 7
                    try:
                        mm = int(request.POST.get(f"minuto_{d}") or 0)
                    except (TypeError, ValueError):
                        mm = 0
                    ampm = (request.POST.get(f"ampm_{d}") or "PM").strip().upper()
                    if ampm not in ("AM", "PM"):
                        ampm = "PM"
                    if mm < 0 or mm > 59:
                        mm = 0
                    if h12 < 1 or h12 > 12:
                        h12 = 7
                    dias_rows.append(
                        {
                            "dia_int": d,
                            "label": day_labels[d],
                            "sel_h12": h12,
                            "sel_mm": mm,
                            "sel_ampm": ampm,
                            "minutos_opts": _minutos_opts_for(mm),
                        }
                    )
                return render(
                    request,
                    "hechos/estructura_wizard_paso3.html",
                    {
                        **wizard_ctx,
                        "step": 3,
                        "dias_rows": dias_rows,
                        "horas_12": list(range(1, 13)),
                    },
                )
            data["horas_por_dia"] = nuevas
            data.pop("hora", None)
            request.session[sk] = data
            request.session.modified = True
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=4)

        dias_rows = _build_dias_horario_rows_paso2(
            dias, day_labels, horas_por_dia, legacy_hora, existing_by_day
        )
        return render(
            request,
            "hechos/estructura_wizard_paso3.html",
            {
                **wizard_ctx,
                "step": 3,
                "dias_rows": dias_rows,
                "horas_12": list(range(1, 13)),
            },
        )

    if step in (4, 5):
        dias = data.get("dias")
        horas_por_dia = dict(data.get("horas_por_dia") or {})
        legacy_hora = data.get("hora")
        if not dias:
            messages.warning(request, "Completa los pasos anteriores (días de clase).")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=2)

        dias_sorted = sorted(dias)
        if legacy_hora and not horas_por_dia:
            for d in dias_sorted:
                horas_por_dia[str(d)] = legacy_hora

        if any(str(d) not in horas_por_dia for d in dias_sorted):
            messages.warning(request, "Define el horario de cada día en el paso anterior.")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=3)

        horas_parseadas = []
        resumen_filas = []
        try:
            for d in dias_sorted:
                tt = _parse_session_time(horas_por_dia[str(d)])
                horas_parseadas.append((d, tt))
                resumen_filas.append(
                    {"dia": day_labels[d], "hora_txt": _time_to_display_12h(tt)}
                )
        except (ValueError, TypeError, IndexError):
            messages.error(request, "Sesión de configuración inválida. Vuelve al paso 3.")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=3)

        fechas = _calcular_fechas_clase(edicion.fecha_inicio, edicion.fecha_fin, set(dias_sorted))
        dias_seleccionados = [day_labels[d] for d in dias_sorted]

        profesores = Profesor.objects.filter(sede=user_sede, is_active=True).select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "id")

        if step == 4:
            if "profesor_wizard_id" in data:
                selected_profesor_id = data["profesor_wizard_id"]
            else:
                selected_profesor_id = edicion.profesor_id

            if request.method == "POST":
                raw = (request.POST.get("profesor_id") or "").strip()
                if not raw:
                    data["profesor_wizard_id"] = None
                else:
                    try:
                        pid = int(raw)
                    except ValueError:
                        messages.error(request, "Selección de profesor inválida.")
                        return render(
                            request,
                            "hechos/estructura_wizard_paso4.html",
                            {
                                **wizard_ctx,
                                "step": 4,
                                "profesores": profesores,
                                "selected_profesor_id": None,
                            },
                        )
                    prof_ok = Profesor.objects.filter(
                        id=pid, sede=user_sede, is_active=True
                    ).first()
                    if not prof_ok:
                        messages.error(
                            request,
                            "El profesor elegido no pertenece a tu sede o no está activo.",
                        )
                        return render(
                            request,
                            "hechos/estructura_wizard_paso4.html",
                            {
                                **wizard_ctx,
                                "step": 4,
                                "profesores": profesores,
                                "selected_profesor_id": pid,
                            },
                        )
                    data["profesor_wizard_id"] = pid
                request.session[sk] = data
                request.session.modified = True
                return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=5)

            return render(
                request,
                "hechos/estructura_wizard_paso4.html",
                {
                    **wizard_ctx,
                    "step": 4,
                    "profesores": profesores,
                    "selected_profesor_id": selected_profesor_id,
                },
            )

        if "profesor_wizard_id" not in data:
            messages.warning(request, "Antes elige al profesor en el paso anterior.")
            return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=4)

        pid_final = data["profesor_wizard_id"]
        prof = None
        if pid_final is not None:
            prof = Profesor.objects.filter(
                id=pid_final, sede=user_sede, is_active=True
            ).select_related("user").first()
            if not prof:
                messages.error(request, "El profesor guardado en la sesión ya no es válido. Vuelve a elegirlo.")
                return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=4)

        if prof:
            profesor_resumen = {
                "nombre": prof.user.get_full_name() or prof.user.username,
                "codigo": prof.codigo_profesor or "",
            }
        else:
            profesor_resumen = {"nombre": "Sin asignar", "codigo": ""}

        if request.method == "POST":
            EdicionCursoHorario.objects.filter(edicion=edicion).delete()
            for d, tt in horas_parseadas:
                EdicionCursoHorario.objects.create(edicion=edicion, dia_semana=d, hora=tt)
            edicion.horario = _dias_horarios_to_string(horas_parseadas)
            edicion.profesor = prof
            edicion.save(update_fields=["horario", "profesor", "updated_at"])
            creadas = _crear_clases_si_vacias_desde_estructura(edicion, user_sede, prof)
            request.session.pop(sk, None)
            request.session.modified = True
            if prof:
                msg = "Estructura guardada y profesor asignado a esta edición."
            else:
                msg = (
                    "Estructura guardada. Puedes asignar un profesor más adelante si lo necesitas."
                )
            if creadas:
                msg += f" Se generaron {creadas} sesiones en el calendario."
            messages.success(request, msg)
            return redirect("hechos:estructura_ediciones")

        ciclo_label = dict(Escuela.Ciclo.choices).get(escuela.ciclo, escuela.ciclo)
        return render(
            request,
            "hechos/estructura_wizard_paso5.html",
            {
                **wizard_ctx,
                "step": 5,
                "dias_seleccionados": dias_seleccionados,
                "resumen_filas": resumen_filas,
                "num_clases": len(fechas),
                "fechas_preview": fechas[:10],
                "profesor_resumen": profesor_resumen,
                "ciclo_label": ciclo_label,
            },
        )


@login_required
def estructura_edicion_legacy_redirect(request, edicion_id):
    """Compatibilidad con enlaces antiguos /hechos/estructura/<edicion_id>/."""
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r
    user_sede = get_user_sede(request.user)
    if not user_sede:
        return redirect("core:dashboard")
    get_object_or_404(EdicionCurso, id=edicion_id, curso__sede=user_sede)
    return redirect("hechos:estructura_configurar", edicion_id=edicion_id, step=1)


@login_required
def cursos_list(request):
    """
    Lista de cursos
    """
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    cursos = Curso.objects.filter(sede=user_sede, is_active=True).select_related('ruta_estudio')
    
    # Filtrar según el perfil del usuario
    if hasattr(request.user, 'estudiante_profile'):
        # Estudiante ve solo sus cursos matriculados
        matriculas_qs = Matricula.objects.filter(
            estudiante=request.user.estudiante_profile,
            sede=user_sede,
            is_active=True
        ).select_related('edicion_curso__curso__ruta_estudio__escuela', 'edicion_curso__profesor__user')
        cursos_ids = matriculas_qs.values_list('edicion_curso__curso_id', flat=True)
        cursos = cursos.filter(id__in=cursos_ids)
        context = {
            'matriculas': matriculas_qs,
            'user_sede': user_sede,
        }
        return render(request, 'hechos/cursos_list_estudiante.html', context)
    elif hasattr(request.user, 'profesor_profile'):
        # Profesor ve solo sus cursos (a través de ediciones)
        ediciones_profesor = EdicionCurso.objects.filter(
            profesor=request.user.profesor_profile,
            curso__sede=user_sede,
            is_active=True
        ).values_list('curso_id', flat=True)
        cursos = cursos.filter(id__in=ediciones_profesor)
    elif hasattr(request.user, 'admin_escuela_profile') and not request.user.is_super_admin():
        resp = ca.require_academico_o_pedagogico(request)
        if resp:
            return resp
    
    context = {
        'cursos': cursos,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/cursos_list_modern.html', context)


@login_required
def escuelas_disponibles(request):
    """
    Lista pública autenticada de escuelas disponibles para estudiantes.
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver las escuelas disponibles.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.info(request, 'Selecciona tu sede para ver escuelas disponibles.')
        return redirect('hechos:seleccionar_sede_estudiante')

    solicitudes = {
        solicitud.edicion_curso_id: solicitud
        for solicitud in SolicitudMatricula.objects.filter(estudiante=estudiante).select_related(
            'edicion_curso__curso__ruta_estudio__escuela', 'edicion_curso__curso__sede', 'edicion_curso__profesor__user'
        )
    }
    matriculas_activas = set(
        Matricula.objects.filter(estudiante=estudiante, is_active=True).values_list('edicion_curso_id', flat=True)
    )

    ediciones = EdicionCurso.objects.filter(
        is_active=True,
        curso__is_active=True,
        curso__ruta_estudio__escuela__isnull=False,
        curso__sede=user_sede,
    ).select_related('curso__ruta_estudio__escuela', 'curso__sede', 'profesor__user').order_by(
        'curso__ruta_estudio__escuela__nombre', 'curso__ruta_estudio__nombre', 'curso__nombre', 'nombre_edicion'
    )

    escuelas_by_id = {}
    for edicion in ediciones:
        solicitud = solicitudes.get(edicion.id)
        escuela = edicion.curso.escuela
        if not escuela:
            continue

        escuela_data = escuelas_by_id.setdefault(
            escuela.id,
            {
                'escuela': escuela,
                'sede': escuela.sede or edicion.curso.sede,
                'niveles': [],
            },
        )
        escuela_data['niveles'].append({
            'nivel': edicion.curso.nivel,
            'edicion': edicion,
            'curso': edicion.curso,
            'ya_matriculado': edicion.id in matriculas_activas,
            'solicitud': solicitud,
            'puede_solicitar': edicion.id not in matriculas_activas and solicitud is None,
        })

    # Solo escuelas donde el estudiante no tiene matrícula activa en ningún grupo de esa escuela.
    escuelas_list = []
    for _eid, escuela_data in escuelas_by_id.items():
        if any(n['ya_matriculado'] for n in escuela_data['niveles']):
            continue
        partes = [
            escuela_data['escuela'].nombre or '',
            getattr(escuela_data.get('sede'), 'nombre', None) or '',
            escuela_data['escuela'].descripcion or '',
        ]
        for n in escuela_data['niveles']:
            if n.get('nivel') and getattr(n['nivel'], 'nombre', None):
                partes.append(n['nivel'].nombre)
            partes.append(n['curso'].nombre or '')
            partes.append(n['edicion'].nombre_edicion or '')
            if n['edicion'].profesor and n['edicion'].profesor.user:
                partes.append(n['edicion'].profesor.user.get_full_name() or '')
        escuela_data['search_text'] = ' '.join(p for p in partes if p)
        escuelas_list.append(escuela_data)

    context = {
        'escuelas': escuelas_list,
        'estudiante': estudiante,
        'user_sede': user_sede,
    }
    return render(request, 'hechos/escuelas_disponibles.html', context)


@login_required
def quejas_reclamos(request):
    if not hasattr(request.user, "estudiante_profile"):
        messages.error(request, "Solo los estudiantes pueden enviar quejas y reclamos.")
        return redirect("core:dashboard")

    estudiante = request.user.estudiante_profile
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.info(request, "Selecciona tu sede para contactar al coordinador académico.")
        return redirect("hechos:seleccionar_sede_estudiante")

    base_coordinadores = AdminEscuela.objects.filter(
        sede=user_sede,
        is_active=True,
        user__is_active=True,
    )
    coordinador_academico = (
        base_coordinadores.filter(capacidad_asignaciones__capacidad__codigo='academico')
        .select_related('user')
        .distinct()
        .first()
    )
    if not coordinador_academico:
        coordinador_academico = (
            base_coordinadores.filter(tipo_coordinador=AdminEscuela.TipoCoordinador.ACADEMICO)
            .select_related('user')
            .first()
        )

    wa_prefill = (
        f"Hola, soy {request.user.get_full_name() or request.user.email} "
        f"(estudiante, sede {user_sede.nombre}). "
        f"Escribo por el canal de quejas y reclamos en HechosHub."
    )
    coordinador_whatsapp_url = None
    if coordinador_academico and coordinador_academico.user.phone:
        base_wa = _whatsapp_me_url(coordinador_academico.user.phone)
        if base_wa:
            coordinador_whatsapp_url = f"{base_wa}?text={quote(wa_prefill)}"

    if request.method == "POST":
        form = QuejaReclamoForm(request.POST)
        if form.is_valid():
            tipo = form.cleaned_data["asunto"]
            etiqueta_asunto = QuejaReclamo.Tipo(tipo).label
            mensaje = form.cleaned_data["mensaje"]

            if tipo == QuejaReclamo.Tipo.SOLICITUD:
                sol = SolicitudEspecialEstudiante.objects.create(
                    sede=user_sede,
                    estudiante=estudiante,
                    tipo=SolicitudEspecialEstudiante.Tipo.OTRA,
                    asunto=etiqueta_asunto,
                    descripcion=mensaje,
                )
                if coordinador_academico and coordinador_academico.user.email:
                    preview = (mensaje[:70] + "…") if len(mensaje) > 70 else mensaje
                    subject = f"[HechosHub] Solicitud - {user_sede.nombre}: {preview}"
                    body = (
                        f"Sede: {user_sede.nombre}\n"
                        f"Estudiante: {request.user.get_full_name()} ({request.user.email})\n"
                        f"Asunto: {etiqueta_asunto}\n\n"
                        f"Mensaje:\n{mensaje}\n\n"
                        f"ID bandeja: {sol.id}\n"
                    )
                    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@hechoshub.local"
                    email = EmailMessage(
                        subject=subject,
                        body=body,
                        from_email=from_email,
                        to=[coordinador_academico.user.email],
                        reply_to=[request.user.email] if request.user.email else None,
                    )
                    try:
                        email.send(fail_silently=False)
                    except Exception:
                        messages.warning(
                            request,
                            "Se registró tu solicitud, pero no se pudo enviar el correo al coordinador.",
                        )
                    else:
                        messages.success(
                            request,
                            "Tu solicitud fue registrada y se notificó al coordinador académico.",
                        )
                else:
                    messages.success(
                        request,
                        "Tu solicitud fue registrada. El coordinador académico la verá en su bandeja.",
                    )
                return redirect("hechos:quejas_reclamos")

            if not coordinador_academico or not coordinador_academico.user.email:
                messages.error(
                    request,
                    "No hay coordinador académico configurado para tu sede, o no tiene correo. Contacta al administrador.",
                )
                return redirect("hechos:quejas_reclamos")

            qr = QuejaReclamo(
                tipo=tipo,
                asunto=etiqueta_asunto,
                mensaje=mensaje,
                estudiante=estudiante,
                sede=user_sede,
                asignado_a=coordinador_academico,
            )
            qr.save()

            subject = f"[HechosHub] {etiqueta_asunto} · {user_sede.nombre}"
            body = (
                f"Sede: {user_sede.nombre}\n"
                f"Estudiante: {request.user.get_full_name()} ({request.user.email})\n"
                f"Asunto: {etiqueta_asunto}\n\n"
                f"Mensaje:\n{qr.mensaje}\n\n"
                f"ID interno: {qr.id}\n"
            )

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or "no-reply@hechoshub.local"
            email = EmailMessage(
                subject=subject,
                body=body,
                from_email=from_email,
                to=[coordinador_academico.user.email],
                reply_to=[request.user.email] if request.user.email else None,
            )
            try:
                email.send(fail_silently=False)
            except Exception:
                messages.warning(
                    request,
                    "Se guardó tu mensaje, pero no se pudo enviar el correo. Revisa la configuración de email.",
                )
            else:
                messages.success(request, "Tu mensaje fue enviado al coordinador académico.")

            return redirect("hechos:quejas_reclamos")
    else:
        form = QuejaReclamoForm()

    return render(
        request,
        "hechos/quejas_reclamos_form.html",
        {
            "form": form,
            "user_sede": user_sede,
            "coordinador_academico": coordinador_academico,
            "coordinador_whatsapp_url": coordinador_whatsapp_url,
        },
    )


@login_required
def mis_certificados(request):
    if not hasattr(request.user, "estudiante_profile"):
        messages.error(request, "Solo los estudiantes pueden acceder a esta sección.")
        return redirect("core:dashboard")
    return render(request, "hechos/mis_certificados.html")


@login_required
def solicitar_matricula(request, edicion_id):
    """
    Crea una solicitud de matrícula para una edición de curso.
    """
    if request.method != 'POST':
        return redirect('hechos:escuelas_disponibles')

    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden solicitar matrícula.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    edicion = get_object_or_404(
        EdicionCurso.objects.select_related('curso__sede', 'profesor__user'),
        id=edicion_id,
        is_active=True,
        curso__is_active=True,
    )

    if Matricula.objects.filter(estudiante=estudiante, edicion_curso=edicion, is_active=True).exists():
        messages.info(request, 'Ya tienes una matrícula activa en esta escuela.')
        return redirect('hechos:escuelas_disponibles')

    if SolicitudMatricula.objects.filter(estudiante=estudiante, edicion_curso=edicion).exists():
        messages.info(request, 'Ya enviaste una solicitud para esta escuela.')
        return redirect('hechos:escuelas_disponibles')

    if edicion.cupos_disponibles <= 0:
        messages.warning(request, 'Esta escuela no tiene cupos disponibles por ahora.')
        return redirect('hechos:escuelas_disponibles')

    SolicitudMatricula.objects.create(
        sede=edicion.curso.sede,
        estudiante=estudiante,
        edicion_curso=edicion,
    )
    messages.success(request, f'Solicitud enviada para {edicion.curso.nombre} - {edicion.nombre_edicion}.')
    return redirect('hechos:mis_escuelas')


@login_required
def mis_escuelas(request):
    """
    Lista de solicitudes de matrícula del estudiante (Mis escuelas).
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver sus escuelas.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    solicitudes = SolicitudMatricula.objects.filter(estudiante=estudiante).select_related(
        'edicion_curso__curso__ruta_estudio__escuela', 'edicion_curso__curso__sede', 'edicion_curso__profesor__user'
    )

    context = {
        'solicitudes': solicitudes,
        'estudiante': estudiante,
    }
    return render(request, 'hechos/mis_escuelas.html', context)


@login_required
def solicitudes_matricula_admin(request):
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    pendientes = SolicitudMatricula.objects.filter(
        sede=user_sede,
        estado='pendiente',
    ).select_related(
        'estudiante__user',
        'edicion_curso__curso__ruta_estudio__escuela',
        'edicion_curso__profesor__user',
    ).order_by('-fecha_solicitud')

    revisadas = SolicitudMatricula.objects.filter(
        sede=user_sede,
    ).exclude(
        estado='pendiente'
    ).select_related(
        'estudiante__user',
        'edicion_curso__curso__ruta_estudio__escuela',
        'revisado_por',
    ).order_by('-fecha_revision', '-updated_at')[:30]

    return render(
        request,
        'hechos/solicitudes_matricula_admin.html',
        {
            'pendientes': pendientes,
            'revisadas': revisadas,
            'user_sede': user_sede,
        },
    )


@login_required
def revisar_solicitud_matricula(request, solicitud_id):
    if request.method != 'POST':
        return redirect('hechos:solicitudes_matricula_admin')

    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    solicitud = get_object_or_404(
        SolicitudMatricula.objects.select_related('estudiante__user', 'edicion_curso__curso__sede'),
        id=solicitud_id,
        sede=user_sede,
    )
    if solicitud.estado != 'pendiente':
        messages.info(request, 'Esta solicitud ya fue revisada.')
        return redirect('hechos:solicitudes_matricula_admin')

    accion = (request.POST.get('accion') or '').strip().lower()
    observaciones = (request.POST.get('observaciones') or '').strip()
    ahora = timezone.now()

    if accion == 'aprobar':
        solicitud.estado = 'aprobada'
        solicitud.observaciones = observaciones
        solicitud.revisado_por = request.user
        solicitud.fecha_revision = ahora
        solicitud.save(update_fields=['estado', 'observaciones', 'revisado_por', 'fecha_revision', 'updated_at'])

        estudiante = solicitud.estudiante
        if estudiante.sede_id != solicitud.sede_id:
            estudiante.sede = solicitud.sede
            estudiante.save(update_fields=['sede'])
        if estudiante.user.sede_id != solicitud.sede_id:
            estudiante.user.sede = solicitud.sede
            estudiante.user.save(update_fields=['sede'])

        Matricula.objects.get_or_create(
            estudiante=estudiante,
            edicion_curso=solicitud.edicion_curso,
            defaults={
                'sede': solicitud.sede,
                'periodo': get_current_period(),
                'estado': 'activa',
                'is_active': True,
            },
        )

        NotificacionEstudiante.objects.create(
            estudiante=estudiante,
            tipo=NotificacionEstudiante.Tipo.APROBACION,
            titulo='Solicitud aprobada',
            mensaje=(
                f"Tu solicitud para {solicitud.edicion_curso.curso.nombre} "
                f"({solicitud.edicion_curso.nombre_edicion}) fue aprobada."
                + (f" Observación: {observaciones}" if observaciones else "")
            ),
        )
        messages.success(request, 'Solicitud aprobada y matrícula creada.')
    elif accion == 'rechazar':
        solicitud.estado = 'rechazada'
        solicitud.observaciones = observaciones
        solicitud.revisado_por = request.user
        solicitud.fecha_revision = ahora
        solicitud.save(update_fields=['estado', 'observaciones', 'revisado_por', 'fecha_revision', 'updated_at'])

        NotificacionEstudiante.objects.create(
            estudiante=solicitud.estudiante,
            tipo=NotificacionEstudiante.Tipo.RECHAZO,
            titulo='Solicitud rechazada',
            mensaje=(
                f"Tu solicitud para {solicitud.edicion_curso.curso.nombre} "
                f"({solicitud.edicion_curso.nombre_edicion}) fue rechazada."
                + (f" Motivo: {observaciones}" if observaciones else "")
            ),
        )
        messages.warning(request, 'Solicitud rechazada.')
    else:
        messages.error(request, 'Acción no válida.')

    return redirect('hechos:solicitudes_matricula_admin')


@login_required
def solicitudes_especiales_estudiante(request):
    """Compatibilidad: la gestión vive en la página unificada de quejas y reclamos."""
    return redirect("hechos:quejas_reclamos")


@login_required
def solicitudes_especiales_admin(request):
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    pendientes = SolicitudEspecialEstudiante.objects.filter(
        sede=user_sede,
        estado='pendiente',
    ).select_related('estudiante__user').order_by('-fecha_solicitud')
    revisadas = SolicitudEspecialEstudiante.objects.filter(
        sede=user_sede,
    ).exclude(estado='pendiente').select_related('estudiante__user', 'revisado_por').order_by('-fecha_revision', '-updated_at')[:30]
    total_bandeja = SolicitudEspecialEstudiante.objects.filter(sede=user_sede).count()

    return render(
        request,
        'hechos/solicitudes_especiales_admin.html',
        {'pendientes': pendientes, 'revisadas': revisadas, 'user_sede': user_sede, 'total_bandeja': total_bandeja},
    )


@login_required
def revisar_solicitud_especial_admin(request, solicitud_id):
    if request.method != 'POST':
        return redirect('hechos:solicitudes_especiales_admin')

    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r

    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    solicitud = get_object_or_404(
        SolicitudEspecialEstudiante.objects.select_related('estudiante__user'),
        id=solicitud_id,
        sede=user_sede,
    )
    if solicitud.estado != SolicitudEspecialEstudiante.Estado.PENDIENTE:
        messages.info(request, 'Esta solicitud ya fue revisada.')
        return redirect('hechos:solicitudes_especiales_admin')

    accion = (request.POST.get('accion') or '').strip().lower()
    observaciones = (request.POST.get('observaciones') or '').strip()
    if accion == 'atender':
        solicitud.estado = SolicitudEspecialEstudiante.Estado.ATENDIDA
    elif accion == 'cerrar':
        solicitud.estado = SolicitudEspecialEstudiante.Estado.CERRADA
    else:
        messages.error(request, 'Acción no válida.')
        return redirect('hechos:solicitudes_especiales_admin')

    solicitud.observaciones = observaciones
    solicitud.revisado_por = request.user
    solicitud.fecha_revision = timezone.now()
    solicitud.save(update_fields=['estado', 'observaciones', 'revisado_por', 'fecha_revision', 'updated_at'])

    NotificacionEstudiante.objects.create(
        estudiante=solicitud.estudiante,
        tipo=NotificacionEstudiante.Tipo.INFO,
        titulo='Actualización de tu solicitud',
        mensaje=(
            f"Tu solicitud «{solicitud.asunto}» fue marcada como {solicitud.get_estado_display().lower()}."
            + (f" Comentario: {observaciones}" if observaciones else "")
        ),
    )
    messages.success(request, 'Solicitud actualizada.')
    return redirect('hechos:solicitudes_especiales_admin')


@login_required
def rutas_estudio_list(request):
    """
    Lista de rutas de estudio (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    rutas = RutaEstudio.objects.filter(sede=user_sede, is_active=True).prefetch_related('cursos')
    
    # Agregar información de cursos para cada ruta
    rutas_con_cursos = []
    for ruta in rutas:
        cursos = ruta.cursos.filter(is_active=True).order_by('orden', 'nombre')
        rutas_con_cursos.append({
            'ruta': ruta,
            'cursos': cursos,
            'total_cursos': cursos.count(),
            'duracion_total': sum(curso.duracion_semanas for curso in cursos)
        })
    
    context = {
        'rutas_con_cursos': rutas_con_cursos,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/rutas_estudio_list.html', context)


@login_required
def ruta_estudio_detail(request, ruta_id):
    """
    Detalle de una ruta de estudio específica
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    ruta = get_object_or_404(RutaEstudio, id=ruta_id, sede=user_sede, is_active=True)
    cursos = ruta.cursos.filter(is_active=True).order_by('orden', 'nombre')
    
    # Estadísticas de la ruta
    total_estudiantes = 0
    for curso in cursos:
        total_estudiantes += curso.total_estudiantes_inscritos
    
    # Obtener profesores disponibles para asignar a nuevos cursos
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True).select_related('user')
    
    context = {
        'ruta': ruta,
        'cursos': cursos,
        'total_cursos': cursos.count(),
        'total_estudiantes': total_estudiantes,
        'duracion_total': sum(curso.duracion_semanas for curso in cursos),
        'profesores': profesores,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/ruta_estudio_detail.html', context)


@login_required
def crear_curso_ruta(request, ruta_id):
    """
    Crear nuevo curso para una ruta específica
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    ruta = get_object_or_404(RutaEstudio, id=ruta_id, sede=user_sede, is_active=True)
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True).select_related('user')
    
    if request.method == 'POST':
        try:
            profesor_id = request.POST.get('profesor')
            profesor = Profesor.objects.get(id=profesor_id, sede=user_sede)
            
            curso = Curso.objects.create(
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion', ''),
                ruta_estudio=ruta,
                orden=request.POST.get('orden', 1) or 1,
                duracion_semanas=request.POST.get('duracion_semanas', 4) or 4,
                sede=user_sede
            )
            
            messages.success(request, f'Curso "{request.POST.get("nombre")}" creado exitosamente en la ruta {ruta.nombre}.')
            return redirect('hechos:ruta_estudio_detail', ruta_id=ruta_id)
            
        except Exception as e:
            messages.error(request, f'Error al crear curso: {str(e)}')
    
    # Obtener el siguiente orden disponible
    ultimo_orden = ruta.cursos.filter(is_active=True).aggregate(
        max_orden=models.Max('orden')
    )['max_orden'] or 0
    siguiente_orden = ultimo_orden + 1
    
    context = {
        'ruta': ruta,
        'profesores': profesores,
        'siguiente_orden': siguiente_orden,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/crear_curso_ruta.html', context)


@login_required
def profesor_bandeja_entregas(request):
    """
    Entregas de actividades con evidencia pendientes de calificar (vista tipo bandeja).
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')
    entregas = list(entregas_pendientes_calificacion_qs(request.user, user_sede))
    return render(
        request,
        'hechos/profesor_bandeja_entregas.html',
        {
            'entregas': entregas,
            'user_sede': user_sede,
        },
    )


@login_required
def clases_list(request):
    """
    Lista de clases
    """
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    if (
        request.resolver_match.url_name == 'clases_list'
        and hasattr(request.user, 'profesor_profile')
        and not hasattr(request.user, 'estudiante_profile')
        and not request.user.is_super_admin()
    ):
        target = reverse('hechos:mis_escuelas_profesor')
        q = request.GET.urlencode()
        if q:
            target = f'{target}?{q}'
        return redirect(target)

    if hasattr(request.user, 'admin_escuela_profile') and not request.user.is_super_admin():
        if not ca.admin_may_access_clases_list(request.user):
            messages.error(request, 'No tienes permisos para ver las clases.')
            return redirect('core:dashboard')

    es_mis_escuelas_docente = request.resolver_match.url_name == 'mis_escuelas_profesor'
    profesor = getattr(request.user, 'profesor_profile', None)

    if es_mis_escuelas_docente:
        if not profesor:
            return redirect('hechos:clases_list')
        escuelas_asignadas = list(
            Escuela.objects.filter(
                sede=user_sede,
                maestro=profesor,
                is_active=True,
            ).order_by('-anio', 'ciclo', 'grupo', 'nombre')
        )
        escuela_pk = request.GET.get('escuela')
        if escuela_pk:
            escuela_filtro = get_object_or_404(
                Escuela,
                id=escuela_pk,
                sede=user_sede,
                maestro=profesor,
                is_active=True,
            )
            ediciones_escuela = EdicionCurso.objects.filter(
                curso__ruta_estudio__escuela=escuela_filtro,
                curso__sede=user_sede,
                is_active=True,
                curso__is_active=True,
            )
            for ed in ediciones_escuela:
                prof_clase = ed.profesor or escuela_filtro.maestro
                _crear_clases_si_vacias_desde_estructura(ed, user_sede, prof_clase)
            clases_qs = (
                Clase.objects.filter(
                    sede=user_sede,
                    is_active=True,
                    edicion_curso__curso__ruta_estudio__escuela=escuela_filtro,
                )
                .select_related(
                    'edicion_curso__curso__ruta_estudio__escuela',
                    'profesor__user',
                )
                .prefetch_related('asistencias')
                .order_by('fecha_clase', 'edicion_curso__curso__nombre', 'numero_clase')
            )
            clases = list(clases_qs)
            for c in clases:
                regs = list(c.asistencias.all())
                total = len(regs)
                presentes = sum(1 for a in regs if a.estado == 'presente')
                c.porcentaje_asistencia_ui = round(100 * presentes / total, 1) if total else None
                c.n_registros_asistencia = total
            num_estudiantes_escuela = (
                Matricula.objects.filter(
                    sede=user_sede,
                    is_active=True,
                    edicion_curso__curso__ruta_estudio__escuela=escuela_filtro,
                )
                .values('estudiante_id')
                .distinct()
                .count()
            )
            return render(
                request,
                'hechos/clases_list_modern.html',
                {
                    'user_sede': user_sede,
                    'docente_mis_escuelas_modo': 'clases_por_escuela',
                    'escuelas_asignadas': escuelas_asignadas,
                    'escuela_filtro': escuela_filtro,
                    'clases': clases,
                    'sesiones_por_mes': sesiones_agrupadas_por_mes(clases),
                    'num_estudiantes_escuela': num_estudiantes_escuela,
                    'clases_completadas': [],
                    'clases_en_progreso': [],
                    'promedio_asistencia': None,
                },
            )

        escuelas_feed = []
        for escuela in escuelas_asignadas:
            ediciones_qs = EdicionCurso.objects.filter(
                curso__ruta_estudio__escuela=escuela,
                curso__sede=user_sede,
                is_active=True,
                curso__is_active=True,
            )
            n_ed = EdicionCurso.objects.filter(
                curso__ruta_estudio__escuela=escuela,
                curso__sede=user_sede,
                is_active=True,
                curso__is_active=True,
            ).count()
            n_clases = Clase.objects.filter(
                sede=user_sede,
                is_active=True,
                edicion_curso__curso__ruta_estudio__escuela=escuela,
            ).count()
            n_est = (
                Matricula.objects.filter(
                    sede=user_sede,
                    is_active=True,
                    edicion_curso__curso__ruta_estudio__escuela=escuela,
                )
                .values('estudiante_id')
                .distinct()
                .count()
            )
            edicion_referencia = (
                ediciones_qs.prefetch_related('estructura_horarios')
                .order_by('-fecha_inicio')
                .first()
            )
            horario_ui = ""
            aula_ui = ""
            if edicion_referencia:
                horarios = list(edicion_referencia.estructura_horarios.all())
                if horarios:
                    horarios = sorted(horarios, key=lambda h: (h.dia_semana, h.hora))
                    horario_ui = " · ".join(
                        f"{h.get_dia_semana_display()} {h.hora.strftime('%I:%M %p').lstrip('0')}"
                        for h in horarios
                    )
                elif edicion_referencia.horario:
                    horario_ui = edicion_referencia.horario
                aula_ui = (edicion_referencia.aula or "").strip()
            if not aula_ui:
                salon_asignado = (
                    Salon.objects.filter(
                        sede=user_sede,
                        escuela=escuela,
                        is_active=True,
                    )
                    .order_by('nombre')
                    .first()
                )
                if salon_asignado:
                    aula_ui = salon_asignado.nombre
            escuelas_feed.append(
                {
                    'escuela': escuela,
                    'num_ediciones': n_ed,
                    'num_clases': n_clases,
                    'num_estudiantes': n_est,
                    'horario_ui': horario_ui,
                    'aula_ui': aula_ui,
                }
            )
        return render(
            request,
            'hechos/clases_list_modern.html',
            {
                'user_sede': user_sede,
                'docente_mis_escuelas_modo': 'escuelas',
                'escuelas_asignadas': escuelas_asignadas,
                'escuelas_feed': escuelas_feed,
                'clases': [],
                'clases_completadas': [],
                'clases_en_progreso': [],
                'promedio_asistencia': None,
            },
        )

    clases = Clase.objects.filter(sede=user_sede, is_active=True).select_related(
        'edicion_curso__curso__ruta_estudio',
        'profesor__user',
    ).prefetch_related('asistencias')

    # Filtrar según el perfil del usuario
    if hasattr(request.user, 'profesor_profile'):
        # Profesor ve solo sus clases
        clases = clases.filter(profesor=request.user.profesor_profile)
    elif hasattr(request.user, 'estudiante_profile'):
        # Estudiante ve clases de las ediciones en las que está matriculado
        edicion_ids = Matricula.objects.filter(
            estudiante=request.user.estudiante_profile,
            sede=user_sede,
            is_active=True,
        ).values_list('edicion_curso_id', flat=True)
        clases = clases.filter(edicion_curso_id__in=edicion_ids)

    clases = list(clases.order_by('fecha_clase', 'edicion_curso__curso__nombre', 'numero_clase'))
    for c in clases:
        regs = list(c.asistencias.all())
        total = len(regs)
        presentes = sum(1 for a in regs if a.estado == 'presente')
        c.porcentaje_asistencia_ui = round(100 * presentes / total, 1) if total else None
        c.n_registros_asistencia = total

    context = {
        'clases': clases,
        'user_sede': user_sede,
        'docente_mis_escuelas_modo': '',
        'clases_completadas': [],
        'clases_en_progreso': [],
        'promedio_asistencia': None,
    }

    return render(request, 'hechos/clases_list_modern.html', context)


def _profesor_escuela_docente(request, escuela_id):
    """Escuela activa del maestro en esta sede, o (None, redirect response)."""
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder.')
        return None, redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return None, redirect('core:dashboard')
    prof = request.user.profesor_profile
    escuela = get_object_or_404(
        Escuela,
        id=escuela_id,
        sede=user_sede,
        maestro=prof,
        is_active=True,
    )
    return (user_sede, escuela, prof), None


def _estudiante_matriculado_en_escuela(estudiante, escuela, user_sede):
    if not escuela or not user_sede:
        return False
    return Matricula.objects.filter(
        estudiante=estudiante,
        sede=user_sede,
        is_active=True,
        edicion_curso__curso__ruta_estudio__escuela=escuela,
    ).exists()


def _porcentajes_evaluacion_por_estudiante_escuela(estudiante_ids, user_sede, escuela):
    """
    Porcentajes por estudiante: notas de curso (modelo Nota) y entregas de actividad
    calificadas (EntregaActividad), siempre en el contexto de esta escuela y sede.
    """
    pct_by_est = defaultdict(list)
    if not estudiante_ids:
        return pct_by_est

    for row in (
        Nota.objects.filter(
            sede=user_sede,
            curso__ruta_estudio__escuela=escuela,
            puntaje_maximo__gt=0,
            estudiante_id__in=estudiante_ids,
        ).values('estudiante_id', 'puntaje_obtenido', 'puntaje_maximo')
    ):
        po = float(row['puntaje_obtenido'])
        pm = float(row['puntaje_maximo'])
        pct_by_est[row['estudiante_id']].append(po * 100.0 / pm)

    entregas = EntregaActividad.objects.filter(
        sede=user_sede,
        actividad__escuela=escuela,
        actividad__is_active=True,
        estudiante_id__in=estudiante_ids,
        puntaje_asignado__isnull=False,
    ).select_related('actividad')
    for ent in entregas:
        max_pts = ent.actividad.puntos_posibles
        if max_pts is None:
            continue
        fm = float(max_pts)
        if fm <= 0 or ent.puntaje_asignado is None:
            continue
        pct_by_est[ent.estudiante_id].append(float(ent.puntaje_asignado) * 100.0 / fm)

    return pct_by_est


@login_required
def profesor_escuela_estudiantes(request, escuela_id):
    """Listado de estudiantes matriculados en cursos de la escuela (docente asignado)."""
    pack, redir = _profesor_escuela_docente(request, escuela_id)
    if redir:
        return redir
    user_sede, escuela, _prof = pack
    estudiante_ids = list(
        Matricula.objects.filter(
            sede=user_sede,
            is_active=True,
            edicion_curso__curso__ruta_estudio__escuela=escuela,
        )
        .values_list('estudiante_id', flat=True)
        .distinct()
    )
    estudiantes = (
        Estudiante.objects.filter(id__in=estudiante_ids)
        .select_related('user')
        .order_by('user__last_name', 'user__first_name', 'user__email')
    )
    pct_by_est = _porcentajes_evaluacion_por_estudiante_escuela(
        estudiante_ids, user_sede, escuela
    )
    filas = []
    for e in estudiantes:
        pcts = pct_by_est.get(e.id) or []
        filas.append(
            {
                'estudiante': e,
                'promedio_pct': (sum(pcts) / len(pcts)) if pcts else None,
                'n_calificaciones': len(pcts),
            }
        )
    volver_url = f"{reverse('hechos:mis_escuelas_profesor')}?escuela={escuela.id}"
    return render(
        request,
        'hechos/profesor_escuela_estudiantes.html',
        {
            'escuela': escuela,
            'user_sede': user_sede,
            'filas': filas,
            'volver_url': volver_url,
        },
    )


@login_required
def profesor_escuela_estudiante_notas(request, escuela_id, estudiante_id):
    """Notas del estudiante en cursos que pertenecen a esta escuela."""
    pack, redir = _profesor_escuela_docente(request, escuela_id)
    if redir:
        return redir
    user_sede, escuela, _prof = pack
    inscrito = Matricula.objects.filter(
        estudiante_id=estudiante_id,
        sede=user_sede,
        is_active=True,
        edicion_curso__curso__ruta_estudio__escuela=escuela,
    ).exists()
    if not inscrito:
        raise Http404
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    notas = (
        Nota.objects.filter(
            estudiante=estudiante,
            sede=user_sede,
            curso__ruta_estudio__escuela=escuela,
        )
        .select_related('curso', 'profesor__user')
        .order_by('-fecha_evaluacion', 'curso__nombre')
    )
    entregas_calif = (
        EntregaActividad.objects.filter(
            estudiante=estudiante,
            sede=user_sede,
            actividad__escuela=escuela,
            actividad__is_active=True,
            puntaje_asignado__isnull=False,
        )
        .select_related('actividad')
        .order_by('-evaluado_en', '-actualizado_en')
    )
    evaluaciones = []
    for n in notas:
        pct = float(n.porcentaje) if n.puntaje_maximo and n.puntaje_maximo > 0 else None
        evaluaciones.append(
            {
                'kind': 'nota',
                'fecha': n.fecha_evaluacion,
                'curso_o_ctx': n.curso.nombre,
                'titulo': n.titulo,
                'tipo_label': n.get_tipo_display(),
                'puntaje_celda': f'{n.puntaje_obtenido} / {n.puntaje_maximo}',
                'porcentaje': pct,
                'nota': n,
            }
        )
    for ent in entregas_calif:
        max_pts = ent.actividad.puntos_posibles
        pct = None
        if max_pts is not None and float(max_pts) > 0 and ent.puntaje_asignado is not None:
            pct = float(ent.puntaje_asignado) * 100.0 / float(max_pts)
        fecha_ev = ent.evaluado_en.date() if ent.evaluado_en else None
        if max_pts is not None:
            puntaje_celda = f'{ent.puntaje_asignado} / {max_pts}'
        else:
            puntaje_celda = str(ent.puntaje_asignado)
        evaluaciones.append(
            {
                'kind': 'entrega',
                'fecha': fecha_ev,
                'curso_o_ctx': 'Actividad de escuela',
                'titulo': ent.actividad.titulo,
                'tipo_label': 'Entrega calificada',
                'puntaje_celda': puntaje_celda,
                'porcentaje': pct,
                'entrega': ent,
            }
        )

    def _sort_key(ev):
        fd = ev['fecha']
        if isinstance(fd, datetime):
            fd = fd.date()
        return fd or date.min

    evaluaciones.sort(key=_sort_key, reverse=True)

    pcts_prom = [e['porcentaje'] for e in evaluaciones if e['porcentaje'] is not None]
    promedio_pct = (sum(pcts_prom) / len(pcts_prom)) if pcts_prom else None
    volver_lista = reverse('hechos:profesor_escuela_estudiantes', kwargs={'escuela_id': escuela.id})
    volver_escuela = f"{reverse('hechos:mis_escuelas_profesor')}?escuela={escuela.id}"
    return render(
        request,
        'hechos/profesor_escuela_estudiante_notas.html',
        {
            'escuela': escuela,
            'estudiante': estudiante,
            'evaluaciones': evaluaciones,
            'promedio_pct': promedio_pct,
            'user_sede': user_sede,
            'volver_lista_url': volver_lista,
            'volver_escuela_url': volver_escuela,
        },
    )


@login_required
def profesor_escuela_asistencia_panel(request, escuela_id):
    """Panel de asistencia por escuela (base para futuras utilidades como descarga Excel)."""
    pack, redir = _profesor_escuela_docente(request, escuela_id)
    if redir:
        return redir
    user_sede, escuela, _prof = pack
    clases = list(
        Clase.objects.filter(
            sede=user_sede,
            is_active=True,
            edicion_curso__curso__ruta_estudio__escuela=escuela,
        )
        .select_related('edicion_curso')
        .order_by('fecha_clase', 'numero_clase')
    )
    volver_url = f"{reverse('hechos:mis_escuelas_profesor')}?escuela={escuela.id}"
    return render(
        request,
        'hechos/profesor_escuela_asistencia_panel.html',
        {
            'escuela': escuela,
            'user_sede': user_sede,
            'clases': clases,
            'volver_url': volver_url,
        },
    )


@login_required
def profesor_escuela_asistencia_excel(request, escuela_id):
    """Descarga plantilla Excel de asistencia para una escuela del docente."""
    pack, redir = _profesor_escuela_docente(request, escuela_id)
    if redir:
        return redir
    user_sede, escuela, prof = pack
    estudiantes = list(
        Estudiante.objects.filter(
            sede=user_sede,
            matriculas__sede=user_sede,
            matriculas__is_active=True,
            matriculas__edicion_curso__curso__ruta_estudio__escuela=escuela,
        )
        .select_related('user')
        .distinct()
        .order_by('user__last_name', 'user__first_name', 'user__email')
    )

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    except Exception:
        messages.error(request, "Falta la dependencia para generar Excel. Instala openpyxl.")
        return redirect('hechos:profesor_escuela_asistencia_panel', escuela_id=escuela.id)

    wb = Workbook()
    ws = wb.active
    ws.title = "Asistencia"

    # Columnas base + 24 columnas de asistencia (parecido al formato de referencia).
    fixed_headers = ["No.", "NOMBRES Y APELLIDOS", "No. CODIGO", "TEL. O CEL"]
    attendance_cols = 24
    headers = fixed_headers + [str(i) for i in range(1, attendance_cols + 1)]

    header_fill = PatternFill("solid", fgColor="22A9E1")
    header_font = Font(color="FFFFFF", bold=True)
    thin_side = Side(style="thin", color="7BC8E8")
    border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    ws.cell(row=1, column=1, value="REGISTRO DE ASISTENCIA")
    ws.cell(row=1, column=1).font = Font(size=18, bold=True, color="22A9E1")
    ws.cell(row=1, column=1).alignment = center

    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=2)
    ws.merge_cells(start_row=3, start_column=3, end_row=3, end_column=4)
    ws.merge_cells(start_row=3, start_column=5, end_row=3, end_column=7)
    ws.merge_cells(start_row=3, start_column=8, end_row=3, end_column=10)
    ws["A3"] = "MAESTRO:"
    ws["C3"] = prof.user.get_full_name() or prof.user.username
    ws["E3"] = "ESCUELA:"
    ws["H3"] = escuela.nombre
    ws["K3"] = "HORA:"
    ws["L3"] = ""
    for cell in ("A3", "C3", "E3", "H3", "K3", "L3"):
        ws[cell].font = Font(bold=True)
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=5, column=col)
        c.value = headers[col - 1]
        c.fill = header_fill
        c.font = header_font
        c.border = border
        c.alignment = center

    row = 6
    for idx, est in enumerate(estudiantes, start=1):
        ws.cell(row=row, column=1, value=f"{idx:02d}")
        ws.cell(row=row, column=2, value=est.user.get_full_name() or est.user.email or "—")
        ws.cell(row=row, column=3, value=est.codigo_estudiante or "")
        ws.cell(row=row, column=4, value=est.telefono_emergencia or "")
        for col in range(5, len(headers) + 1):
            ws.cell(row=row, column=col, value="")
        row += 1

    # Mantener una altura visual similar aunque haya pocos estudiantes.
    min_rows_visual = 14
    while (row - 6) < min_rows_visual:
        ws.cell(row=row, column=1, value=f"{(row - 5):02d}")
        row += 1

    for r in range(6, row):
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=r, column=c)
            cell.border = border
            cell.alignment = left if c == 2 else center

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 16
    for col_idx in range(5, len(headers) + 1):
        ws.column_dimensions[ws.cell(row=5, column=col_idx).column_letter].width = 4

    # Nombre corto y descriptivo: asistencia + id escuela + nombre (recortado) + fecha
    nombre_corto = (slugify(escuela.nombre) or "escuela")[:24].strip("-")
    fecha = timezone.now().strftime("%Y%m%d")
    filename = f"asis-e{escuela.id}-{nombre_corto}-{fecha}.xlsx"
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def asistencia_clase(request, clase_id):
    """
    Tomar asistencia de una clase (solo para profesores)
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden tomar asistencia.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    prof = request.user.profesor_profile
    clase = get_object_or_404(
        Clase.objects.select_related(
            "profesor",
            "edicion_curso__profesor",
            "edicion_curso__curso",
            "edicion_curso__curso__ruta_estudio",
            "edicion_curso__curso__ruta_estudio__escuela",
        ),
        id=clase_id,
        sede=user_sede,
    )
    if not _profesor_puede_gestionar_clase(clase, prof):
        messages.error(request, "No tienes permisos para tomar asistencia en esta sesión.")
        return redirect("core:dashboard")

    estudiantes_qs = Estudiante.objects.filter(
        matriculas__edicion_curso=clase.edicion_curso,
        matriculas__sede=user_sede,
        matriculas__is_active=True,
        sede=user_sede,
    ).distinct().select_related("user")

    if request.method == 'POST':
        valid_states = {'presente', 'ausente', 'tarde', 'justificado'}
        for estudiante in estudiantes_qs:
            raw = (request.POST.get(f'estudiante_{estudiante.id}') or 'ausente').strip()
            value = raw if raw in valid_states else 'ausente'
            asistencia, created = Asistencia.objects.get_or_create(
                clase=clase,
                estudiante=estudiante,
                sede=user_sede,
                defaults={
                    'estado': value,
                    'registrado_por': request.user,
                },
            )
            if not created:
                asistencia.estado = value
                asistencia.registrado_por = request.user
                asistencia.save(update_fields=['estado', 'registrado_por'])

        messages.success(request, 'Asistencia registrada correctamente.')
        return redirect('hechos:asistencia_clase', clase_id=clase_id)

    estudiantes = estudiantes_qs
    
    asistencias = list(
        Asistencia.objects.filter(clase=clase, sede=user_sede).select_related('estudiante__user')
    )
    asistencia_dict = {a.estudiante_id: a.estado for a in asistencias}
    filas_asistencia = [
        {'estudiante': e, 'estado': asistencia_dict.get(e.id)} for e in estudiantes
    ]
    presentes_count = sum(1 for a in asistencias if a.estado == 'presente')
    ausentes_count = sum(1 for a in asistencias if a.estado == 'ausente')
    tarde_count = sum(1 for a in asistencias if a.estado == 'tarde')
    just_count = sum(1 for a in asistencias if a.estado == 'justificado')

    escuela_pk = None
    rt = getattr(clase.curso, 'ruta_estudio', None) if clase.edicion_curso_id else None
    if rt is not None:
        escuela_pk = getattr(rt, 'escuela_id', None)
    volver_url = reverse('hechos:mis_escuelas_profesor')
    if escuela_pk:
        volver_url = f'{volver_url}?escuela={escuela_pk}'

    context = {
        'clase': clase,
        'estudiantes': estudiantes,
        'filas_asistencia': filas_asistencia,
        'presentes_count': presentes_count,
        'ausentes_count': ausentes_count,
        'tarde_count': tarde_count,
        'justificado_count': just_count,
        'user_sede': user_sede,
        'volver_mis_escuelas_url': volver_url,
    }

    return render(request, 'hechos/asistencia_clase_modern.html', context)


def _sesion_herramienta_placeholder(request, clase_id, titulo, texto_ayuda):
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    prof = request.user.profesor_profile
    clase = get_object_or_404(
        Clase.objects.select_related(
            'edicion_curso__curso',
            'edicion_curso__curso__ruta_estudio',
        ),
        id=clase_id,
        sede=user_sede,
    )
    if not _profesor_puede_gestionar_clase(clase, prof):
        messages.error(request, 'No tienes permisos para gestionar esta sesión.')
        return redirect('core:dashboard')
    rt = getattr(clase.curso, 'ruta_estudio', None) if clase.edicion_curso_id else None
    escuela_pk = getattr(rt, 'escuela_id', None) if rt is not None else None
    volver_url = reverse('hechos:mis_escuelas_profesor')
    if escuela_pk:
        volver_url = f'{volver_url}?escuela={escuela_pk}'
    return render(
        request,
        'hechos/sesion_herramienta_placeholder.html',
        {
            'clase': clase,
            'titulo_herramienta': titulo,
            'texto_ayuda': texto_ayuda,
            'volver_url': volver_url,
            'user_sede': user_sede,
        },
    )


@login_required
def escuela_crear_actividad(request, escuela_id):
    """
    Crear actividad para la escuela (flujo tipo assignment de LMS: tipo, título,
    instrucciones, fecha límite, puntos, archivo opcional).
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    prof = request.user.profesor_profile
    escuela = get_object_or_404(
        Escuela,
        id=escuela_id,
        sede=user_sede,
        maestro=prof,
        is_active=True,
    )
    volver_url = f"{reverse('hechos:mis_escuelas_profesor')}?escuela={escuela.id}"

    if request.method == 'POST':
        form = ActividadEscuelaForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.sede = user_sede
            obj.escuela = escuela
            obj.creada_por = prof
            obj.save()
            messages.success(
                request,
                f'Actividad «{obj.titulo}» publicada para esta escuela.',
            )
            return redirect('hechos:escuela_crear_actividad', escuela_id=escuela.id)
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = ActividadEscuelaForm()

    actividades = (
        ActividadEscuela.objects.filter(
            escuela=escuela,
            sede=user_sede,
            is_active=True,
        )
        .annotate(n_entregas=Count('entregas'))
        .select_related('creada_por__user')
        .order_by('-created_at')[:100]
    )

    return render(
        request,
        'hechos/escuela_actividad_form.html',
        {
            'escuela': escuela,
            'form': form,
            'volver_url': volver_url,
            'user_sede': user_sede,
            'actividades': actividades,
        },
    )


def _estudiante_matriculado_en_curso(curso, estudiante, sede):
    return Matricula.objects.filter(
        estudiante=estudiante,
        edicion_curso__curso=curso,
        sede=sede,
        is_active=True,
    ).exists()


@login_required
def entregar_actividad_estudiante(request, curso_id, actividad_id):
    """
    El estudiante sube evidencia (texto y/o archivo) para una actividad de su escuela.
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden entregar actividades.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')
    estudiante = request.user.estudiante_profile
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    if not _estudiante_matriculado_en_curso(curso, estudiante, user_sede):
        messages.error(request, 'No tienes matrícula activa en este curso.')
        return redirect('hechos:mis_escuelas')
    escuela = curso.escuela
    if not escuela:
        messages.error(request, 'Este curso no está asociado a una escuela.')
        return redirect('hechos:mis_escuelas')
    actividad = get_object_or_404(
        ActividadEscuela,
        id=actividad_id,
        escuela=escuela,
        sede=user_sede,
        is_active=True,
    )
    volver = reverse('hechos:detalle_mis_escuela', kwargs={'curso_id': curso.id})
    if actividad.fecha_limite and timezone.now() > actividad.fecha_limite:
        messages.warning(
            request,
            'La fecha límite de esta actividad ya pasó; ya no puedes enviar ni modificar tu entrega.',
        )
        return redirect(f'{volver}#actividades')

    entrega, _created = EntregaActividad.objects.get_or_create(
        actividad=actividad,
        estudiante=estudiante,
        defaults={'sede': user_sede},
    )
    if entrega.evaluado_en:
        messages.info(request, 'Tu entrega ya fue evaluada por el docente y no se puede cambiar.')
        return redirect(f'{volver}#actividades')

    if request.method == 'POST':
        # Texto con ModelForm; archivo con request.FILES + input nativo visible (mismo patrón que el avatar).
        form = EntregaActividadTextoForm(request.POST, instance=entrega)
        uf = request.FILES.get("archivo")
        if uf is not None and getattr(uf, "size", 0) == 0:
            messages.error(
                request,
                "El archivo que elegiste pesa 0 bytes: está vacío o no se guardó nada dentro. "
                "Ábrelo (Bloc de notas, Word, etc.), escribe o pega tu tarea, guarda el archivo "
                "y vuelve a subirlo.",
            )
            uf = None
        nuevo_archivo = uf is not None and getattr(uf, "size", 0) > 0
        archivo_rechazado = False
        if nuevo_archivo:
            uf = normalizar_archivo_entrega(uf)
            try:
                entrega_evidencia_archivo_validator(uf)
            except DjangoValidationError as exc:
                archivo_rechazado = True
                err_msg = exc.messages[0] if exc.messages else str(exc)
                messages.error(request, err_msg)

        if form.is_valid() and not archivo_rechazado:
            texto = (form.cleaned_data.get("texto") or "").strip()
            tenia_archivo = bool(entrega.archivo and entrega.archivo.name)
            if not texto and not tenia_archivo and not nuevo_archivo:
                messages.error(
                    request,
                    "Debes escribir una respuesta o subir un archivo con contenido "
                    "(los archivos vacíos no cuentan).",
                )
            else:
                try:
                    mr = str(settings.MEDIA_ROOT)
                    os.makedirs(mr, exist_ok=True)
                    os.makedirs(os.path.join(mr, "actividades"), exist_ok=True)
                    obj = form.save(commit=False)
                    obj.sede = user_sede
                    if nuevo_archivo:
                        obj.archivo = uf
                    obj.save()
                except OSError as exc:
                    messages.error(
                        request,
                        "No se pudo escribir el archivo en la carpeta media del proyecto "
                        "(permisos, carpeta inexistente o carpeta sincronizada en la nube bloqueando). "
                        f"Detalle: {exc}",
                    )
                    return redirect(request.path)
                entrega = EntregaActividad.objects.get(pk=obj.pk)
                form = EntregaActividadTextoForm(instance=entrega)
                archivo_basename = (
                    os.path.basename(entrega.archivo.name)
                    if (entrega.archivo and entrega.archivo.name)
                    else ''
                )
                if nuevo_archivo:
                    messages.success(request, "Archivo guardado en media/actividades/.")
                else:
                    messages.success(request, "Tu entrega se guardó correctamente.")
                return render(
                    request,
                    'hechos/entregar_actividad_estudiante.html',
                    {
                        'form': form,
                        'curso': curso,
                        'actividad': actividad,
                        'entrega': entrega,
                        'volver_url': f'{volver}#actividades',
                        'user_sede': user_sede,
                        'entrega_archivo_basename': archivo_basename,
                    },
                )
        elif not form.is_valid():
            messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = EntregaActividadTextoForm(instance=entrega)

    entrega.refresh_from_db()
    archivo_basename = (
        os.path.basename(entrega.archivo.name)
        if (entrega.archivo and entrega.archivo.name)
        else ''
    )

    return render(
        request,
        'hechos/entregar_actividad_estudiante.html',
        {
            'form': form,
            'curso': curso,
            'actividad': actividad,
            'entrega': entrega,
            'volver_url': f'{volver}#actividades',
            'user_sede': user_sede,
            'entrega_archivo_basename': archivo_basename,
        },
    )


@login_required
def descargar_archivo_entrega_actividad(request, curso_id, actividad_id):
    """Descarga el archivo de la entrega del estudiante (forzar adjunto, misma autorización que entregar)."""
    if not hasattr(request.user, 'estudiante_profile'):
        raise Http404
    user_sede = get_user_sede(request.user)
    if not user_sede:
        raise Http404
    estudiante = request.user.estudiante_profile
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    if not _estudiante_matriculado_en_curso(curso, estudiante, user_sede):
        raise Http404
    escuela = curso.escuela
    if not escuela:
        raise Http404
    actividad = get_object_or_404(
        ActividadEscuela,
        id=actividad_id,
        escuela=escuela,
        sede=user_sede,
        is_active=True,
    )
    entrega = get_object_or_404(
        EntregaActividad,
        actividad=actividad,
        estudiante=estudiante,
        sede=user_sede,
    )
    if not entrega.archivo or not entrega.archivo.name:
        raise Http404
    fname = os.path.basename(entrega.archivo.name)
    try:
        fh = entrega.archivo.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    return FileResponse(fh, as_attachment=True, filename=fname)


@login_required
def profesor_actividad_entregas(request, escuela_id, actividad_id):
    """Lista entregas de una actividad y permite evaluar (puntaje + comentario)."""
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden revisar entregas.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')
    prof = request.user.profesor_profile
    actividad = get_object_or_404(
        ActividadEscuela.objects.select_related('escuela'),
        id=actividad_id,
        escuela_id=escuela_id,
        sede=user_sede,
        escuela__maestro=prof,
        is_active=True,
    )
    volver = reverse('hechos:escuela_crear_actividad', kwargs={'escuela_id': escuela_id})

    failed_entrega_id = None
    failed_form = None
    if request.method == 'POST' and request.POST.get('action') == 'evaluar':
        entrega = get_object_or_404(
            EntregaActividad.objects.select_related('estudiante__user'),
            id=request.POST.get('entrega_id'),
            actividad=actividad,
            sede=user_sede,
        )
        prefix = f'e{entrega.id}'
        form = ProfesorEvaluaEntregaForm(
            request.POST, instance=entrega, actividad=actividad, prefix=prefix,
        )
        if form.is_valid():
            obj = form.save(commit=False)
            obj.evaluado_en = timezone.now()
            obj.evaluado_por = prof
            obj.save()
            messages.success(
                request,
                f'Evaluación guardada para {entrega.estudiante.user.get_full_name()}.',
            )
            return redirect('hechos:profesor_actividad_entregas', escuela_id=escuela_id, actividad_id=actividad_id)
        messages.error(request, 'Revisa el puntaje o el comentario.')
        failed_entrega_id = entrega.id
        failed_form = form

    entregas = (
        EntregaActividad.objects.filter(actividad=actividad, sede=user_sede)
        .select_related('estudiante__user')
        .order_by('estudiante__user__last_name', 'estudiante__user__first_name')
    )
    entregas_rows = []
    for e in entregas:
        if failed_form is not None and e.id == failed_entrega_id:
            frm = failed_form
        else:
            frm = ProfesorEvaluaEntregaForm(
                instance=e, actividad=actividad, prefix=f'e{e.id}',
            )
        entregas_rows.append({'entrega': e, 'form': frm})

    return render(
        request,
        'hechos/profesor_actividad_entregas.html',
        {
            'actividad': actividad,
            'escuela': actividad.escuela,
            'entregas_rows': entregas_rows,
            'volver_url': volver,
            'user_sede': user_sede,
        },
    )


@login_required
def profesor_descargar_entrega_archivo(request, escuela_id, actividad_id, entrega_id):
    """
    Sirve el archivo de evidencia de una entrega (solo el maestro de la escuela).
    Fuerza descarga con nombre de archivo legible.
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden descargar entregas.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')
    prof = request.user.profesor_profile
    entrega = get_object_or_404(
        EntregaActividad.objects.select_related('actividad__escuela'),
        id=entrega_id,
        actividad_id=actividad_id,
        actividad__escuela_id=escuela_id,
        sede=user_sede,
        actividad__escuela__maestro=prof,
    )
    if not entrega.archivo or not entrega.archivo.name:
        raise Http404('Esta entrega no tiene archivo.')
    try:
        file_handle = entrega.archivo.open('rb')
    except FileNotFoundError:
        raise Http404('El archivo ya no está en el servidor.')
    filename = os.path.basename(entrega.archivo.name)
    return FileResponse(
        file_handle,
        as_attachment=True,
        filename=filename or 'entrega',
    )


@login_required
def escuela_archivos(request, escuela_id):
    """Subir y administrar materiales de la escuela (docente asignado)."""
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    prof = request.user.profesor_profile
    escuela = get_object_or_404(
        Escuela,
        id=escuela_id,
        sede=user_sede,
        maestro=prof,
        is_active=True,
    )
    volver_url = f"{reverse('hechos:mis_escuelas_profesor')}?escuela={escuela.id}"

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'eliminar':
            ar = get_object_or_404(
                ArchivoRecursoEscuela,
                id=request.POST.get('archivo_id'),
                escuela=escuela,
                sede=user_sede,
            )
            ar.is_active = False
            ar.save()
            messages.success(request, f'Se quitó «{ar.titulo}» de los recursos visibles.')
            return redirect('hechos:escuela_archivos', escuela_id=escuela.id)

        form = ArchivoRecursoEscuelaForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.sede = user_sede
            obj.escuela = escuela
            obj.subido_por = prof
            try:
                mr = str(settings.MEDIA_ROOT)
                os.makedirs(mr, exist_ok=True)
                os.makedirs(os.path.join(mr, 'recursos_escuela'), exist_ok=True)
                obj.save()
            except OSError as exc:
                messages.error(
                    request,
                    f'No se pudo guardar el archivo en el servidor. Detalle: {exc}',
                )
            else:
                messages.success(request, f'Recurso «{obj.titulo}» publicado para los estudiantes.')
            return redirect('hechos:escuela_archivos', escuela_id=escuela.id)
        messages.error(request, 'Revisa el formulario: título y archivo son obligatorios.')
    else:
        form = ArchivoRecursoEscuelaForm()

    archivos = (
        ArchivoRecursoEscuela.objects.filter(escuela=escuela, sede=user_sede, is_active=True)
        .select_related('subido_por__user')
        .order_by('-created_at')
    )
    return render(
        request,
        'hechos/escuela_archivos_modern.html',
        {
            'escuela': escuela,
            'form': form,
            'archivos': archivos,
            'volver_url': volver_url,
            'user_sede': user_sede,
        },
    )


@login_required
def estudiante_escuela_recursos(request, escuela_id):
    """Lista de archivos de la escuela para estudiantes matriculados en algún curso de esa escuela."""
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver recursos de escuela.')
        return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')
    estudiante = request.user.estudiante_profile
    escuela = get_object_or_404(
        Escuela,
        id=escuela_id,
        sede=user_sede,
        is_active=True,
    )
    if not _estudiante_matriculado_en_escuela(estudiante, escuela, user_sede):
        messages.error(request, 'No tienes acceso a los recursos de esta escuela.')
        return redirect('hechos:mis_escuelas')

    archivos = (
        ArchivoRecursoEscuela.objects.filter(escuela=escuela, sede=user_sede, is_active=True)
        .select_related('subido_por__user')
        .order_by('-created_at')
    )
    return render(
        request,
        'hechos/estudiante_escuela_recursos.html',
        {
            'escuela': escuela,
            'archivos': archivos,
            'user_sede': user_sede,
        },
    )


@login_required
def descargar_archivo_recurso_escuela(request, escuela_id, archivo_id):
    """Descarga segura: maestro de la escuela o estudiante matriculado en la escuela."""
    user_sede = get_user_sede(request.user)
    if not user_sede:
        raise Http404
    ar = get_object_or_404(
        ArchivoRecursoEscuela.objects.select_related('escuela'),
        id=archivo_id,
        escuela_id=escuela_id,
        sede=user_sede,
        is_active=True,
    )
    esc = ar.escuela
    permitido = False
    if hasattr(request.user, 'profesor_profile'):
        prof = request.user.profesor_profile
        if esc.maestro_id == prof.id and esc.sede_id == user_sede.id:
            permitido = True
    elif hasattr(request.user, 'estudiante_profile'):
        if _estudiante_matriculado_en_escuela(request.user.estudiante_profile, esc, user_sede):
            permitido = True
    if not permitido:
        raise Http404
    if not ar.archivo or not ar.archivo.name:
        raise Http404
    fname = os.path.basename(ar.archivo.name)
    try:
        fh = ar.archivo.open('rb')
    except FileNotFoundError:
        raise Http404 from None
    return FileResponse(
        fh,
        as_attachment=True,
        filename=fname or 'recurso',
    )


@login_required
def sesion_actividad(request, clase_id):
    """Reserva de pantalla: crear actividad ligada a la sesión (pendiente de implementar)."""
    return _sesion_herramienta_placeholder(
        request,
        clase_id,
        titulo='Crear actividad',
        texto_ayuda=(
            'Aquí podrás crear actividades para esta sesión (por ejemplo tareas o ejercicios). '
            'La función está en preparación.'
        ),
    )


@login_required
def sesion_archivos(request, clase_id):
    """Reserva de pantalla: materiales de la sesión (pendiente de implementar)."""
    return _sesion_herramienta_placeholder(
        request,
        clase_id,
        titulo='Subir archivos',
        texto_ayuda=(
            'Aquí podrás subir archivos y materiales para los estudiantes de esta sesión. '
            'La función está en preparación.'
        ),
    )


@login_required
def notas_estudiante(request):
    """
    Notas del estudiante
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver sus notas.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    estudiante = request.user.estudiante_profile
    
    # Obtener matrículas activas
    matriculas_activas = Matricula.objects.filter(
        estudiante=estudiante,
        sede=user_sede,
        is_active=True
    ).select_related('edicion_curso__curso__ruta_estudio', 'edicion_curso__profesor__user')
    
    # Obtener todas las notas del estudiante
    notas = Nota.objects.filter(estudiante=estudiante, sede=user_sede).select_related('curso', 'profesor__user').order_by('-fecha_evaluacion')
    
    # Calcular promedio general
    promedio_general = 0
    if notas.exists():
        promedio_general = sum(nota.puntaje_obtenido for nota in notas) / notas.count()
    
    # Procesar cursos matriculados con sus datos
    cursos_matriculados = []
    cursos_aprobados = []
    cursos_en_progreso = []
    
    for matricula in matriculas_activas:
        curso = matricula.edicion_curso.curso
        
        # Obtener notas del curso
        notas_curso = notas.filter(curso=curso)
        
        # Calcular promedio del curso
        promedio_curso = 0
        if notas_curso.exists():
            promedio_curso = sum(nota.puntaje_obtenido for nota in notas_curso) / notas_curso.count()
        
        # Determinar estado del curso (aprobado con 3.5/5.0 o más)
        estado = 'en_progreso'
        if promedio_curso >= 3.5:  # 3.5/5.0 = 70%
            estado = 'aprobado'
            cursos_aprobados.append(curso)
        else:
            cursos_en_progreso.append(curso)
        
        # Obtener asistencia del curso
        from hechos.models import Asistencia
        total_asistencias = Asistencia.objects.filter(
            estudiante=estudiante,
            clase__edicion_curso__curso=curso,
            sede=user_sede
        ).count()
        
        asistencias_presentes = Asistencia.objects.filter(
            estudiante=estudiante,
            clase__edicion_curso__curso=curso,
            sede=user_sede,
            estado='presente'
        ).count()
        
        porcentaje_asistencia = (asistencias_presentes / total_asistencias * 100) if total_asistencias > 0 else 0
        
        # Obtener clases del curso
        from hechos.models import Clase
        total_clases = Clase.objects.filter(
            edicion_curso__curso=curso,
            sede=user_sede
        ).count()
        
        curso_data = {
            'curso': curso,
            'matricula': matricula,
            'notas_curso': notas_curso,
            'promedio_curso': round(promedio_curso, 2),
            'estado': estado,
            'porcentaje_asistencia': round(porcentaje_asistencia, 1),
            'total_asistencias': total_asistencias,
            'asistencias_presentes': asistencias_presentes,
            'total_clases': total_clases,
            'progreso_curso': min(100, (asistencias_presentes / total_clases * 100)) if total_clases > 0 else 0
        }
        
        cursos_matriculados.append(curso_data)
    
    context = {
        'estudiante': estudiante,
        'notas': notas,
        'cursos_matriculados': cursos_matriculados,
        'cursos_aprobados': cursos_aprobados,
        'cursos_en_progreso': cursos_en_progreso,
        'promedio_general': round(promedio_general, 2),
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/notas_estudiante_modern.html', context)


@login_required
def notas_estudiante_ruta(request, ruta_id):
    """
    Notas del estudiante por ruta de estudio específica
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver sus notas.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    estudiante = request.user.estudiante_profile
    
    # Obtener la ruta específica
    try:
        ruta = RutaEstudio.objects.get(id=ruta_id, sede=user_sede, is_active=True)
    except RutaEstudio.DoesNotExist:
        messages.error(request, 'La ruta de estudio no existe o no tienes acceso a ella.')
        return redirect('hechos:notas_estudiante')
    
    # Obtener cursos de la ruta
    cursos_ruta = Curso.objects.filter(
        ruta_estudio=ruta,
        sede=user_sede,
        is_active=True
    ).order_by('orden', 'nombre')
    
    # Obtener matrículas del estudiante en esta ruta
    matriculas_ruta = Matricula.objects.filter(
        estudiante=estudiante,
        edicion_curso__curso__ruta_estudio=ruta,
        sede=user_sede,
        is_active=True
    ).select_related('edicion_curso__curso', 'edicion_curso__profesor__user')
    
    # Obtener todas las notas del estudiante en esta ruta
    notas_ruta = Nota.objects.filter(
        estudiante=estudiante,
        curso__ruta_estudio=ruta,
        sede=user_sede
    ).select_related('curso', 'profesor__user').order_by('-fecha_evaluacion')
    
    # Calcular promedio de la ruta
    promedio_ruta = 0
    if notas_ruta.exists():
        promedio_ruta = sum(nota.puntaje_obtenido for nota in notas_ruta) / notas_ruta.count()
    
    # Procesar cada curso de la ruta
    cursos_con_datos = []
    cursos_completados = 0
    cursos_en_progreso = 0
    cursos_pendientes = 0
    
    for curso in cursos_ruta:
        # Verificar si está matriculado
        matricula_curso = matriculas_ruta.filter(edicion_curso__curso=curso).first()
        
        if matricula_curso:
            # Obtener notas del curso
            notas_curso = notas_ruta.filter(curso=curso)
            
            # Calcular promedio del curso
            promedio_curso = 0
            if notas_curso.exists():
                promedio_curso = sum(nota.puntaje_obtenido for nota in notas_curso) / notas_curso.count()
            
            # Determinar estado del curso (completado con 3.5/5.0 o más)
            estado = 'en_progreso'
            if promedio_curso >= 3.5:  # 3.5/5.0 = 70%
                estado = 'completado'
                cursos_completados += 1
            else:
                cursos_en_progreso += 1
            
            # Obtener asistencia del curso
            total_asistencias = Asistencia.objects.filter(
                estudiante=estudiante,
                clase__edicion_curso__curso=curso,
                sede=user_sede
            ).count()
            
            asistencias_presentes = Asistencia.objects.filter(
                estudiante=estudiante,
                clase__edicion_curso__curso=curso,
                sede=user_sede,
                estado='presente'
            ).count()
            
            porcentaje_asistencia = (asistencias_presentes / total_asistencias * 100) if total_asistencias > 0 else 0
            
            # Obtener clases del curso
            total_clases = Clase.objects.filter(
                edicion_curso__curso=curso,
                sede=user_sede
            ).count()
            
            curso_data = {
                'curso': curso,
                'matricula': matricula_curso,
                'notas_curso': notas_curso,
                'promedio_curso': round(promedio_curso, 2),
                'estado': estado,
                'porcentaje_asistencia': round(porcentaje_asistencia, 1),
                'total_asistencias': total_asistencias,
                'asistencias_presentes': asistencias_presentes,
                'total_clases': total_clases,
                'progreso_curso': min(100, (asistencias_presentes / total_clases * 100)) if total_clases > 0 else 0
            }
            
            cursos_con_datos.append(curso_data)
        else:
            # Curso no matriculado
            curso_data = {
                'curso': curso,
                'matricula': None,
                'notas_curso': [],
                'promedio_curso': 0,
                'estado': 'pendiente',
                'porcentaje_asistencia': 0,
                'total_asistencias': 0,
                'asistencias_presentes': 0,
                'total_clases': 0,
                'progreso_curso': 0
            }
            
            cursos_con_datos.append(curso_data)
            cursos_pendientes += 1
    
    # Calcular progreso general de la ruta
    total_cursos = cursos_ruta.count()
    progreso_ruta = (cursos_completados / total_cursos * 100) if total_cursos > 0 else 0
    
    context = {
        'estudiante': estudiante,
        'ruta': ruta,
        'cursos_con_datos': cursos_con_datos,
        'notas_ruta': notas_ruta,
        'promedio_ruta': round(promedio_ruta, 2),
        'cursos_completados': cursos_completados,
        'cursos_en_progreso': cursos_en_progreso,
        'cursos_pendientes': cursos_pendientes,
        'progreso_ruta': round(progreso_ruta, 1),
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/notas_estudiante_ruta_modern.html', context)


# ===== VISTAS DE CREACIÓN PARA ADMIN DE SEDE =====

@login_required
def crear_estudiante(request):
    """
    Crear nuevo estudiante (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            avatar_file = request.FILES.get('avatar')
            # Crear usuario
            user = User.objects.create_user(
                username=request.POST.get('username'),
                email=request.POST.get('email'),
                password=request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                sede=user_sede,
                avatar=avatar_file,
            )
            
            # Crear perfil de estudiante
            Estudiante.objects.create(
                user=user,
                sede=user_sede,
                telefono_emergencia=request.POST.get('telefono_emergencia', ''),
                contacto_emergencia=request.POST.get('contacto_emergencia', ''),
                direccion=request.POST.get('direccion', ''),
                iglesia=request.POST.get('iglesia', ''),
                fecha_nacimiento=request.POST.get('fecha_nacimiento') or None,
                notas_medicas=request.POST.get('notas_medicas', '')
            )
            
            messages.success(request, f'Estudiante {user.get_full_name()} creado exitosamente.')
            return redirect('hechos:estudiantes_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear estudiante: {str(e)}')
    
    context = {
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/crear_estudiante.html', context)


@login_required
def crear_profesor(request):
    """
    Crear nuevo profesor (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            email = (request.POST.get('email') or '').strip()
            username = generate_unique_username(User, email)
            # Crear usuario
            user = User.objects.create_user(
                username=username,
                email=email,
                password=request.POST.get('password'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                sede=user_sede,
                avatar=request.FILES.get('avatar'),
            )
            tel = (request.POST.get('telefono') or '').strip()
            if tel:
                user.phone = tel
                user.save(update_fields=['phone'])
            
            # Crear perfil de profesor
            Profesor.objects.create(
                user=user,
                sede=user_sede,
            )
            
            messages.success(request, f'Profesor {user.get_full_name()} creado exitosamente.')
            return redirect('hechos:profesores_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear profesor: {str(e)}')
    
    context = {
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/crear_profesor.html', context)


@login_required
def crear_ruta_estudio(request):
    """
    Crear nueva ruta de estudio (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        try:
            RutaEstudio.objects.create(
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion', ''),
                duracion_semanas=request.POST.get('duracion_semanas', 0) or 0,
                nivel=request.POST.get('nivel'),
                sede=user_sede
            )
            
            messages.success(request, f'Ruta de estudio "{request.POST.get("nombre")}" creada exitosamente.')
            return redirect('hechos:rutas_estudio_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear ruta de estudio: {str(e)}')
    
    context = {
        'user_sede': user_sede,
        'nivel_choices': [
            ('basico', 'Básico'),
            ('intermedio', 'Intermedio'),
            ('avanzado', 'Avanzado'),
        ],
    }
    
    return render(request, 'hechos/crear_ruta_estudio.html', context)


@login_required
def crear_curso(request):
    """
    Crear nuevo curso (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    # Obtener rutas de estudio y profesores disponibles
    rutas = RutaEstudio.objects.filter(sede=user_sede, is_active=True)
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True)
    
    if request.method == 'POST':
        try:
            ruta_id = request.POST.get('ruta_estudio')
            profesor_id = request.POST.get('profesor')
            
            ruta = RutaEstudio.objects.get(id=ruta_id, sede=user_sede)
            profesor = Profesor.objects.get(id=profesor_id, sede=user_sede)
            
            Curso.objects.create(
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion', ''),
                ruta_estudio=ruta,
                profesor=profesor,
                orden=request.POST.get('orden', 1) or 1,
                fecha_inicio=request.POST.get('fecha_inicio'),
                fecha_fin=request.POST.get('fecha_fin'),
                sede=user_sede
            )
            
            messages.success(request, f'Curso "{request.POST.get("nombre")}" creado exitosamente.')
            return redirect('hechos:cursos_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear curso: {str(e)}')
    
    context = {
        'user_sede': user_sede,
        'rutas': rutas,
        'profesores': profesores,
    }
    
    return render(request, 'hechos/crear_curso.html', context)


@login_required
def matricular_estudiante(request):
    """
    Matricular estudiante en curso (para admins y profesores)
    """
    allowed = (
        request.user.is_super_admin()
        or hasattr(request.user, 'profesor_profile')
        or (
            hasattr(request.user, 'admin_escuela_profile')
            and ca.has_capacidad(request.user, 'academico')
        )
    )
    if not allowed:
        messages.error(request, 'No tienes permisos para matricular estudiantes.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    # Obtener estudiantes y cursos disponibles
    estudiantes = Estudiante.objects.filter(sede=user_sede, is_active=True)
    
    # Filtrar cursos según el perfil del usuario
    if hasattr(request.user, 'profesor_profile'):
        # Profesor solo puede matricular en sus cursos (a través de ediciones)
        cursos = Curso.objects.filter(
            ediciones__profesor=request.user.profesor_profile,
            sede=user_sede,
            is_active=True
        ).distinct()
    else:
        # Admin puede matricular en todos los cursos
        cursos = Curso.objects.filter(sede=user_sede, is_active=True)
    
    if request.method == 'POST':
        try:
            estudiante_id = request.POST.get('estudiante')
            curso_id = request.POST.get('curso')
            edicion_id = request.POST.get('edicion')
            
            estudiante = Estudiante.objects.get(id=estudiante_id, sede=user_sede)
            curso = Curso.objects.get(id=curso_id, sede=user_sede)
            
            # Si es profesor, verificar que tenga ediciones de este curso
            if hasattr(request.user, 'profesor_profile'):
                edicion = EdicionCurso.objects.get(id=edicion_id, curso=curso, profesor=request.user.profesor_profile, is_active=True)
            else:
                # Admin puede usar cualquier edición del curso
                edicion = EdicionCurso.objects.get(id=edicion_id, curso=curso, is_active=True)
            
            # Verificar si ya está matriculado
            if Matricula.objects.filter(estudiante=estudiante, edicion_curso=edicion, sede=user_sede).exists():
                messages.warning(request, 'El estudiante ya está matriculado en esta edición del curso.')
            else:
                # Verificar cupo disponible
                if edicion.estudiantes_inscritos >= edicion.cupo_maximo:
                    messages.warning(request, f'No hay cupo disponible en la edición {edicion.nombre_edicion}.')
                else:
                    # Determinar el período automáticamente
                    periodo = get_current_period()
                    
                    Matricula.objects.create(
                        estudiante=estudiante,
                        edicion_curso=edicion,
                        sede=user_sede,
                        periodo=periodo,
                        fecha_matricula=request.POST.get('fecha_matricula') or timezone.now()
                    )
                    messages.success(request, f'Estudiante {estudiante.user.get_full_name()} matriculado exitosamente en {curso.nombre} - {edicion.nombre_edicion} para el período {get_period_display(periodo)}.')
                    return redirect('hechos:cursos_list')
            
        except Exception as e:
            messages.error(request, f'Error al matricular estudiante: {str(e)}')
    
    # Obtener ediciones para cada curso
    cursos_con_ediciones = []
    for curso in cursos:
        if hasattr(request.user, 'profesor_profile'):
            ediciones = EdicionCurso.objects.filter(
                curso=curso,
                profesor=request.user.profesor_profile,
                is_active=True
            )
        else:
            ediciones = EdicionCurso.objects.filter(
                curso=curso,
                is_active=True
            )
        
        cursos_con_ediciones.append({
            'curso': curso,
            'ediciones': ediciones
        })
    
    context = {
        'user_sede': user_sede,
        'estudiantes': estudiantes,
        'cursos': cursos,
        'cursos_con_ediciones': cursos_con_ediciones,
    }
    
    return render(request, 'hechos/matricular_estudiante.html', context)


# ===== VISTAS DE GESTIÓN PARA ADMIN DE SEDE =====

@login_required
def editar_estudiante(request, estudiante_id):
    """
    Editar estudiante existente (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    estudiante = get_object_or_404(Estudiante, id=estudiante_id, sede=user_sede)
    
    if request.method == 'POST':
        try:
            # Actualizar usuario
            estudiante.user.first_name = request.POST.get('first_name')
            estudiante.user.last_name = request.POST.get('last_name')
            estudiante.user.email = request.POST.get('email')
            if request.POST.get('password'):
                estudiante.user.set_password(request.POST.get('password'))
            estudiante.user.save()
            
            # Actualizar perfil de estudiante
            estudiante.telefono = request.POST.get('telefono', '')
            estudiante.direccion = request.POST.get('direccion', '')
            estudiante.fecha_nacimiento = request.POST.get('fecha_nacimiento') or None
            estudiante.save()
            
            messages.success(request, f'Estudiante {estudiante.user.get_full_name()} actualizado exitosamente.')
            return redirect('hechos:estudiantes_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar estudiante: {str(e)}')
    
    context = {
        'estudiante': estudiante,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/editar_estudiante.html', context)


@login_required
def editar_profesor(request, profesor_id):
    """
    Editar profesor existente (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = get_object_or_404(Profesor, id=profesor_id, sede=user_sede)
    
    if request.method == 'POST':
        try:
            # Actualizar usuario
            profesor.user.first_name = request.POST.get('first_name')
            profesor.user.last_name = request.POST.get('last_name')
            profesor.user.email = request.POST.get('email')
            if request.POST.get('password'):
                profesor.user.set_password(request.POST.get('password'))
            tel = (request.POST.get('telefono') or '').strip()
            profesor.user.phone = tel
            profesor.user.save()

            messages.success(request, f'Profesor {profesor.user.get_full_name()} actualizado exitosamente.')
            return redirect('hechos:profesores_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar profesor: {str(e)}')
    
    context = {
        'profesor': profesor,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/editar_profesor.html', context)


@login_required
def editar_curso(request, curso_id):
    """
    Editar curso existente (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede)
    rutas = RutaEstudio.objects.filter(sede=user_sede, is_active=True)
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True)
    
    if request.method == 'POST':
        try:
            ruta_id = request.POST.get('ruta_estudio')
            profesor_id = request.POST.get('profesor')
            
            ruta = RutaEstudio.objects.get(id=ruta_id, sede=user_sede)
            profesor = Profesor.objects.get(id=profesor_id, sede=user_sede)
            
            curso.nombre = request.POST.get('nombre')
            curso.descripcion = request.POST.get('descripcion', '')
            curso.ruta_estudio = ruta
            curso.profesor = profesor
            curso.orden = request.POST.get('orden', 1) or 1
            curso.fecha_inicio = request.POST.get('fecha_inicio')
            curso.fecha_fin = request.POST.get('fecha_fin')
            curso.save()
            
            messages.success(request, f'Curso "{curso.nombre}" actualizado exitosamente.')
            return redirect('hechos:cursos_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar curso: {str(e)}')
    
    context = {
        'curso': curso,
        'rutas': rutas,
        'profesores': profesores,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/editar_curso.html', context)


@login_required
def editar_ruta_estudio(request, ruta_id):
    """
    Editar ruta de estudio existente (solo para admins)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    ruta = get_object_or_404(RutaEstudio, id=ruta_id, sede=user_sede)
    
    if request.method == 'POST':
        try:
            ruta.nombre = request.POST.get('nombre')
            ruta.descripcion = request.POST.get('descripcion', '')
            ruta.duracion_semanas = request.POST.get('duracion_semanas', 0) or 0
            ruta.nivel = request.POST.get('nivel')
            ruta.save()
            
            messages.success(request, f'Ruta de estudio "{ruta.nombre}" actualizada exitosamente.')
            return redirect('hechos:rutas_estudio_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar ruta de estudio: {str(e)}')
    
    context = {
        'ruta': ruta,
        'user_sede': user_sede,
        'nivel_choices': [
            ('basico', 'Básico'),
            ('intermedio', 'Intermedio'),
            ('avanzado', 'Avanzado'),
        ],
    }
    
    return render(request, 'hechos/editar_ruta_estudio.html', context)


@login_required
def eliminar_estudiante(request, estudiante_id):
    """
    Eliminar estudiante (soft delete)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    estudiante = get_object_or_404(Estudiante, id=estudiante_id, sede=user_sede)
    
    if request.method == 'POST':
        estudiante.is_active = False
        estudiante.save()
        messages.success(request, f'Estudiante {estudiante.user.get_full_name()} eliminado exitosamente.')
        return redirect('hechos:estudiantes_list')
    
    context = {
        'estudiante': estudiante,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/eliminar_estudiante.html', context)


@login_required
def eliminar_profesor(request, profesor_id):
    """
    Eliminar profesor (soft delete)
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = get_object_or_404(Profesor, id=profesor_id, sede=user_sede)
    
    if request.method == 'POST':
        profesor.is_active = False
        profesor.save()
        messages.success(request, f'Profesor {profesor.user.get_full_name()} eliminado exitosamente.')
        return redirect('hechos:profesores_list')
    
    context = {
        'profesor': profesor,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/eliminar_profesor.html', context)


@login_required
def eliminar_curso(request, curso_id):
    """
    Eliminar curso (soft delete)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede)
    
    if request.method == 'POST':
        curso.is_active = False
        curso.save()
        messages.success(request, f'Curso "{curso.nombre}" eliminado exitosamente.')
        return redirect('hechos:cursos_list')
    
    context = {
        'curso': curso,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/eliminar_curso.html', context)


@login_required
def eliminar_ruta_estudio(request, ruta_id):
    """
    Eliminar ruta de estudio (soft delete)
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    ruta = get_object_or_404(RutaEstudio, id=ruta_id, sede=user_sede)
    
    if request.method == 'POST':
        ruta.is_active = False
        ruta.save()
        messages.success(request, f'Ruta de estudio "{ruta.nombre}" eliminada exitosamente.')
        return redirect('hechos:rutas_estudio_list')
    
    context = {
        'ruta': ruta,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/eliminar_ruta_estudio.html', context)


@login_required
def detalle_estudiante(request, estudiante_id):
    """
    Ver detalles completos del estudiante
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    estudiante = get_object_or_404(Estudiante, id=estudiante_id, sede=user_sede)
    matriculas = Matricula.objects.filter(estudiante=estudiante, sede=user_sede, is_active=True)
    notas = Nota.objects.filter(estudiante=estudiante, sede=user_sede).order_by('-fecha_evaluacion')[:10]
    
    context = {
        'estudiante': estudiante,
        'matriculas': matriculas,
        'notas': notas,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/detalle_estudiante.html', context)


@login_required
def detalle_profesor(request, profesor_id):
    """
    Ver detalles completos del profesor
    """
    if not request.user.is_super_admin():
        r = ca.require_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = get_object_or_404(Profesor, id=profesor_id, sede=user_sede)
    # Obtener cursos a través de ediciones
    cursos = Curso.objects.filter(
        ediciones__profesor=profesor,
        sede=user_sede,
        is_active=True
    ).distinct()
    clases = Clase.objects.filter(profesor=profesor, sede=user_sede, is_active=True).order_by('-fecha_clase')[:10]
    
    context = {
        'profesor': profesor,
        'cursos': cursos,
        'clases': clases,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/detalle_profesor.html', context)


@login_required
def detalle_curso(request, curso_id):
    """
    Ver detalles completos del curso
    """
    if (
        hasattr(request.user, 'estudiante_profile')
        and request.resolver_match
        and request.resolver_match.url_name == 'detalle_curso'
    ):
        return redirect('hechos:detalle_mis_escuela', curso_id=curso_id)

    allowed = (
        request.user.is_super_admin()
        or hasattr(request.user, 'estudiante_profile')
        or hasattr(request.user, 'profesor_profile')
        or (
            hasattr(request.user, 'admin_escuela_profile')
            and ca.has_any_capacidad(request.user, ('academico', 'pedagogico'))
        )
    )
    if not allowed:
        messages.error(request, 'No tienes permisos para ver detalles de cursos.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede)
    
    if hasattr(request.user, 'estudiante_profile'):
        estudiante = request.user.estudiante_profile
        matricula = Matricula.objects.filter(
            estudiante=estudiante,
            edicion_curso__curso=curso,
            sede=user_sede,
            is_active=True,
        ).select_related('edicion_curso__profesor__user').first()
        if not matricula:
            messages.error(request, 'No tienes acceso a este curso.')
            return redirect('hechos:mis_escuelas')

        clases = Clase.objects.filter(
            edicion_curso=matricula.edicion_curso,
            sede=user_sede,
            is_active=True,
        ).order_by('fecha_clase')
        notas_curso = Nota.objects.filter(
            curso=curso,
            estudiante=estudiante,
            sede=user_sede,
        ).order_by('-fecha_evaluacion')
        promedio = notas_curso.aggregate(promedio=Avg('puntaje_obtenido'))['promedio'] or 0
        escuela = curso.escuela
        if escuela:
            actividades_qs = ActividadEscuela.objects.filter(
                escuela=escuela,
                sede=user_sede,
                is_active=True,
            ).order_by('-created_at')
            actividades_list = list(actividades_qs)
            act_ids = [a.id for a in actividades_list]
            entregas_map = {
                e.actividad_id: e
                for e in EntregaActividad.objects.filter(
                    estudiante=estudiante,
                    sede=user_sede,
                    actividad_id__in=act_ids,
                )
            }
            ahora = timezone.now()
            actividades_con_entrega = []
            for a in actividades_list:
                ent = entregas_map.get(a.id)
                plazo_vencido = bool(a.fecha_limite and ahora > a.fecha_limite)
                limite_ok = not plazo_vencido
                puede_entregar = limite_ok and (not ent or not ent.evaluado_en)
                actividades_con_entrega.append(
                    {
                        'actividad': a,
                        'entrega': ent,
                        'puede_entregar': puede_entregar,
                        'plazo_vencido': plazo_vencido,
                    }
                )
            actividades_escuela = actividades_qs
            recursos_con_archivo = actividades_qs.exclude(
                Q(material_adjunto='') | Q(material_adjunto__isnull=True)
            )
            archivos_recurso_escuela = list(
                ArchivoRecursoEscuela.objects.filter(
                    escuela=escuela,
                    sede=user_sede,
                    is_active=True,
                )
                .select_related('subido_por__user')
                .order_by('-created_at')
            )
        else:
            actividades_escuela = ActividadEscuela.objects.none()
            recursos_con_archivo = ActividadEscuela.objects.none()
            actividades_con_entrega = []
            archivos_recurso_escuela = []
        context = {
            'curso': curso,
            'matricula': matricula,
            'clases': clases,
            'notas_curso': notas_curso,
            'promedio_general': round(promedio, 2),
            'total_clases': clases.count(),
            'total_notas': notas_curso.count(),
            'user_sede': user_sede,
            'escuela': escuela,
            'actividades_escuela': actividades_escuela,
            'actividades_con_entrega': actividades_con_entrega,
            'recursos_con_archivo': recursos_con_archivo,
            'archivos_recurso_escuela': archivos_recurso_escuela,
        }
        return render(request, 'hechos/detalle_curso_estudiante.html', context)

    # Si es profesor, verificar que tenga ediciones de este curso
    if hasattr(request.user, 'profesor_profile'):
        if not EdicionCurso.objects.filter(curso=curso, profesor=request.user.profesor_profile, is_active=True).exists():
            messages.error(request, 'No tienes permisos para acceder a este curso.')
            return redirect('hechos:cursos_list')
    
    # Obtener matrículas según el perfil del usuario
    if hasattr(request.user, 'profesor_profile'):
        # Profesor ve solo estudiantes de sus ediciones
        matriculas = Matricula.objects.filter(
            edicion_curso__curso=curso,
            edicion_curso__profesor=request.user.profesor_profile,
            sede=user_sede,
            is_active=True
        ).select_related('estudiante__user', 'edicion_curso')
        clases = Clase.objects.filter(
            edicion_curso__curso=curso,
            edicion_curso__profesor=request.user.profesor_profile,
            sede=user_sede,
            is_active=True
        ).order_by('fecha_clase')
    else:
        # Admin ve todas las matrículas del curso
        matriculas = Matricula.objects.filter(edicion_curso__curso=curso, sede=user_sede, is_active=True).select_related('estudiante__user', 'edicion_curso')
        clases = Clase.objects.filter(edicion_curso__curso=curso, sede=user_sede, is_active=True).order_by('fecha_clase')
    
    # Calcular estadísticas para el contexto
    total_estudiantes = matriculas.count()
    total_clases = clases.count()
    
    notas_qs = Nota.objects.filter(
        curso=curso,
        sede=user_sede
    ).select_related('estudiante__user').order_by('-fecha_evaluacion')

    promedio_general = notas_qs.aggregate(
        promedio=Avg('puntaje_obtenido')
    )['promedio'] or 0

    estudiantes_con_notas = []
    for matricula in matriculas:
        notas_estudiante = notas_qs.filter(estudiante=matricula.estudiante)
        
        # Calcular promedio del estudiante
        if notas_estudiante.exists():
            promedio_estudiante = notas_estudiante.aggregate(
                promedio=Avg('puntaje_obtenido')
            )['promedio'] or 0
        else:
            promedio_estudiante = 0
        
        estudiantes_con_notas.append({
            'matricula': matricula,
            'promedio': round(promedio_estudiante, 2),
            'total_notas': notas_estudiante.count(),
            'notas': notas_estudiante[:3]  # Últimas 3 notas
        })
    
    context = {
        'curso': curso,
        'matriculas': matriculas,
        'clases': clases,
        'estudiantes_con_notas': estudiantes_con_notas,
        'total_estudiantes': total_estudiantes,
        'total_clases': total_clases,
        'promedio_general': round(promedio_general, 2),
        'user_sede': user_sede,
    }

    return render(request, 'hechos/detalle_curso.html', context)


@login_required
def tomar_asistencia_curso(request, curso_id):
    """
    Tomar asistencia semanal para un curso específico
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden tomar asistencia.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = request.user.profesor_profile
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    
    # Verificar que el profesor tenga ediciones de este curso
    if not EdicionCurso.objects.filter(curso=curso, profesor=profesor, is_active=True).exists():
        messages.error(request, 'No tienes permisos para acceder a este curso.')
        return redirect('hechos:cursos_list')
    
    # Obtener estudiantes matriculados en las ediciones del profesor
    estudiantes = Estudiante.objects.filter(
        matriculas__edicion_curso__curso=curso,
        matriculas__edicion_curso__profesor=profesor,
        matriculas__sede=user_sede,
        matriculas__is_active=True,
        sede=user_sede,
        is_active=True
    ).distinct().select_related('user')
    
    # Obtener fecha actual para la asistencia
    fecha_actual = timezone.now().date()
    
    # Crear o obtener una clase para la asistencia semanal
    clase_semanal, created = Clase.objects.get_or_create(
        edicion_curso__curso=curso,
        edicion_curso__profesor=profesor,
        fecha_clase__date=fecha_actual,
        sede=user_sede,
        defaults={
            'edicion_curso': EdicionCurso.objects.filter(
                curso=curso, 
                profesor=profesor, 
                is_active=True
            ).first(),
            'numero_clase': 1,
            'titulo': f'Clase Semanal - {fecha_actual.strftime("%d/%m/%Y")}',
            'descripcion': 'Asistencia semanal del curso',
            'fecha_clase': timezone.now(),
            'profesor': profesor
        }
    )
    
    # Obtener asistencias existentes para esta clase
    asistencias_existentes = Asistencia.objects.filter(
        clase=clase_semanal,
        sede=user_sede
    ).select_related('estudiante__user')
    
    asistencia_dict = {a.estudiante.id: a.estado for a in asistencias_existentes}
    
    if request.method == 'POST':
        # Procesar asistencia
        for key, value in request.POST.items():
            if key.startswith('estudiante_'):
                estudiante_id = key.split('_')[1]
                try:
                    estudiante = Estudiante.objects.get(id=estudiante_id, sede=user_sede)
                    asistencia, created = Asistencia.objects.get_or_create(
                        clase=clase_semanal,
                        estudiante=estudiante,
                        sede=user_sede,
                        defaults={
                            'estado': value,
                            'registrado_por': request.user
                        }
                    )
                    if not created:
                        asistencia.estado = value
                        asistencia.registrado_por = request.user
                        asistencia.save()
                except Estudiante.DoesNotExist:
                    continue
        
        messages.success(request, f'Asistencia registrada correctamente para el {fecha_actual.strftime("%d/%m/%Y")}.')
        return redirect('hechos:tomar_asistencia_curso', curso_id=curso_id)
    
    # Obtener historial de asistencias (últimas 5 fechas)
    historial_asistencias = Clase.objects.filter(
        edicion_curso__curso=curso,
        edicion_curso__profesor=profesor,
        sede=user_sede,
        is_active=True
    ).values('fecha_clase__date').distinct().order_by('-fecha_clase__date')[:5]
    
    # Preparar datos de estudiantes con asistencia
    estudiantes_con_asistencia = []
    for estudiante in estudiantes:
        estado_asistencia = asistencia_dict.get(estudiante.id, 'presente')  # Default a presente
        estudiantes_con_asistencia.append({
            'estudiante': estudiante,
            'estado_asistencia': estado_asistencia
        })
    
    context = {
        'curso': curso,
        'estudiantes': estudiantes,
        'estudiantes_con_asistencia': estudiantes_con_asistencia,
        'asistencia_dict': asistencia_dict,
        'fecha_actual': fecha_actual,
        'historial_asistencias': historial_asistencias,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/tomar_asistencia_curso.html', context)




@login_required
def matriculas_list(request):
    """
    Lista de matrículas para administradores de sede con filtros y agrupación
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    # Obtener parámetros de filtro
    filtro_curso = request.GET.get('curso', '')
    filtro_estado = request.GET.get('estado', '')
    filtro_ruta = request.GET.get('ruta', '')
    filtro_periodo = request.GET.get('periodo', '')
    agrupar_por = request.GET.get('agrupar', 'fecha')  # fecha, curso, ruta, estudiante, periodo
    
    # Obtener todas las matrículas de la sede
    matriculas = Matricula.objects.filter(
        sede=user_sede
    ).select_related(
        'estudiante__user', 
        'edicion_curso__curso__ruta_estudio', 
        'edicion_curso__profesor__user'
    ).order_by('-periodo', '-fecha_matricula')
    
    # Aplicar filtros
    if filtro_curso:
        matriculas = matriculas.filter(edicion_curso__curso__id=filtro_curso)
    
    if filtro_estado:
        if filtro_estado == 'activa':
            matriculas = matriculas.filter(is_active=True)
        elif filtro_estado == 'inactiva':
            matriculas = matriculas.filter(is_active=False)
    
    if filtro_ruta:
        matriculas = matriculas.filter(edicion_curso__curso__ruta_estudio__id=filtro_ruta)
    
    if filtro_periodo:
        matriculas = matriculas.filter(periodo=filtro_periodo)
    
    # Ordenar según agrupación
    if agrupar_por == 'curso':
        matriculas = matriculas.order_by('edicion_curso__curso__nombre', '-fecha_matricula')
    elif agrupar_por == 'ruta':
        matriculas = matriculas.order_by('edicion_curso__curso__ruta_estudio__nombre', 'edicion_curso__curso__orden', '-fecha_matricula')
    elif agrupar_por == 'estudiante':
        matriculas = matriculas.order_by('estudiante__user__first_name', 'estudiante__user__last_name', '-fecha_matricula')
    elif agrupar_por == 'periodo':
        matriculas = matriculas.order_by('-periodo', 'estudiante__user__first_name')
    else:  # fecha
        matriculas = matriculas.order_by('-fecha_matricula')
    
    # Estadísticas
    matriculas_activas = matriculas.filter(is_active=True)
    matriculas_en_progreso = matriculas_activas.filter(
        edicion_curso__fecha_inicio__lte=timezone.now().date(),
        edicion_curso__fecha_fin__gte=timezone.now().date()
    )
    cursos_unicos = Curso.objects.filter(
        ediciones__matriculas__in=matriculas_activas,
        sede=user_sede
    ).distinct()
    
    # Obtener opciones para filtros
    cursos_disponibles = Curso.objects.filter(sede=user_sede, is_active=True).order_by('nombre')
    rutas_disponibles = RutaEstudio.objects.filter(sede=user_sede, is_active=True).order_by('nombre')
    periodos_disponibles = Matricula.objects.filter(sede=user_sede).values_list('periodo', flat=True).distinct().order_by('-periodo')
    
    # Agrupar matrículas según el parámetro
    matriculas_agrupadas = {}
    if agrupar_por == 'curso':
        for matricula in matriculas:
            curso_nombre = matricula.edicion_curso.curso.nombre
            if curso_nombre not in matriculas_agrupadas:
                matriculas_agrupadas[curso_nombre] = []
            matriculas_agrupadas[curso_nombre].append(matricula)
    elif agrupar_por == 'ruta':
        for matricula in matriculas:
            ruta_nombre = matricula.edicion_curso.curso.ruta_estudio.nombre if matricula.edicion_curso.curso.ruta_estudio else 'Sin ruta'
            if ruta_nombre not in matriculas_agrupadas:
                matriculas_agrupadas[ruta_nombre] = []
            matriculas_agrupadas[ruta_nombre].append(matricula)
    elif agrupar_por == 'estudiante':
        for matricula in matriculas:
            estudiante_nombre = matricula.estudiante.user.get_full_name()
            if estudiante_nombre not in matriculas_agrupadas:
                matriculas_agrupadas[estudiante_nombre] = []
            matriculas_agrupadas[estudiante_nombre].append(matricula)
    elif agrupar_por == 'periodo':
        for matricula in matriculas:
            periodo_display = get_period_display(matricula.periodo)
            if periodo_display not in matriculas_agrupadas:
                matriculas_agrupadas[periodo_display] = []
            matriculas_agrupadas[periodo_display].append(matricula)
    else:  # fecha
        for matricula in matriculas:
            fecha_str = matricula.fecha_matricula.strftime('%Y-%m-%d')
            if fecha_str not in matriculas_agrupadas:
                matriculas_agrupadas[fecha_str] = []
            matriculas_agrupadas[fecha_str].append(matricula)
    
    context = {
        'matriculas': matriculas,
        'matriculas_agrupadas': matriculas_agrupadas,
        'matriculas_activas': matriculas_activas,
        'matriculas_en_progreso': matriculas_en_progreso,
        'cursos_unicos': cursos_unicos,
        'cursos_disponibles': cursos_disponibles,
        'rutas_disponibles': rutas_disponibles,
        'periodos_disponibles': periodos_disponibles,
        'user_sede': user_sede,
        'filtro_curso': filtro_curso,
        'filtro_estado': filtro_estado,
        'filtro_ruta': filtro_ruta,
        'filtro_periodo': filtro_periodo,
        'agrupar_por': agrupar_por,
    }
    
    return render(request, 'hechos/matriculas_list.html', context)


@login_required
def desmatricular_estudiante(request, matricula_id):
    """
    Desmatricular estudiante de un curso
    """
    if not request.user.is_super_admin():
        r = ca.require_academico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    try:
        matricula = Matricula.objects.get(id=matricula_id, sede=user_sede)
    except Matricula.DoesNotExist:
        messages.error(request, 'Matrícula no encontrada.')
        return redirect('hechos:matriculas_list')
    
    if request.method == 'POST':
        try:
            matricula.is_active = False
            matricula.save()
            messages.success(request, f'Estudiante {matricula.estudiante.user.get_full_name()} desmatriculado exitosamente del curso {matricula.curso.nombre}.')
            return redirect('hechos:matriculas_list')
        except Exception as e:
            messages.error(request, f'Error al desmatricular estudiante: {str(e)}')
    
    context = {
        'matricula': matricula,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/desmatricular_estudiante.html', context)


# ===== VISTAS PARA GESTIONAR EDICIONES DE CURSOS =====

@login_required
def ediciones_curso_list(request, curso_id):
    """
    Lista de ediciones de un curso específico
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    ediciones = EdicionCurso.objects.filter(curso=curso, is_active=True).select_related('profesor__user')
    
    context = {
        'curso': curso,
        'ediciones': ediciones,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/ediciones_curso_list.html', context)


@login_required
def crear_edicion_curso(request, curso_id):
    """
    Crear nueva edición de curso
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True).select_related('user')
    
    if request.method == 'POST':
        try:
            profesor_id = request.POST.get('profesor')
            profesor = Profesor.objects.get(id=profesor_id, sede=user_sede) if profesor_id else None
            
            EdicionCurso.objects.create(
                curso=curso,
                nombre_edicion=request.POST.get('nombre_edicion'),
                profesor=profesor,
                fecha_inicio=request.POST.get('fecha_inicio'),
                fecha_fin=request.POST.get('fecha_fin'),
                horario=request.POST.get('horario', ''),
                aula=request.POST.get('aula', ''),
                cupo_maximo=request.POST.get('cupo_maximo', 30) or 30
            )
            
            messages.success(request, f'Edición "{request.POST.get("nombre_edicion")}" creada exitosamente.')
            return redirect('hechos:ediciones_curso_list', curso_id=curso_id)
            
        except Exception as e:
            messages.error(request, f'Error al crear edición: {str(e)}')
    
    context = {
        'curso': curso,
        'profesores': profesores,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/crear_edicion_curso.html', context)


@login_required
def editar_edicion_curso(request, edicion_id):
    """
    Editar edición de curso existente
    """
    if not request.user.is_super_admin():
        r = ca.require_academico_o_pedagogico(request)
        if r:
            return r
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    edicion = get_object_or_404(EdicionCurso, id=edicion_id, curso__sede=user_sede)
    profesores = Profesor.objects.filter(sede=user_sede, is_active=True).select_related('user')
    
    if request.method == 'POST':
        try:
            profesor_id = request.POST.get('profesor')
            profesor = Profesor.objects.get(id=profesor_id, sede=user_sede) if profesor_id else None
            
            edicion.nombre_edicion = request.POST.get('nombre_edicion')
            edicion.profesor = profesor
            edicion.fecha_inicio = request.POST.get('fecha_inicio')
            edicion.fecha_fin = request.POST.get('fecha_fin')
            edicion.horario = request.POST.get('horario', '')
            edicion.aula = request.POST.get('aula', '')
            edicion.cupo_maximo = request.POST.get('cupo_maximo', 30) or 30
            edicion.save()
            
            messages.success(request, f'Edición "{edicion.nombre_edicion}" actualizada exitosamente.')
            return redirect('hechos:ediciones_curso_list', curso_id=edicion.curso.id)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar edición: {str(e)}')
    
    context = {
        'edicion': edicion,
        'profesores': profesores,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/editar_edicion_curso.html', context)


def _coordinador_financiero_gate(request):
    if request.user.is_super_admin():
        return None
    if ca.has_capacidad(request.user, 'financiero'):
        return None
    messages.error(request, 'Necesitas la función de recursos y finanzas para acceder a esta sección.')
    return redirect('core:dashboard')


@login_required
def coordinador_recursos(request):
    gate = _coordinador_financiero_gate(request)
    if gate:
        return gate
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')

    ofrendas_qs = (
        Ofrenda.objects.filter(sede=user_sede)
        .select_related('escuela', 'registrado_por')
        .order_by('-fecha', '-id')[:1500]
    )
    recaudos_qs = (
        RecaudoOcasional.objects.filter(sede=user_sede)
        .select_related('registrado_por')
        .order_by('-fecha', '-id')[:1500]
    )
    agg_of = Ofrenda.objects.filter(sede=user_sede).aggregate(
        total=Sum('valor'),
        n=Count('id'),
    )
    agg_rec = RecaudoOcasional.objects.filter(sede=user_sede).aggregate(
        total=Sum('monto'),
        n=Count('id'),
    )
    total_of = agg_of['total'] or Decimal('0')
    total_rec = agg_rec['total'] or Decimal('0')
    n_of = agg_of['n'] or 0
    n_rec = agg_rec['n'] or 0

    movimientos = []
    for o in ofrendas_qs:
        movimientos.append(
            {
                'kind': 'ofrenda',
                'fecha': o.fecha,
                'pk': o.id,
                'origen_label': 'Ofrenda',
                'detalle': o.escuela.nombre,
                'valor': o.valor,
                'registrado_por': o.registrado_por,
            }
        )
    for r in recaudos_qs:
        movimientos.append(
            {
                'kind': 'recaudo',
                'fecha': r.fecha,
                'pk': r.id,
                'origen_label': 'Recaudo ocasional',
                'detalle': r.concepto,
                'valor': r.monto,
                'registrado_por': r.registrado_por,
            }
        )
    movimientos.sort(key=lambda m: (m['fecha'], m['pk']), reverse=True)
    movimientos = movimientos[:500]

    return render(
        request,
        'hechos/coordinador_recursos.html',
        {
            'user_sede': user_sede,
            'movimientos': movimientos,
            'total_ofrendado': total_of,
            'total_recaudos_ocasionales': total_rec,
            'total_ingresos_sede': total_of + total_rec,
            'num_ofrendas': n_of,
            'num_recaudos': n_rec,
            'num_movimientos': n_of + n_rec,
        },
    )


@login_required
def coordinador_eventos_presupuesto(request):
    """
    Eventos o partidas y monto que la sede destina (planificación), aparte del registro de ofrendas.
    """
    gate = _coordinador_financiero_gate(request)
    if gate:
        return gate
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'eliminar_evento':
            try:
                eid = int(request.POST.get('evento_id'))
            except (TypeError, ValueError):
                messages.error(request, 'Solicitud inválida.')
                return redirect('hechos:coordinador_eventos_presupuesto')
            evento = get_object_or_404(PresupuestoEvento, id=eid, sede=user_sede)
            evento.delete()
            messages.success(request, 'Registro de evento eliminado.')
            return redirect('hechos:coordinador_eventos_presupuesto')

        form = PresupuestoEventoForm(request.POST, sede=user_sede)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.sede = user_sede
            obj.creado_por = request.user
            obj.save()
            messages.success(
                request,
                'Listo: quedó registrado el evento y el monto que planeas destinar.',
            )
            return redirect('hechos:coordinador_eventos_presupuesto')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = PresupuestoEventoForm(sede=user_sede)

    eventos = PresupuestoEvento.objects.filter(sede=user_sede).order_by(
        '-fecha_evento', '-created_at', '-id'
    )
    agg = PresupuestoEvento.objects.filter(sede=user_sede).aggregate(total=Sum('monto_destinado'))
    td = agg['total'] or Decimal('0')
    ti = ingresos_totales_sede(user_sede)
    return render(
        request,
        'hechos/coordinador_eventos_presupuesto.html',
        {
            'user_sede': user_sede,
            'eventos': eventos,
            'form': form,
            'total_destinado_eventos': td,
            'total_ingresos_sede': ti,
            'disponible_para_eventos': max(ti - td, Decimal('0')),
        },
    )


@login_required
def coordinador_recaudos_ocasionales(request):
    """
    Ingresos puntuales que registra el financiero: extras, sobrantes de evento, donaciones ocasionales, etc.
    """
    gate = _coordinador_financiero_gate(request)
    if gate:
        return gate
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()
        if action == 'eliminar_recaudo':
            try:
                rid = int(request.POST.get('recaudo_id'))
            except (TypeError, ValueError):
                messages.error(request, 'Solicitud inválida.')
                return redirect('hechos:coordinador_recaudos_ocasionales')
            rec = get_object_or_404(RecaudoOcasional, id=rid, sede=user_sede)
            rec.delete()
            messages.success(request, 'Recaudo ocasional eliminado.')
            return redirect('hechos:coordinador_recaudos_ocasionales')

        form = RecaudoOcasionalForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.sede = user_sede
            obj.registrado_por = request.user
            obj.save()
            messages.success(request, 'Recaudo ocasional registrado correctamente.')
            return redirect('hechos:coordinador_recaudos_ocasionales')
        messages.error(request, 'Revisa los datos del formulario.')
    else:
        form = RecaudoOcasionalForm(initial={'fecha': timezone.localdate()})

    recaudos = RecaudoOcasional.objects.filter(sede=user_sede).select_related('registrado_por').order_by(
        '-fecha', '-created_at', '-id'
    )
    agg = RecaudoOcasional.objects.filter(sede=user_sede).aggregate(total=Sum('monto'))
    return render(
        request,
        'hechos/coordinador_recaudos_ocasionales.html',
        {
            'user_sede': user_sede,
            'recaudos': recaudos,
            'form': form,
            'total_recaudado_ocasional': agg['total'] or 0,
        },
    )


@login_required
def coordinador_logistica(request):
    if not request.user.is_super_admin():
        p = getattr(request.user, 'admin_escuela_profile', None)
        if not p or not p.is_active or not ca.has_capacidad(request.user, 'logistico'):
            messages.error(request, 'Necesitas la función logística para acceder a esta sección.')
            return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada.')
        return redirect('core:dashboard')

    raw_tab = (request.GET.get('tab') or '').strip().lower()
    if raw_tab in ('salones', 'escuelas'):
        logistica_tab = raw_tab
    elif request.GET.get('escuela'):
        logistica_tab = 'escuelas'
    else:
        logistica_tab = 'salones'

    salon_form = SalonForm(prefix='nuevo')
    salon_editando = None
    salon_edit_form = None

    if request.method == 'POST':
        action = (request.POST.get('action') or '').strip()

        if action == 'crear_salon':
            salon_form = SalonForm(request.POST, prefix='nuevo')
            if salon_form.is_valid():
                salon = salon_form.save(commit=False)
                salon.sede = user_sede
                try:
                    salon.save()
                    messages.success(
                        request,
                        f'Salón «{salon.nombre}» creado con {salon.capacidad_plazas} plazas.',
                    )
                except IntegrityError:
                    messages.error(request, 'Ya existe un salón con ese nombre en esta sede.')
                return _redirect_coordinador_logistica(tab='salones')
            messages.error(request, 'Revisa los datos del salón.')

        elif action == 'actualizar_salon':
            salon = get_object_or_404(
                Salon,
                id=request.POST.get('salon_id'),
                sede=user_sede,
            )
            salon_edit_form = SalonForm(request.POST, instance=salon, prefix='edit')
            if salon_edit_form.is_valid():
                try:
                    salon_edit_form.save()
                    s = salon_edit_form.instance
                    if s.escuela_id:
                        EdicionCurso.objects.filter(
                            curso__ruta_estudio__escuela_id=s.escuela_id,
                            is_active=True,
                            curso__is_active=True,
                        ).update(cupo_maximo=s.capacidad_plazas)
                    messages.success(
                        request,
                        f'Salón «{salon_edit_form.instance.nombre}» actualizado.',
                    )
                    return _redirect_coordinador_logistica(tab='salones')
                except IntegrityError:
                    messages.error(request, 'Ya existe un salón con ese nombre en esta sede.')
            else:
                messages.error(request, 'Revisa los datos del salón.')
            salon_editando = salon

        elif action == 'toggle_salon':
            salon = get_object_or_404(
                Salon,
                id=request.POST.get('salon_id'),
                sede=user_sede,
            )
            salon.is_active = not salon.is_active
            salon.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, 'Estado del salón actualizado.')
            return _redirect_coordinador_logistica(tab='salones')

        elif action == 'asignar_salon_escuela':
            escuela = get_object_or_404(
                Escuela,
                id=request.POST.get('escuela_id'),
                sede=user_sede,
                is_active=True,
            )
            raw_sid = (request.POST.get('salon_id') or '').strip()
            if not raw_sid:
                messages.error(request, 'Elige un salón en el menú desplegable.')
                return _redirect_coordinador_logistica(tab='escuelas', escuela_id=escuela.id)
            salon = get_object_or_404(Salon, id=raw_sid, sede=user_sede)
            if salon.escuela_id == escuela.id:
                messages.info(request, 'Ese salón ya está asignado a esta escuela.')
                return _redirect_coordinador_logistica(tab='escuelas', escuela_id=escuela.id)
            if not salon.is_active:
                messages.error(request, 'Activa el salón antes de asignarlo.')
            elif escuela.sede_id != user_sede.id:
                messages.error(request, 'La escuela no pertenece a tu sede.')
            else:
                otros_en_escuela = list(
                    Salon.objects.filter(escuela=escuela).exclude(pk=salon.pk),
                )
                if otros_en_escuela:
                    Salon.objects.filter(escuela=escuela).exclude(pk=salon.pk).update(
                        escuela=None,
                        updated_at=timezone.now(),
                    )
                prev = salon.escuela
                salon.escuela = escuela
                salon.save(update_fields=['escuela', 'updated_at'])
                EdicionCurso.objects.filter(
                    curso__ruta_estudio__escuela=escuela,
                    is_active=True,
                    curso__is_active=True,
                ).update(cupo_maximo=salon.capacidad_plazas)

                frases = []
                if otros_en_escuela:
                    nombres = ', '.join(f'«{o.nombre}»' for o in otros_en_escuela)
                    frases.append(
                        f'Cada escuela solo puede tener un salón; se quitó {nombres} de esta escuela.',
                    )
                if prev and prev.id != escuela.id:
                    frases.append(
                        f'«{salon.nombre}» pasó de «{prev.nombre}» a «{escuela.nombre}».',
                    )
                elif not prev:
                    frases.append(f'«{salon.nombre}» quedó asignado a «{escuela.nombre}».')
                if frases:
                    messages.success(request, ' '.join(frases))
            return _redirect_coordinador_logistica(tab='escuelas', escuela_id=escuela.id)

        elif action == 'quitar_salon_escuela':
            escuela = get_object_or_404(
                Escuela,
                id=request.POST.get('escuela_id'),
                sede=user_sede,
                is_active=True,
            )
            salon = get_object_or_404(
                Salon,
                id=request.POST.get('salon_id'),
                sede=user_sede,
                escuela=escuela,
            )
            salon.escuela = None
            salon.save(update_fields=['escuela', 'updated_at'])
            EdicionCurso.objects.filter(
                curso__ruta_estudio__escuela=escuela,
                is_active=True,
                curso__is_active=True,
            ).update(cupo_maximo=0)
            messages.success(request, f'«{salon.nombre}» ya no está asignado a «{escuela.nombre}».')
            return _redirect_coordinador_logistica(tab='escuelas', escuela_id=escuela.id)

    salones = (
        Salon.objects.filter(sede=user_sede)
        .select_related('escuela')
        .order_by('-is_active', 'nombre')
    )
    escuelas = Escuela.objects.filter(sede=user_sede, is_active=True).order_by('-anio', 'nombre')

    escuela_focus = None
    eid = request.GET.get('escuela')
    if eid:
        try:
            escuela_focus = Escuela.objects.get(
                id=int(eid),
                sede=user_sede,
                is_active=True,
            )
        except (ValueError, Escuela.DoesNotExist):
            escuela_focus = None

    if logistica_tab == 'salones' and salon_editando is None:
        edit_get = request.GET.get('editar')
        if edit_get:
            try:
                salon_editando = Salon.objects.get(id=int(edit_get), sede=user_sede)
                salon_edit_form = SalonForm(instance=salon_editando, prefix='edit')
            except (ValueError, Salon.DoesNotExist):
                messages.warning(request, 'No se encontró ese salón en tu sede.')

    salon_asignado_escuela = None
    salones_elegibles_asignar = []
    if escuela_focus:
        salon_asignado_escuela = (
            Salon.objects.filter(sede=user_sede, escuela_id=escuela_focus.id)
            .select_related('escuela')
            .order_by('-is_active', 'nombre')
            .first()
        )
        salones_elegibles_asignar = list(
            Salon.objects.filter(sede=user_sede, is_active=True)
            .exclude(escuela_id=escuela_focus.id)
            .select_related('escuela')
            .order_by('nombre'),
        )

    return render(
        request,
        'hechos/coordinador_logistica.html',
        {
            'user_sede': user_sede,
            'salon_form': salon_form,
            'salon_editando': salon_editando,
            'salon_edit_form': salon_edit_form,
            'salones': salones,
            'escuelas': escuelas,
            'escuela_focus': escuela_focus,
            'logistica_tab': logistica_tab,
            'salon_asignado_escuela': salon_asignado_escuela,
            'salones_elegibles_asignar': salones_elegibles_asignar,
        },
    )
