from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import CoordinadorForm, PastorSedeFormSet, SedeForm
from .models import AppModule, Sede, UserAppPermission
from hechos.models import AdminEscuela, Estudiante, Profesor

User = get_user_model()


def _get_home_redirect(user):
    if user.is_super_admin():
        return 'core:director_dashboard'

    if hasattr(user, 'estudiante_profile') or hasattr(user, 'profesor_profile') or hasattr(user, 'admin_escuela_profile'):
        return 'hechos:dashboard'

    user_permission = UserAppPermission.objects.filter(
        user=user,
        can_view=True,
        app_module__is_active=True,
    ).select_related('app_module').order_by('app_module__order').first()
    if user_permission:
        return user_permission.app_module.url_name

    return 'core:profile'


def inicio(request):
    """
    Landing pública del sistema.
    """
    if request.user.is_authenticated:
        return redirect(_get_home_redirect(request.user))

    return render(request, 'core/inicio.html')


@login_required
def dashboard(request):
    """
    Redirección al inicio real según el usuario.
    """
    return redirect(_get_home_redirect(request.user))


def _director_required(request):
    if not request.user.is_super_admin():
        messages.error(request, 'Solo el director puede acceder a esta sección.')
        return False
    return True


@login_required
def director_dashboard(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    sedes = Sede.objects.all().order_by('nombre')
    sedes_data = []
    for sede in sedes:
        coordinadores = AdminEscuela.objects.filter(sede=sede, is_active=True).select_related('user')
        sedes_data.append({
            'sede': sede,
            'coordinadores_count': coordinadores.count(),
            'coordinadores': coordinadores[:3],
        })

    context = {
        'sedes_data': sedes_data,
    }
    return render(request, 'core/director_dashboard.html', context)


@login_required
def sede_create(request):
    if not _director_required(request):
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = SedeForm(request.POST, request.FILES)
        pastores_formset = PastorSedeFormSet(request.POST, request.FILES, prefix='pastores')
        if form.is_valid() and pastores_formset.is_valid():
            sede = form.save()
            pastores_formset.instance = sede
            pastores_formset.save()
            messages.success(request, f'Sede {sede.nombre} creada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm()
        pastores_formset = PastorSedeFormSet(prefix='pastores')

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
            'pastores_formset': pastores_formset,
            'page_title': 'Crear sede',
        },
    )


@login_required
def sede_edit(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)

    if request.method == 'POST':
        form = SedeForm(request.POST, request.FILES, instance=sede)
        pastores_formset = PastorSedeFormSet(request.POST, request.FILES, instance=sede, prefix='pastores')
        if form.is_valid() and pastores_formset.is_valid():
            sede = form.save()
            pastores_formset.instance = sede
            pastores_formset.save()
            messages.success(request, f'Sede {sede.nombre} actualizada correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = SedeForm(instance=sede)
        pastores_formset = PastorSedeFormSet(instance=sede, prefix='pastores')

    return render(
        request,
        'core/sede_form.html',
        {
            'form': form,
            'pastores_formset': pastores_formset,
            'page_title': 'Editar sede',
            'sede': sede,
        },
    )


@login_required
def sede_delete(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    if request.method == 'POST':
        sede.is_active = False
        sede.save(update_fields=['is_active'])
        messages.success(request, f'Sede {sede.nombre} eliminada correctamente.')
    return redirect('core:director_dashboard')


@login_required
def director_sede_detail(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    coordinadores = AdminEscuela.objects.filter(
        sede=sede,
        is_active=True,
        user__is_active=True,
    ).select_related('user').order_by(
        'user__first_name', 'user__last_name'
    )

    context = {
        'sede': sede,
        'coordinadores': coordinadores,
        'pastores_adicionales': sede.pastores_adicionales.all(),
    }
    return render(request, 'core/director_sede_detail.html', context)


@login_required
def coordinador_create(request, sede_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    hechos_module = AppModule.objects.filter(name='hechos').first()

    if request.method == 'POST':
        form = CoordinadorForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(User, sede, hechos_module)
            messages.success(request, 'Coordinador creado correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = CoordinadorForm()

    context = {
        'form': form,
        'sede': sede,
        'page_title': 'Crear coordinador',
        'submit_label': 'Crear coordinador',
    }
    return render(request, 'core/coordinador_form.html', context)


@login_required
def coordinador_edit(request, sede_id, coordinador_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    admin_profile = get_object_or_404(
        AdminEscuela,
        id=coordinador_id,
        sede=sede,
        is_active=True,
        user__is_active=True,
    )
    hechos_module = AppModule.objects.filter(name='hechos').first()

    if request.method == 'POST':
        form = CoordinadorForm(request.POST, request.FILES, admin_profile=admin_profile)
        if form.is_valid():
            form.save(User, sede, hechos_module)
            messages.success(request, 'Coordinador actualizado correctamente.')
            return redirect('core:director_sede_detail', sede_id=sede.id)
    else:
        form = CoordinadorForm(
            admin_profile=admin_profile,
            initial={
                'first_name': admin_profile.user.first_name,
                'last_name': admin_profile.user.last_name,
                'username': admin_profile.user.username,
                'email': admin_profile.user.email,
                'cargo': admin_profile.cargo,
                'is_active': admin_profile.is_active and admin_profile.user.is_active,
            },
        )

    context = {
        'form': form,
        'sede': sede,
        'coordinador': admin_profile,
        'page_title': 'Editar coordinador',
        'submit_label': 'Guardar cambios',
    }
    return render(request, 'core/coordinador_form.html', context)


@login_required
def coordinador_delete(request, sede_id, coordinador_id):
    if not _director_required(request):
        return redirect('core:dashboard')

    sede = get_object_or_404(Sede, id=sede_id)
    admin_profile = get_object_or_404(
        AdminEscuela,
        id=coordinador_id,
        sede=sede,
        is_active=True,
        user__is_active=True,
    )

    if request.method == 'POST':
        admin_profile.is_active = False
        admin_profile.save(update_fields=['is_active'])
        admin_profile.user.is_active = False
        admin_profile.user.save(update_fields=['is_active'])
        messages.success(request, 'Coordinador eliminado correctamente.')

    return redirect('core:director_sede_detail', sede_id=sede.id)


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
