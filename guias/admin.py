from django.contrib import admin
from .models import PersonaNueva, Seguimiento, EventoEspecial, Ministerio, InteresMinisterio


@admin.register(PersonaNueva)
class PersonaNuevaAdmin(admin.ModelAdmin):
    list_display = ['nombre_completo', 'email', 'telefono', 'estado', 'sede', 'fecha_registro']
    list_filter = ['estado', 'sede', 'genero', 'fecha_registro']
    search_fields = ['nombre', 'apellido', 'email', 'telefono']
    readonly_fields = ['fecha_registro', 'created_at', 'updated_at']
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'apellido', 'email', 'telefono', 'fecha_nacimiento', 'genero')
        }),
        ('Información de Contacto', {
            'fields': ('direccion', 'ciudad', 'codigo_postal')
        }),
        ('Información de la Iglesia', {
            'fields': ('sede', 'estado', 'fecha_primera_visita', 'como_conocio')
        }),
        ('Información Adicional', {
            'fields': ('intereses', 'necesidades_especiales', 'notas', 'referido_por', 'responsable_seguimiento')
        }),
        ('Control', {
            'fields': ('is_active', 'fecha_registro', 'created_at', 'updated_at')
        }),
    )


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ['persona', 'tipo', 'fecha_seguimiento', 'realizado_por']
    list_filter = ['tipo', 'fecha_seguimiento', 'realizado_por']
    search_fields = ['persona__nombre', 'persona__apellido', 'descripcion']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(EventoEspecial)
class EventoEspecialAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'tipo', 'fecha_evento', 'lugar', 'sede', 'responsable']
    list_filter = ['tipo', 'sede', 'fecha_evento', 'is_active']
    search_fields = ['nombre', 'descripcion', 'lugar']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['personas_invitadas', 'personas_confirmadas']


@admin.register(Ministerio)
class MinisterioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'responsable', 'sede', 'is_active']
    list_filter = ['sede', 'is_active']
    search_fields = ['nombre', 'descripcion']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(InteresMinisterio)
class InteresMinisterioAdmin(admin.ModelAdmin):
    list_display = ['persona', 'ministerio', 'nivel_interes', 'fecha_interes']
    list_filter = ['nivel_interes', 'fecha_interes', 'ministerio']
    search_fields = ['persona__nombre', 'persona__apellido', 'ministerio__nombre']