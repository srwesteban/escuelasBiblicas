from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import AppModule, UserAppPermission
from hechos.models import Estudiante, Profesor, AdminEscuela


@login_required
def dashboard(request):
    """
    Dashboard principal del sistema
    """
    # Obtener módulos disponibles para el usuario
    available_modules = []
    
    if request.user.is_super_admin():
        # Super admin ve todos los módulos activos
        available_modules = AppModule.objects.filter(is_active=True).order_by('order')
    elif request.user.is_app_admin():
        # Admin de app ve módulos según permisos
        user_permissions = UserAppPermission.objects.filter(
            user=request.user,
            can_view=True
        ).select_related('app_module')
        available_modules = [perm.app_module for perm in user_permissions if perm.app_module.is_active]
    else:
        # Usuario normal ve módulos según permisos
        user_permissions = UserAppPermission.objects.filter(
            user=request.user,
            can_view=True
        ).select_related('app_module')
        available_modules = [perm.app_module for perm in user_permissions if perm.app_module.is_active]
    
    context = {
        'available_modules': available_modules,
    }
    
    return render(request, 'core/dashboard_modern.html', context)


@login_required
def profile(request):
    """
    Vista del perfil del usuario
    """
    # Obtener perfiles específicos del usuario
    estudiante_profile = None
    profesor_profile = None
    admin_escuela_profile = None
    
    try:
        estudiante_profile = request.user.estudiante_profile
    except:
        pass
    
    try:
        profesor_profile = request.user.profesor_profile
    except:
        pass
    
    try:
        admin_escuela_profile = request.user.admin_escuela_profile
    except:
        pass
    
    context = {
        'estudiante_profile': estudiante_profile,
        'profesor_profile': profesor_profile,
        'admin_escuela_profile': admin_escuela_profile,
    }
    
    return render(request, 'core/profile_modern.html', context)


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
