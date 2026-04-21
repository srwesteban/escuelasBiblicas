from django.contrib import admin
from .models import (
    Estudiante, Profesor, AdminEscuela, Salon, RutaEstudio, Curso, EdicionCurso,
    Matricula, Clase, Asistencia, Nota, ActividadEscuela, EntregaActividad,
    ArchivoRecursoEscuela, EscuelaPrograma, EscuelaProgramaPlantilla, NivelPrograma,
    NivelProgramaPlantilla,
)


@admin.register(Estudiante)
class EstudianteAdmin(admin.ModelAdmin):
    list_display = ('user', 'sede', 'codigo_estudiante', 'iglesia', 'is_active', 'created_at')
    list_filter = ('sede', 'is_active', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'codigo_estudiante', 'iglesia', 'sede__nombre')
    readonly_fields = ('codigo_estudiante', 'created_at', 'updated_at')
    ordering = ('user__first_name', 'user__last_name')
    
    fieldsets = (
        ('Información Personal', {'fields': ('user', 'sede', 'codigo_estudiante', 'fecha_nacimiento')}),
        ('Contacto', {'fields': ('direccion', 'telefono_emergencia', 'contacto_emergencia')}),
        ('Información Adicional', {'fields': ('iglesia', 'notas_medicas')}),
        ('Estado', {'fields': ('is_active', 'created_at', 'updated_at')}),
    )


@admin.register(Profesor)
class ProfesorAdmin(admin.ModelAdmin):
    list_display = ('user', 'sede', 'codigo_profesor', 'especialidad', 'experiencia_anos', 'is_active', 'created_at')
    list_filter = ('sede', 'is_active', 'experiencia_anos', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'codigo_profesor', 'especialidad', 'sede__nombre')
    readonly_fields = ('codigo_profesor', 'created_at', 'updated_at')
    ordering = ('user__first_name', 'user__last_name')
    
    fieldsets = (
        ('Información Personal', {'fields': ('user', 'sede', 'codigo_profesor')}),
        ('Información Profesional', {'fields': ('especialidad', 'experiencia_anos', 'biografia')}),
        ('Estado', {'fields': ('is_active', 'created_at', 'updated_at')}),
    )


@admin.register(AdminEscuela)
class AdminEscuelaAdmin(admin.ModelAdmin):
    list_display = ('user', 'sede', 'cargo', 'is_active', 'created_at')
    list_filter = ('is_active', 'sede', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'sede__nombre', 'cargo')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('user__first_name', 'user__last_name')


@admin.register(NivelProgramaPlantilla)
class NivelProgramaPlantillaAdmin(admin.ModelAdmin):
    list_display = ('jerarquia', 'nombre', 'updated_at')
    ordering = ('jerarquia',)


@admin.register(EscuelaProgramaPlantilla)
class EscuelaProgramaPlantillaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nivel_plantilla', 'tiene_matricula', 'updated_at')
    list_filter = ('nivel_plantilla', 'tiene_matricula')
    search_fields = ('nombre', 'descripcion')
    ordering = ('nivel_plantilla__jerarquia', 'nombre')


@admin.register(NivelPrograma)
class NivelProgramaAdmin(admin.ModelAdmin):
    list_display = ('sede', 'jerarquia', 'nombre', 'is_active', 'updated_at')
    list_filter = ('sede', 'is_active')
    search_fields = ('nombre', 'descripcion', 'sede__nombre')
    ordering = ('sede', 'jerarquia')


@admin.register(EscuelaPrograma)
class EscuelaProgramaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'nivel_programa',
        'sede',
        'tiene_matricula',
        'costo_matricula_cop',
        'is_active',
        'updated_at',
    )
    list_filter = ('nivel_programa', 'sede', 'is_active')
    search_fields = ('nombre', 'descripcion', 'sede__nombre')


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('sede', 'nombre', 'codigo', 'capacidad_plazas', 'escuela', 'is_active', 'updated_at')
    list_filter = ('sede', 'is_active')
    search_fields = ('nombre', 'codigo', 'sede__nombre')
    ordering = ('sede', 'nombre')


@admin.register(RutaEstudio)
class RutaEstudioAdmin(admin.ModelAdmin):
    list_display = ('sede', 'escuela', 'nombre', 'nivel', 'duracion_semanas', 'is_active', 'created_at')
    list_filter = ('sede', 'nivel', 'is_active', 'created_at')
    search_fields = ('nombre', 'descripcion', 'sede__nombre')
    ordering = ('sede', 'nivel', 'nombre')


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('sede', 'nombre', 'ruta_estudio', 'orden', 'duracion_semanas', 'total_estudiantes_inscritos', 'is_active')
    list_filter = ('sede', 'ruta_estudio', 'is_active', 'created_at')
    search_fields = ('nombre', 'descripcion', 'sede__nombre')
    ordering = ('sede', 'ruta_estudio', 'orden', 'nombre')
    
    fieldsets = (
        ('Información Básica', {'fields': ('sede', 'ruta_estudio', 'nombre', 'descripcion')}),
        ('Configuración', {'fields': ('orden', 'duracion_semanas')}),
        ('Estado', {'fields': ('is_active',)}),
    )


