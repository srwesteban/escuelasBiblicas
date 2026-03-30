from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('inicio/', views.inicio, name='inicio'),
    path('', views.inicio, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('director/', views.director_dashboard, name='director_dashboard'),
    path('direccion/sedes/crear/', views.sede_create, name='sede_create'),
    path('direccion/sedes/<int:sede_id>/editar/', views.sede_edit, name='sede_edit'),
    path('direccion/sedes/<int:sede_id>/eliminar/', views.sede_delete, name='sede_delete'),
    path('direccion/sedes/<int:sede_id>/', views.director_sede_detail, name='director_sede_detail'),
    path('direccion/sedes/<int:sede_id>/escuelas/', views.coordinador_sede_escuelas, name='coordinador_sede_escuelas'),
    path('direccion/sedes/<int:sede_id>/escuelas/<int:escuela_id>/editar/', views.coordinador_sede_escuela_edit, name='coordinador_sede_escuela_edit'),
    path('direccion/sedes/<int:sede_id>/escuelas/<int:escuela_id>/eliminar/', views.coordinador_sede_escuela_delete, name='coordinador_sede_escuela_delete'),
    path('direccion/sedes/<int:sede_id>/equipo/', views.coordinador_sede_equipo, name='coordinador_sede_equipo'),
    path('direccion/sedes/<int:sede_id>/coordinadores/crear/', views.coordinador_create, name='coordinador_create'),
    path('direccion/sedes/<int:sede_id>/coordinadores/<int:coordinador_id>/editar/', views.coordinador_edit, name='coordinador_edit'),
    path('direccion/sedes/<int:sede_id>/coordinadores/<int:coordinador_id>/eliminar/', views.coordinador_delete, name='coordinador_delete'),
    path('profile/', views.profile, name='profile'),
    path('api/modules/', views.get_user_modules, name='user_modules'),
]
