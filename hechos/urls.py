from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'hechos'

urlpatterns = [
    path('', views.hechos_dashboard, name='dashboard'),
    path('dashboard/', views.hechos_dashboard, name='dashboard'),
    path('mi-sede/', views.seleccionar_sede_estudiante, name='seleccionar_sede_estudiante'),
    path('coordinacion/recursos/', views.coordinador_recursos, name='coordinador_recursos'),
    path('coordinacion/financiero/info/', views.coordinador_financiero_info, name='coordinador_financiero_info'),
    path(
        'coordinacion/eventos-presupuesto/',
        views.coordinador_eventos_presupuesto,
        name='coordinador_eventos_presupuesto',
    ),
    path(
        'coordinacion/recaudos-ocasionales/',
        views.coordinador_recaudos_ocasionales,
        name='coordinador_recaudos_ocasionales',
    ),
    path('coordinacion/logistica/', views.coordinador_logistica, name='coordinador_logistica'),
    path('escuelas/', views.escuelas_disponibles, name='escuelas_disponibles'),
    path(
        'escuelas/por-escuela/<int:escuela_id>/solicitar-matricula/',
        views.solicitar_matricula_escuela,
        name='solicitar_matricula_escuela',
    ),
    path('quejas-reclamos/', views.quejas_reclamos, name='quejas_reclamos'),
    path('escuelas/<int:edicion_id>/solicitar-matricula/', views.solicitar_matricula, name='solicitar_matricula'),
    path(
        'coordinacion/pedagogico/editar-escuela/',
        views.estructura_ediciones,
        name='pedagogico_editar_escuela',
    ),
    path(
        'coordinacion/pedagogico/editar-escuela/<int:escuela_id>/',
        views.estructura_escuela_portal,
        name='pedagogico_editar_escuela_portal',
    ),
    path(
        'coordinacion/pedagogico/editar-escuela/<int:escuela_id>/paso/<int:step>/',
        views.estructura_configurar_paso,
        name='pedagogico_editar_escuela_paso',
    ),
    # Rutas antiguas /estructura/ → pedagogico/editar-escuela
    path(
        'estructura/',
        RedirectView.as_view(pattern_name='hechos:pedagogico_editar_escuela', permanent=False),
    ),
    path(
        'estructura/escuela/<int:escuela_id>/',
        RedirectView.as_view(pattern_name='hechos:pedagogico_editar_escuela_portal', permanent=False),
    ),
    path(
        'estructura/escuela/<int:escuela_id>/paso/<int:step>/',
        RedirectView.as_view(pattern_name='hechos:pedagogico_editar_escuela_paso', permanent=False),
    ),
    path('coordinacion/pedagogico/escuelas/crear/', views.pedagogico_crear_escuela, name='pedagogico_crear_escuela'),
    path('coordinacion/pedagogico/info/', views.pedagogico_info, name='pedagogico_info'),
    path('mis-certificados/', views.mis_certificados, name='mis_certificados'),
    path('mis-escuelas/', views.mis_escuelas, name='mis_escuelas'),
    path('historial-escuelas/', views.historial_escuelas, name='historial_escuelas'),
    path('horario/', views.mi_horario, name='mi_horario'),
    path('horario/descargar/', views.mi_horario_descargar, name='mi_horario_descargar'),
    path(
        'mis-escuelas/escuela/<int:escuela_id>/recursos/',
        views.estudiante_escuela_recursos,
        name='estudiante_escuela_recursos',
    ),
    path(
        'archivo-recurso-escuela/<int:escuela_id>/<int:archivo_id>/',
        views.descargar_archivo_recurso_escuela,
        name='descargar_archivo_recurso_escuela',
    ),
    path(
        'mis-escuelas/escuela/<int:escuela_id>/certificado/',
        views.ver_certificado_escuela,
        name='ver_certificado_escuela',
    ),
    path(
        'mis-escuelas/<int:curso_id>/actividad/<int:actividad_id>/entregar/',
        views.entregar_actividad_estudiante,
        name='entregar_actividad_estudiante',
    ),
    path(
        'mis-escuelas/<int:curso_id>/actividad/<int:actividad_id>/descargar-archivo/',
        views.descargar_archivo_entrega_actividad,
        name='descargar_entrega_actividad_archivo',
    ),
    path('mis-escuelas/<int:curso_id>/', views.detalle_mis_escuela, name='detalle_mis_escuela'),
    path(
        'mis-solicitudes/',
        RedirectView.as_view(pattern_name='hechos:mis_escuelas', permanent=False),
    ),
    path('solicitudes/', views.solicitudes_matricula_admin, name='solicitudes_matricula_admin'),
    path('solicitudes/<int:solicitud_id>/revisar/', views.revisar_solicitud_matricula, name='revisar_solicitud_matricula'),
    path('mis-solicitudes-especiales/', views.solicitudes_especiales_estudiante, name='solicitudes_especiales_estudiante'),
    path('solicitudes-especiales/', views.solicitudes_especiales_admin, name='solicitudes_especiales_admin'),
    path('solicitudes-especiales/<int:solicitud_id>/revisar/', views.revisar_solicitud_especial_admin, name='revisar_solicitud_especial_admin'),
    
    # Estudiantes (el directorio en sí vive en core:estudiantes_list, /director/estudiantes/,
    # junto a los otros dos directorios compartidos: profesores y coordinadores)
    path('estudiantes/crear/', views.crear_estudiante, name='crear_estudiante'),
    path('estudiantes/<int:estudiante_id>/', views.detalle_estudiante, name='detalle_estudiante'),
    path(
        'estudiantes/<int:estudiante_id>/resumen/',
        views.estudiante_resumen_fragment,
        name='estudiante_resumen_fragment',
    ),
    path('estudiantes/<int:estudiante_id>/editar/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiantes/<int:estudiante_id>/eliminar/', views.eliminar_estudiante, name='eliminar_estudiante'),
    
    # Profesores (coordinador pedagógico)
    path('coordinacion/pedagogico/profesores/', views.profesores_list, name='profesores_list'),
    path('coordinacion/pedagogico/profesores/crear/', views.crear_profesor, name='crear_profesor'),
    path('coordinacion/pedagogico/profesores/<int:profesor_id>/', views.detalle_profesor, name='detalle_profesor'),
    path(
        'coordinacion/pedagogico/profesores/<int:profesor_id>/editar/',
        views.editar_profesor,
        name='editar_profesor',
    ),
    path(
        'coordinacion/pedagogico/profesores/<int:profesor_id>/eliminar/',
        views.eliminar_profesor,
        name='eliminar_profesor',
    ),
    # Rutas antiguas /profesores/ → coordinacion/pedagogico/profesores/
    path('profesores/', RedirectView.as_view(pattern_name='hechos:profesores_list', permanent=False)),
    path('profesores/crear/', RedirectView.as_view(pattern_name='hechos:crear_profesor', permanent=False)),
    path(
        'profesores/<int:profesor_id>/',
        RedirectView.as_view(pattern_name='hechos:detalle_profesor', permanent=False),
    ),
    path(
        'profesores/<int:profesor_id>/editar/',
        RedirectView.as_view(pattern_name='hechos:editar_profesor', permanent=False),
    ),
    path(
        'profesores/<int:profesor_id>/eliminar/',
        RedirectView.as_view(pattern_name='hechos:eliminar_profesor', permanent=False),
    ),

    # Cursos
    path('cursos/', views.cursos_list, name='cursos_list'),
    path('cursos/crear/', views.crear_curso, name='crear_curso'),
    path('cursos/<int:curso_id>/', views.detalle_curso, name='detalle_curso'),
    path('cursos/<int:curso_id>/editar/', views.editar_curso, name='editar_curso'),
    path('cursos/<int:curso_id>/eliminar/', views.eliminar_curso, name='eliminar_curso'),
    path('cursos/<int:curso_id>/asistencia/', views.tomar_asistencia_curso, name='tomar_asistencia_curso'),
    path('cursos/matricular/', views.matricular_estudiante, name='matricular_estudiante'),
    path(
        'cursos/matricular/buscar-doc/',
        views.buscar_estudiante_doc_matricula,
        name='buscar_estudiante_doc_matricula',
    ),
    path(
        'cursos/matricular/sugerencias-doc/',
        views.sugerencias_estudiante_doc_matricula,
        name='sugerencias_estudiante_doc_matricula',
    ),
    
    # Rutas de Estudio
    path('rutas-estudio/', views.rutas_estudio_list, name='rutas_estudio_list'),
    path('rutas-estudio/crear/', views.crear_ruta_estudio, name='crear_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/', views.ruta_estudio_detail, name='ruta_estudio_detail'),
    path('rutas-estudio/<int:ruta_id>/editar/', views.editar_ruta_estudio, name='editar_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/eliminar/', views.eliminar_ruta_estudio, name='eliminar_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/crear-curso/', views.crear_curso_ruta, name='crear_curso_ruta'),
    
    # Clases (lista docente con URL amigable; /clases/ redirige aquí si eres profesor)
    path(
        'profesor/entregas-pendientes/',
        views.profesor_bandeja_entregas,
        name='profesor_bandeja_entregas',
    ),
    path(
        'profesor/solicitudes-matricula/',
        views.profesor_solicitudes_matricula,
        name='profesor_solicitudes_matricula',
    ),
    path(
        'profesor/restablecer-contrasena/',
        views.profesor_restablecer_contrasena,
        name='profesor_restablecer_contrasena',
    ),
    path('profesor/mis-escuelas/', views.clases_list, name='mis_escuelas_profesor'),
    path(
        'profesor/crear-instancia-escuela/',
        views.profesor_crear_instancia_escuela,
        name='profesor_crear_instancia_escuela',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/dar-de-baja/',
        views.profesor_escuela_dar_de_baja,
        name='profesor_escuela_dar_de_baja',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/actividad/<int:actividad_id>/entregas/<int:entrega_id>/archivo/',
        views.profesor_descargar_entrega_archivo,
        name='profesor_descargar_entrega_archivo',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/actividad/<int:actividad_id>/entregas/',
        views.profesor_actividad_entregas,
        name='profesor_actividad_entregas',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/actividad/',
        views.escuela_crear_actividad,
        name='escuela_crear_actividad',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/archivos/',
        views.escuela_archivos,
        name='escuela_archivos',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/estudiantes/',
        views.profesor_escuela_estudiantes,
        name='profesor_escuela_estudiantes',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/estudiantes/<int:estudiante_id>/editar/',
        views.profesor_escuela_estudiante_editar,
        name='profesor_escuela_estudiante_editar',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/estudiantes/<int:estudiante_id>/quitar-matricula/',
        views.profesor_escuela_estudiante_quitar_matricula,
        name='profesor_escuela_estudiante_quitar_matricula',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/',
        views.profesor_escuela_asistencia_panel,
        name='profesor_escuela_asistencia_panel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/excel/',
        views.profesor_escuela_asistencia_excel,
        name='profesor_escuela_asistencia_excel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/excel-formato/',
        views.profesor_escuela_asistencia_excel_formato,
        name='profesor_escuela_asistencia_excel_formato',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/importar-excel/',
        views.profesor_escuela_asistencia_import_excel,
        name='profesor_escuela_asistencia_import_excel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/agregar-sesion/',
        views.profesor_escuela_asistencia_agregar_sesion,
        name='profesor_escuela_asistencia_agregar_sesion',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/asistencia/quitar-sesion/',
        views.profesor_escuela_asistencia_quitar_sesion,
        name='profesor_escuela_asistencia_quitar_sesion',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/',
        views.profesor_escuela_notas_panel,
        name='profesor_escuela_notas_panel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/excel/',
        views.profesor_escuela_notas_excel,
        name='profesor_escuela_notas_excel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/excel-formato/',
        views.profesor_escuela_notas_excel_formato,
        name='profesor_escuela_notas_excel_formato',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/importar-excel/',
        views.profesor_escuela_notas_import_excel,
        name='profesor_escuela_notas_import_excel',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/agregar-nota/',
        views.profesor_escuela_notas_agregar_columna,
        name='profesor_escuela_notas_agregar_columna',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/quitar-nota/',
        views.profesor_escuela_notas_quitar_columna,
        name='profesor_escuela_notas_quitar_columna',
    ),
    path(
        'profesor/escuelas/<int:escuela_id>/notas-grilla/certificado/',
        views.profesor_escuela_notas_toggle_certificado,
        name='profesor_escuela_notas_toggle_certificado',
    ),
    path('clases/', views.clases_list, name='clases_list'),
    path('clases/<int:clase_id>/asistencia/', views.asistencia_clase, name='asistencia_clase'),

    # Notas
    path('notas/', views.notas_estudiante, name='notas_estudiante'),
    path('notas/ruta/<int:ruta_id>/', views.notas_estudiante_ruta, name='notas_estudiante_ruta'),

    # Gestión de Matrículas
    path('matriculas/', views.matriculas_list, name='matriculas_list'),
    path('matriculas/<int:matricula_id>/desmatricular/', views.desmatricular_estudiante, name='desmatricular_estudiante'),
]
