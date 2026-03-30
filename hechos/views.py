from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Exists, OuterRef
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Estudiante, Profesor, AdminEscuela, Escuela, RutaEstudio, Curso,
    Matricula, Clase, Asistencia, Nota, EdicionCurso, SolicitudMatricula, NotificacionEstudiante,
    SolicitudEspecialEstudiante,
)
from .utils import get_current_period, get_period_from_date, get_period_display, get_period_stats
from core.models import Sede, generate_unique_username
from hechos import coordinador_access as ca

User = get_user_model()


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


@login_required
def hechos_dashboard(request):
    """
    Dashboard del módulo Hechos (Escuelas Bíblicas)
    """
    redir = ca.redirect_operational_home_if_restricted(request)
    if redir:
        return redir

    if (
        hasattr(request.user, 'admin_escuela_profile')
        and ca.admin_tipo(request.user) == AdminEscuela.TipoCoordinador.PEDAGOGICO
    ):
        return redirect('hechos:profesores_list')

    # Verificar si el usuario tiene acceso al módulo
    if not hasattr(request.user, 'estudiante_profile') and not hasattr(request.user, 'profesor_profile') and not hasattr(request.user, 'admin_escuela_profile'):
        messages.warning(request, 'No tienes acceso al módulo Hechos.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede and hasattr(request.user, 'estudiante_profile'):
        return redirect('hechos:seleccionar_sede_estudiante')
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    context = {
        'user_sede': user_sede,
    }
    
    # Datos específicos según el perfil del usuario
    if hasattr(request.user, 'estudiante_profile'):
        estudiante = request.user.estudiante_profile
        
        # Obtener matrículas activas con información detallada
        matriculas_activas = Matricula.objects.filter(
            estudiante=estudiante,
            sede=user_sede,
            is_active=True
        ).select_related('edicion_curso__curso__ruta_estudio__escuela', 'edicion_curso__profesor__user')
        
        # Obtener curso actual (el más reciente)
        matricula_actual = None
        if matriculas_activas.exists():
            matricula_actual = matriculas_activas.first()
        curso_actual = matricula_actual.edicion_curso.curso if matricula_actual else None
        
        # Importar Nota al inicio
        from hechos.models import Nota
        
        # Obtener notas recientes
        notas_recientes = Nota.objects.filter(
            estudiante=estudiante, 
            sede=user_sede
        ).select_related('curso', 'profesor__user').order_by('-fecha_evaluacion')[:5]
        
        # Calcular promedio general
        todas_las_notas = Nota.objects.filter(estudiante=estudiante, sede=user_sede)
        promedio_general = 0
        if todas_las_notas.exists():
            promedio_general = sum(nota.puntaje_obtenido for nota in todas_las_notas) / todas_las_notas.count()

        escuelas_activas = []
        escuelas_activas_ids = set()
        for matricula in matriculas_activas:
            escuela = matricula.edicion_curso.curso.escuela
            if escuela and escuela.id not in escuelas_activas_ids:
                escuelas_activas.append({
                    'escuela': escuela,
                    'nivel': matricula.edicion_curso.curso.nivel,
                    'grupo': matricula.edicion_curso,
                    'curso': matricula.edicion_curso.curso,
                })
                escuelas_activas_ids.add(escuela.id)

        solicitudes_estudiante = SolicitudMatricula.objects.filter(estudiante=estudiante).select_related(
            'edicion_curso__curso__ruta_estudio__escuela'
        )
        solicitudes_pendientes = solicitudes_estudiante.filter(estado='pendiente')

        solicitudes_por_edicion = {
            solicitud.edicion_curso_id: solicitud
            for solicitud in SolicitudMatricula.objects.filter(estudiante=estudiante).select_related(
                'edicion_curso__curso__ruta_estudio__escuela',
                'edicion_curso__curso__sede',
                'edicion_curso__profesor__user',
            )
        }
        matriculas_activas_ids = set(
            Matricula.objects.filter(estudiante=estudiante, is_active=True).values_list('edicion_curso_id', flat=True)
        )
        ediciones_disponibles = EdicionCurso.objects.filter(
            is_active=True,
            curso__is_active=True,
            curso__ruta_estudio__escuela__isnull=False,
            curso__sede=user_sede,
        ).select_related(
            'curso__ruta_estudio__escuela',
            'curso__sede',
            'profesor__user',
        ).order_by(
            'curso__ruta_estudio__escuela__nombre',
            'curso__ruta_estudio__nombre',
            'curso__nombre',
            'nombre_edicion',
        )
        escuelas_feed_by_id = {}
        for edicion in ediciones_disponibles:
            escuela = edicion.curso.escuela
            if not escuela:
                continue
            solicitud = solicitudes_por_edicion.get(edicion.id)
            escuela_data = escuelas_feed_by_id.setdefault(
                escuela.id,
                {
                    'escuela': escuela,
                    'sede': escuela.sede or edicion.curso.sede,
                    'niveles': [],
                },
            )
            escuela_data['niveles'].append(
                {
                    'nivel': edicion.curso.nivel,
                    'edicion': edicion,
                    'curso': edicion.curso,
                    'ya_matriculado': edicion.id in matriculas_activas_ids,
                    'solicitud': solicitud,
                    'puede_solicitar': edicion.id not in matriculas_activas_ids and solicitud is None,
                }
            )
        
        # Obtener asistencia reciente
        from hechos.models import Asistencia
        asistencia_reciente = Asistencia.objects.filter(
            estudiante=estudiante,
            sede=user_sede
        ).select_related('clase__edicion_curso__curso').order_by('-fecha_registro')[:5]
        
        # Estadísticas de asistencia
        total_asistencias = Asistencia.objects.filter(estudiante=estudiante, sede=user_sede).count()
        asistencias_presentes = Asistencia.objects.filter(
            estudiante=estudiante, 
            sede=user_sede, 
            estado='presente'
        ).count()
        porcentaje_asistencia = (asistencias_presentes / total_asistencias * 100) if total_asistencias > 0 else 0
        
        context.update({
            'estudiante': estudiante,
            'matriculas_activas': matriculas_activas,
            'curso_actual': curso_actual,
            'matricula_actual': matricula_actual,
            'notas_recientes': notas_recientes,
            'promedio_general': round(promedio_general, 2),
            'escuelas_activas': escuelas_activas,
            'solicitudes_pendientes_count': solicitudes_pendientes.count(),
            'asistencia_reciente': asistencia_reciente,
            'total_asistencias': total_asistencias,
            'asistencias_presentes': asistencias_presentes,
            'porcentaje_asistencia': round(porcentaje_asistencia, 1),
            'escuelas_feed': list(escuelas_feed_by_id.values()),
        })
    
    if hasattr(request.user, 'profesor_profile'):
        profesor = request.user.profesor_profile
        # Obtener cursos a través de ediciones
        cursos_profesor = Curso.objects.filter(
            ediciones__profesor=profesor,
            sede=user_sede,
            is_active=True
        ).distinct()
        
        # Obtener ediciones del profesor
        ediciones_profesor = EdicionCurso.objects.filter(
            profesor=profesor,
            curso__sede=user_sede,
            is_active=True
        ).select_related('curso__ruta_estudio')
        
        # Obtener estudiantes del profesor
        estudiantes_profesor = Estudiante.objects.filter(
            matriculas__edicion_curso__profesor=profesor,
            matriculas__sede=user_sede,
            matriculas__is_active=True
        ).distinct()
        
        # Obtener clases próximas
        clases_proximas = Clase.objects.filter(
            edicion_curso__profesor=profesor,
            sede=user_sede,
            is_active=True
        ).order_by('fecha_clase')[:5]
        
        context.update({
            'profesor': profesor,
            'cursos': cursos_profesor,
            'ediciones': ediciones_profesor,
            'estudiantes_total': estudiantes_profesor.count(),
            'clases_proximas': clases_proximas,
        })
    
    if hasattr(request.user, 'admin_escuela_profile'):
        admin = request.user.admin_escuela_profile
        solicitudes_matricula_pendientes = SolicitudMatricula.objects.filter(
            sede=user_sede,
            estado='pendiente',
        ).count()
        solicitudes_especiales_pendientes = SolicitudEspecialEstudiante.objects.filter(
            sede=user_sede,
            estado='pendiente',
        ).count()
        context.update({
            'admin': admin,
            'admin_tipo_coordinador': admin.tipo_coordinador,
            'total_estudiantes': Estudiante.objects.filter(sede=user_sede, is_active=True).count(),
            'total_profesores': Profesor.objects.filter(sede=user_sede, is_active=True).count(),
            'total_cursos': Curso.objects.filter(sede=user_sede, is_active=True).count(),
            'total_matriculas': Matricula.objects.filter(sede=user_sede, is_active=True).count(),
            'solicitudes_matricula_pendientes': solicitudes_matricula_pendientes,
            'solicitudes_especiales_pendientes': solicitudes_especiales_pendientes,
        })
    
    # Estudiantes no deben usar esta pantalla: enviarlos a Escuelas.
    if hasattr(request.user, 'estudiante_profile'):
        return redirect('hechos:escuelas_disponibles')
    if (
        hasattr(request.user, 'admin_escuela_profile')
        and request.user.admin_escuela_profile.tipo_coordinador == AdminEscuela.TipoCoordinador.ACADEMICO
    ):
        return render(request, 'hechos/dashboard_academico.html', context)
    else:
        return render(request, 'hechos/dashboard_modern.html', context)


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
            and ca.admin_tipo(request.user) == AdminEscuela.TipoCoordinador.ACADEMICO
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
            and ca.admin_tipo(request.user) == AdminEscuela.TipoCoordinador.PEDAGOGICO
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

    es_pedagogico = ca.admin_tipo(request.user) == AdminEscuela.TipoCoordinador.PEDAGOGICO

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

    context = {
        'escuelas': list(escuelas_by_id.values()),
        'estudiante': estudiante,
        'user_sede': user_sede,
    }
    return render(request, 'hechos/escuelas_disponibles.html', context)


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
    return redirect('hechos:mis_solicitudes')


@login_required
def mis_solicitudes(request):
    """
    Lista de solicitudes de matrícula del estudiante.
    """
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden ver sus solicitudes.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    solicitudes = SolicitudMatricula.objects.filter(estudiante=estudiante).select_related(
        'edicion_curso__curso__ruta_estudio__escuela', 'edicion_curso__curso__sede', 'edicion_curso__profesor__user'
    )

    context = {
        'solicitudes': solicitudes,
        'estudiante': estudiante,
    }
    return render(request, 'hechos/mis_solicitudes.html', context)


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
    if not hasattr(request.user, 'estudiante_profile'):
        messages.error(request, 'Solo los estudiantes pueden acceder a esta sección.')
        return redirect('core:dashboard')

    estudiante = request.user.estudiante_profile
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.info(request, 'Selecciona tu sede para continuar.')
        return redirect('hechos:seleccionar_sede_estudiante')

    if request.method == 'POST':
        asunto = (request.POST.get('asunto') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        if not asunto or not descripcion:
            messages.error(request, 'Asunto y descripción son obligatorios.')
            return redirect('hechos:solicitudes_especiales_estudiante')

        SolicitudEspecialEstudiante.objects.create(
            sede=user_sede,
            estudiante=estudiante,
            tipo=SolicitudEspecialEstudiante.Tipo.OTRA,
            asunto=asunto,
            descripcion=descripcion,
        )
        messages.success(request, 'Tu solicitud especial fue enviada.')
        return redirect('hechos:solicitudes_especiales_estudiante')

    solicitudes = SolicitudEspecialEstudiante.objects.filter(
        estudiante=estudiante,
    ).select_related('revisado_por').order_by('-fecha_solicitud')
    return render(
        request,
        'hechos/solicitudes_especiales_estudiante.html',
        {'solicitudes': solicitudes},
    )


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
        titulo='Actualización de solicitud especial',
        mensaje=(
            f"Tu solicitud '{solicitud.asunto}' fue marcada como {solicitud.get_estado_display().lower()}."
            + (f" Comentario: {observaciones}" if observaciones else "")
        ),
    )
    messages.success(request, 'Solicitud especial actualizada.')
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
def clases_list(request):
    """
    Lista de clases
    """
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')

    if hasattr(request.user, 'admin_escuela_profile') and not request.user.is_super_admin():
        if not ca.admin_may_access_clases_list(request.user):
            messages.error(request, 'No tienes permisos para ver las clases.')
            return redirect('core:dashboard')
    
    clases = Clase.objects.filter(sede=user_sede, is_active=True).select_related('edicion_curso__curso', 'profesor__user')
    
    # Filtrar según el perfil del usuario
    if hasattr(request.user, 'profesor_profile'):
        # Profesor ve solo sus clases
        clases = clases.filter(profesor=request.user.profesor_profile)
    elif hasattr(request.user, 'estudiante_profile'):
        # Estudiante ve clases de sus cursos matriculados
        matriculas = Matricula.objects.filter(
            estudiante=request.user.estudiante_profile,
            sede=user_sede,
            is_active=True
        ).values_list('curso_id', flat=True)
        clases = clases.filter(curso_id__in=matriculas)
    
    context = {
        'clases': clases,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/clases_list_modern.html', context)


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
    
    clase = get_object_or_404(Clase, id=clase_id, profesor=request.user.profesor_profile, sede=user_sede)
    
    if request.method == 'POST':
        # Procesar asistencia
        for key, value in request.POST.items():
            if key.startswith('estudiante_'):
                estudiante_id = key.split('_')[1]
                try:
                    estudiante = Estudiante.objects.get(id=estudiante_id, sede=user_sede)
                    asistencia, created = Asistencia.objects.get_or_create(
                        clase=clase,
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
        
        messages.success(request, 'Asistencia registrada correctamente.')
        return redirect('hechos:asistencia_clase', clase_id=clase_id)
    
    # Obtener estudiantes matriculados en el curso
    estudiantes = Estudiante.objects.filter(
        matriculas__curso=clase.curso,
        matriculas__sede=user_sede,
        matriculas__is_active=True,
        sede=user_sede
    ).select_related('user')
    
    # Obtener asistencias existentes
    asistencias = Asistencia.objects.filter(clase=clase, sede=user_sede).select_related('estudiante__user')
    asistencia_dict = {a.estudiante.id: a.estado for a in asistencias}
    
    context = {
        'clase': clase,
        'estudiantes': estudiantes,
        'asistencia_dict': asistencia_dict,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/asistencia_clase_modern.html', context)


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


@login_required
def notas_profesor(request):
    """
    Dashboard de notas para profesores
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder a esta página.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = request.user.profesor_profile
    # Obtener cursos a través de ediciones
    cursos = Curso.objects.filter(
        ediciones__profesor=profesor,
        sede=user_sede,
        is_active=True
    ).distinct().select_related('ruta_estudio')
    
    # Obtener estadísticas por curso
    cursos_con_estadisticas = []
    for curso in cursos:
        # Obtener estudiantes matriculados a través de ediciones
        estudiantes_matriculados = Matricula.objects.filter(
            edicion_curso__curso=curso,
            sede=user_sede,
            is_active=True
        ).select_related('estudiante__user')
        
        # Obtener notas del curso
        notas_curso = Nota.objects.filter(curso=curso, sede=user_sede).select_related('estudiante__user')
        
        # Calcular estadísticas
        total_estudiantes = estudiantes_matriculados.count()
        total_notas = notas_curso.count()
        
        # Promedio general del curso
        if notas_curso.exists():
            promedio_general = notas_curso.aggregate(
                promedio=models.Avg('puntaje_obtenido')
            )['promedio'] or 0
        else:
            promedio_general = 0
        
        cursos_con_estadisticas.append({
            'curso': curso,
            'total_estudiantes': total_estudiantes,
            'total_notas': total_notas,
            'promedio_general': round(promedio_general, 2),
            'estudiantes_matriculados': estudiantes_matriculados,
        })
    
    context = {
        'profesor': profesor,
        'cursos_con_estadisticas': cursos_con_estadisticas,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/notas_profesor_modern.html', context)


@login_required
def notas_curso(request, curso_id):
    """
    Gestión de notas para un curso específico - Vista simplificada
    """
    if not hasattr(request.user, 'profesor_profile'):
        messages.error(request, 'Solo los profesores pueden acceder a esta página.')
        return redirect('core:dashboard')
    
    # Obtener la sede del usuario
    user_sede = get_user_sede(request.user)
    if not user_sede:
        messages.warning(request, 'No tienes una sede asignada. Contacta al administrador.')
        return redirect('core:dashboard')
    
    profesor = request.user.profesor_profile
    # Verificar que el profesor tenga ediciones de este curso
    curso = get_object_or_404(Curso, id=curso_id, sede=user_sede, is_active=True)
    if not EdicionCurso.objects.filter(curso=curso, profesor=profesor, is_active=True).exists():
        messages.error(request, 'No tienes permisos para acceder a este curso.')
        return redirect('hechos:notas_profesor')
    
    # Obtener estudiantes matriculados a través de ediciones
    estudiantes_matriculados = Matricula.objects.filter(
        edicion_curso__curso=curso,
        edicion_curso__profesor=profesor,
        sede=user_sede,
        is_active=True
    ).select_related('estudiante__user')
    
    # Obtener todas las notas del curso
    notas = Nota.objects.filter(curso=curso, sede=user_sede).select_related('estudiante__user').order_by('-fecha_evaluacion')
    
    # Preparar datos de estudiantes con sus notas
    estudiantes_con_notas = []
    for matricula in estudiantes_matriculados:
        estudiante = matricula.estudiante
        
        # Obtener notas del estudiante en este curso
        notas_estudiante = notas.filter(estudiante=estudiante)
        
        # Calcular promedio
        if notas_estudiante.exists():
            promedio = notas_estudiante.aggregate(
                promedio=models.Avg('puntaje_obtenido')
            )['promedio'] or 0
        else:
            promedio = 0
        
        # Obtener nota final si existe
        nota_final = notas_estudiante.filter(tipo='final').first()
        
        estudiantes_con_notas.append({
            'estudiante': estudiante,
            'matricula': matricula,
            'notas': notas_estudiante,
            'promedio': round(promedio, 2),
            'nota_final': nota_final,
            'total_notas': notas_estudiante.count()
        })
    
    if request.method == 'POST':
        # Procesar múltiples notas
        for key, value in request.POST.items():
            if key.startswith('nota_') and value:
                estudiante_id = key.split('_')[1]
                try:
                    estudiante = Estudiante.objects.get(id=estudiante_id, sede=user_sede)
                    
                    # Verificar si ya existe una nota final
                    nota_existente = Nota.objects.filter(
                        estudiante=estudiante,
                        curso=curso,
                        tipo='final',
                        sede=user_sede
                    ).first()
                    
                    if nota_existente:
                        # Actualizar nota existente
                        nota_existente.puntaje_obtenido = float(value)
                        nota_existente.fecha_evaluacion = timezone.now().date()
                        nota_existente.save()
                    else:
                        # Crear nueva nota final
                        Nota.objects.create(
                            sede=user_sede,
                            estudiante=estudiante,
                            curso=curso,
                            tipo='final',
                            titulo='Nota Final',
                            puntaje_obtenido=float(value),
                            puntaje_maximo=5.0,
                            fecha_evaluacion=timezone.now().date(),
                            profesor=profesor,
                            observaciones='Nota final del curso'
                        )
                except (Estudiante.DoesNotExist, ValueError):
                    continue
        
        messages.success(request, 'Notas actualizadas correctamente.')
        return redirect('hechos:notas_curso', curso_id=curso_id)
    
    context = {
        'curso': curso,
        'estudiantes_con_notas': estudiantes_con_notas,
        'user_sede': user_sede,
    }
    
    return render(request, 'hechos/notas_curso_modern.html', context)


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
            and ca.admin_tipo(request.user) == AdminEscuela.TipoCoordinador.ACADEMICO
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
            
            # Actualizar perfil de profesor
            profesor.especialidad = request.POST.get('especialidad', '')
            profesor.experiencia_anos = request.POST.get('experiencia_anos', 0) or 0
            profesor.biografia = request.POST.get('biografia', '')
            profesor.save()
            
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
    allowed = (
        request.user.is_super_admin()
        or hasattr(request.user, 'estudiante_profile')
        or hasattr(request.user, 'profesor_profile')
        or (
            hasattr(request.user, 'admin_escuela_profile')
            and ca.admin_tipo(request.user)
            in (
                AdminEscuela.TipoCoordinador.ACADEMICO,
                AdminEscuela.TipoCoordinador.PEDAGOGICO,
            )
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
            return redirect('hechos:dashboard')

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
        context = {
            'curso': curso,
            'matricula': matricula,
            'clases': clases,
            'notas_curso': notas_curso,
            'promedio_general': round(promedio, 2),
            'total_clases': clases.count(),
            'total_notas': notas_curso.count(),
            'user_sede': user_sede,
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
    
    # Obtener notas del curso
    notas_curso = Nota.objects.filter(
        curso=curso,
        sede=user_sede
    ).select_related('estudiante__user').order_by('-fecha_evaluacion')
    
    # Calcular promedio general
    promedio_general = notas_curso.aggregate(
        promedio=Avg('puntaje_obtenido')
    )['promedio'] or 0
    
    # Preparar datos de estudiantes con notas
    estudiantes_con_notas = []
    for matricula in matriculas:
        # Obtener notas del estudiante en este curso
        notas_estudiante = notas_curso.filter(estudiante=matricula.estudiante)
        
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
        'notas_curso': notas_curso[:10],  # Últimas 10 notas
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


@login_required
def coordinador_recursos(request):
    if not request.user.is_super_admin():
        p = getattr(request.user, 'admin_escuela_profile', None)
        if not p or p.tipo_coordinador != AdminEscuela.TipoCoordinador.FINANCIERO:
            messages.error(request, 'Solo el coordinador financiero puede acceder a esta sección.')
            return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    return render(request, 'hechos/coordinador_recursos.html', {'user_sede': user_sede})


@login_required
def coordinador_logistica(request):
    if not request.user.is_super_admin():
        p = getattr(request.user, 'admin_escuela_profile', None)
        if not p or p.tipo_coordinador != AdminEscuela.TipoCoordinador.LOGISTICO:
            messages.error(request, 'Solo el coordinador logístico puede acceder a esta sección.')
            return redirect('core:dashboard')
    user_sede = get_user_sede(request.user)
    return render(request, 'hechos/coordinador_logistica.html', {'user_sede': user_sede})
