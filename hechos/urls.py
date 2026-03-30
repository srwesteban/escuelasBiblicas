from django.urls import path
from . import views

app_name = 'hechos'

urlpatterns = [
    path('', views.hechos_dashboard, name='dashboard'),
    path('dashboard/', views.hechos_dashboard, name='dashboard'),
    path('mi-sede/', views.seleccionar_sede_estudiante, name='seleccionar_sede_estudiante'),
    path('coordinacion/recursos/', views.coordinador_recursos, name='coordinador_recursos'),
    path('coordinacion/logistica/', views.coordinador_logistica, name='coordinador_logistica'),
    path('escuelas/', views.escuelas_disponibles, name='escuelas_disponibles'),
    path('escuelas/<int:edicion_id>/solicitar-matricula/', views.solicitar_matricula, name='solicitar_matricula'),
    path('mis-solicitudes/', views.mis_solicitudes, name='mis_solicitudes'),
    path('solicitudes/', views.solicitudes_matricula_admin, name='solicitudes_matricula_admin'),
    path('solicitudes/<int:solicitud_id>/revisar/', views.revisar_solicitud_matricula, name='revisar_solicitud_matricula'),
    path('mis-solicitudes-especiales/', views.solicitudes_especiales_estudiante, name='solicitudes_especiales_estudiante'),
    path('solicitudes-especiales/', views.solicitudes_especiales_admin, name='solicitudes_especiales_admin'),
    path('solicitudes-especiales/<int:solicitud_id>/revisar/', views.revisar_solicitud_especial_admin, name='revisar_solicitud_especial_admin'),
    
    # Estudiantes
    path('estudiantes/', views.estudiantes_list, name='estudiantes_list'),
    path('estudiantes/crear/', views.crear_estudiante, name='crear_estudiante'),
    path('estudiantes/<int:estudiante_id>/', views.detalle_estudiante, name='detalle_estudiante'),
    path('estudiantes/<int:estudiante_id>/editar/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiantes/<int:estudiante_id>/eliminar/', views.eliminar_estudiante, name='eliminar_estudiante'),
    
    # Profesores
    path('profesores/', views.profesores_list, name='profesores_list'),
    path('profesores/crear/', views.crear_profesor, name='crear_profesor'),
    path('profesores/<int:profesor_id>/', views.detalle_profesor, name='detalle_profesor'),
    path('profesores/<int:profesor_id>/editar/', views.editar_profesor, name='editar_profesor'),
    path('profesores/<int:profesor_id>/eliminar/', views.eliminar_profesor, name='eliminar_profesor'),
    
    # Cursos
    path('cursos/', views.cursos_list, name='cursos_list'),
    path('cursos/crear/', views.crear_curso, name='crear_curso'),
    path('cursos/<int:curso_id>/', views.detalle_curso, name='detalle_curso'),
    path('cursos/<int:curso_id>/editar/', views.editar_curso, name='editar_curso'),
    path('cursos/<int:curso_id>/eliminar/', views.eliminar_curso, name='eliminar_curso'),
    path('cursos/<int:curso_id>/asistencia/', views.tomar_asistencia_curso, name='tomar_asistencia_curso'),
    path('cursos/matricular/', views.matricular_estudiante, name='matricular_estudiante'),
    
    # Rutas de Estudio
    path('rutas-estudio/', views.rutas_estudio_list, name='rutas_estudio_list'),
    path('rutas-estudio/crear/', views.crear_ruta_estudio, name='crear_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/', views.ruta_estudio_detail, name='ruta_estudio_detail'),
    path('rutas-estudio/<int:ruta_id>/editar/', views.editar_ruta_estudio, name='editar_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/eliminar/', views.eliminar_ruta_estudio, name='eliminar_ruta_estudio'),
    path('rutas-estudio/<int:ruta_id>/crear-curso/', views.crear_curso_ruta, name='crear_curso_ruta'),
    
    # Clases
    path('clases/', views.clases_list, name='clases_list'),
    path('clases/<int:clase_id>/asistencia/', views.asistencia_clase, name='asistencia_clase'),
    
    # Notas
    path('notas/', views.notas_estudiante, name='notas_estudiante'),
    path('notas/ruta/<int:ruta_id>/', views.notas_estudiante_ruta, name='notas_estudiante_ruta'),
    path('notas-profesor/', views.notas_profesor, name='notas_profesor'),
    path('notas-curso/<int:curso_id>/', views.notas_curso, name='notas_curso'),
    
    # Progreso del Estudiante
    
    # Gestión de Matrículas
    path('matriculas/', views.matriculas_list, name='matriculas_list'),
    path('matriculas/<int:matricula_id>/desmatricular/', views.desmatricular_estudiante, name='desmatricular_estudiante'),
    
    # Ediciones de Cursos
    path('cursos/<int:curso_id>/ediciones/', views.ediciones_curso_list, name='ediciones_curso_list'),
    path('cursos/<int:curso_id>/ediciones/crear/', views.crear_edicion_curso, name='crear_edicion_curso'),
    path('ediciones/<int:edicion_id>/editar/', views.editar_edicion_curso, name='editar_edicion_curso'),
]