@admin.register(EdicionCurso)
class EdicionCursoAdmin(admin.ModelAdmin):
    list_display = ('curso', 'nombre_edicion', 'profesor', 'fecha_inicio', 'fecha_fin', 'estudiantes_inscritos', 'cupos_disponibles', 'is_active')
    list_filter = ('curso__sede', 'curso__ruta_estudio', 'profesor', 'fecha_inicio', 'is_active')
    search_fields = ('curso__nombre', 'nombre_edicion', 'profesor__user__first_name', 'profesor__user__last_name')
    ordering = ('curso', 'fecha_inicio')
    
    fieldsets = (
        ('Información Básica', {'fields': ('curso', 'nombre_edicion', 'profesor')}),
        ('Horario y Lugar', {'fields': ('fecha_inicio', 'fecha_fin', 'horario', 'aula')}),
        ('Capacidad', {'fields': ('cupo_maximo',)}),
        ('Estado', {'fields': ('is_active',)}),
    )


@admin.register(Matricula)
class MatriculaAdmin(admin.ModelAdmin):
    list_display = ('sede', 'estudiante', 'edicion_curso', 'estado', 'fecha_matricula', 'is_active')
    list_filter = ('sede', 'estado', 'is_active', 'fecha_matricula', 'edicion_curso__curso__ruta_estudio')
    search_fields = ('estudiante__user__first_name', 'estudiante__user__last_name', 'edicion_curso__curso__nombre', 'sede__nombre')
    ordering = ('-fecha_matricula',)


@admin.register(Clase)
class ClaseAdmin(admin.ModelAdmin):
    list_display = ('sede', 'edicion_curso', 'numero_clase', 'titulo', 'fecha_clase', 'profesor', 'is_active')
    list_filter = ('sede', 'edicion_curso', 'profesor', 'fecha_clase', 'is_active')
    search_fields = ('titulo', 'descripcion', 'edicion_curso__curso__nombre', 'sede__nombre')
    ordering = ('sede', 'edicion_curso', 'numero_clase')


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('sede', 'estudiante', 'clase', 'estado', 'fecha_registro', 'registrado_por')
    list_filter = ('sede', 'estado', 'fecha_registro', 'clase__edicion_curso__curso')
    search_fields = ('estudiante__user__first_name', 'estudiante__user__last_name', 'clase__titulo', 'sede__nombre')
    ordering = ('-fecha_registro',)


@admin.register(ActividadEscuela)
class ActividadEscuelaAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'escuela', 'tipo', 'fecha_limite', 'puntos_posibles', 'creada_por', 'created_at', 'is_active',
    )
    list_filter = ('sede', 'tipo', 'is_active', 'created_at')
    search_fields = ('titulo', 'instrucciones', 'escuela__nombre', 'sede__nombre')
    ordering = ('-created_at',)
    raw_id_fields = ('escuela', 'creada_por')


@admin.register(EntregaActividad)
class EntregaActividadAdmin(admin.ModelAdmin):
    list_display = (
        'actividad', 'estudiante', 'evaluado_en', 'puntaje_asignado', 'actualizado_en', 'sede',
    )
    list_filter = ('sede', 'evaluado_en')
    search_fields = (
        'actividad__titulo', 'estudiante__user__first_name', 'estudiante__user__last_name',
        'estudiante__user__email',
    )
    raw_id_fields = ('actividad', 'estudiante', 'evaluado_por')
    ordering = ('-actualizado_en',)


@admin.register(ArchivoRecursoEscuela)
class ArchivoRecursoEscuelaAdmin(admin.ModelAdmin):
    list_display = (
        'titulo', 'escuela', 'subido_por', 'created_at', 'is_active', 'sede',
    )
    list_filter = ('sede', 'is_active', 'created_at')
    search_fields = ('titulo', 'descripcion', 'escuela__nombre')
    raw_id_fields = ('escuela', 'subido_por')
    ordering = ('-created_at',)


@admin.register(Nota)
class NotaAdmin(admin.ModelAdmin):
    list_display = ('sede', 'estudiante', 'curso', 'titulo', 'tipo', 'puntaje_obtenido', 'puntaje_maximo', 'porcentaje', 'fecha_evaluacion')
    list_filter = ('sede', 'tipo', 'fecha_evaluacion', 'curso', 'profesor')
    search_fields = ('estudiante__user__first_name', 'estudiante__user__last_name', 'titulo', 'curso__nombre', 'sede__nombre')
    ordering = ('-fecha_evaluacion', 'estudiante__user__first_name')
    
    fieldsets = (
        ('Información Básica', {'fields': ('sede', 'estudiante', 'curso', 'tipo', 'titulo', 'descripcion')}),
        ('Evaluación', {'fields': ('puntaje_obtenido', 'puntaje_maximo', 'fecha_evaluacion', 'profesor')}),
        ('Observaciones', {'fields': ('observaciones',)}),
    )
