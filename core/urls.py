from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'core'

urlpatterns = [
    path('inicio/', views.inicio, name='inicio'),
    path('', views.inicio, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('director/sedes/', views.director_dashboard, name='director_dashboard'),
    path(
        'director/',
        RedirectView.as_view(pattern_name='core:director_dashboard', permanent=True, query_string=True),
        name='director_dashboard_legacy',
    ),
    path(
        'director/importar-seguimiento/',
        views.director_import_seguimiento,
        name='director_import_seguimiento',
    ),
    path('director/programa-escuelas/', views.director_programa_escuelas, name='director_programa_escuelas'),
    path('director/profesores/', views.director_profesores, name='director_profesores'),
    path(
        'director/profesores/<int:profesor_id>/ficha/',
        views.director_profesor_ficha_fragment,
        name='director_profesor_ficha_fragment',
    ),
    path('director/sedes/crear/', views.sede_create, name='sede_create'),
    path('director/sedes/buscar-coordinador/', views.buscar_persona_coordinador, name='buscar_persona_coordinador'),
    path('director/sedes/<int:sede_id>/editar/', views.sede_edit, name='sede_edit'),
    path('director/sedes/<int:sede_id>/eliminar/', views.sede_delete, name='sede_delete'),
    path('director/sedes/<int:sede_id>/reactivar/', views.sede_reactivate, name='sede_reactivate'),
    path('director/sedes/<int:sede_id>/', views.director_sede_detail, name='director_sede_detail'),
    path('director/sedes/<int:sede_id>/informacion/', views.coordinador_sede_info, name='coordinador_sede_info'),
    path('director/sedes/<int:sede_id>/equipo/', views.coordinador_sede_equipo, name='coordinador_sede_equipo'),
    path('director/sedes/<int:sede_id>/coordinadores/crear/', views.coordinador_create, name='coordinador_create'),
    path(
        'director/sedes/<int:sede_id>/coordinadores/<int:coordinador_id>/ficha/',
        views.director_coordinador_ficha_fragment,
        name='director_coordinador_ficha_fragment',
    ),
    path('director/sedes/<int:sede_id>/coordinadores/<int:coordinador_id>/editar/', views.coordinador_edit, name='coordinador_edit'),
    path('director/sedes/<int:sede_id>/coordinadores/<int:coordinador_id>/eliminar/', views.coordinador_delete, name='coordinador_delete'),
    path('profile/', views.profile, name='profile'),
    path('notificaciones/', views.mis_notificaciones, name='mis_notificaciones'),
    path('api/modules/', views.get_user_modules, name='user_modules'),
    path('api/signup/check-documento/', views.signup_check_documento, name='signup_check_documento'),
]
