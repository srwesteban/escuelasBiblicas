from django.urls import path
from . import views

app_name = 'guias'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_guias, name='dashboard'),
    
    # Personas
    path('personas/', views.personas_list, name='personas_list'),
    path('personas/crear/', views.crear_persona, name='crear_persona'),
    path('personas/<int:persona_id>/', views.persona_detail, name='persona_detail'),
    path('personas/<int:persona_id>/editar/', views.editar_persona, name='editar_persona'),
    path('personas/<int:persona_id>/eliminar/', views.eliminar_persona, name='eliminar_persona'),
    path('personas/<int:persona_id>/seguimiento/', views.agregar_seguimiento, name='agregar_seguimiento'),
    
    # Eventos
    path('eventos/', views.eventos_list, name='eventos_list'),
    path('eventos/crear/', views.crear_evento, name='crear_evento'),
    
    # Ministerios
    path('ministerios/', views.ministerios_list, name='ministerios_list'),
    path('ministerios/crear/', views.crear_ministerio, name='crear_ministerio'),
    
    # API endpoints
    path('api/personas/', views.get_personas_ajax, name='get_personas_ajax'),
]
