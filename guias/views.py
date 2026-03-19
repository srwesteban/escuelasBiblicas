from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, timedelta

from .models import PersonaNueva, Seguimiento, EventoEspecial, Ministerio, InteresMinisterio
from core.models import Sede


@login_required
def dashboard_guias(request):
    """
    Dashboard principal de la app Guias
    """
    # Obtener estadísticas básicas
    total_personas = PersonaNueva.objects.filter(is_active=True).count()
    personas_nuevas_mes = PersonaNueva.objects.filter(
        is_active=True,
        fecha_registro__gte=timezone.now().replace(day=1)
    ).count()
    
    # Personas por estado
    estados_stats = {}
    for estado, _ in PersonaNueva.ESTADO_CHOICES:
        count = PersonaNueva.objects.filter(is_active=True, estado=estado).count()
        estados_stats[estado] = count
    
    # Seguimientos pendientes
    seguimientos_pendientes = Seguimiento.objects.filter(
        fecha_proxima_accion__lte=timezone.now().date() + timedelta(days=7),
        fecha_proxima_accion__isnull=False
    ).count()
    
    # Próximos eventos
    proximos_eventos = EventoEspecial.objects.filter(
        fecha_evento__gte=timezone.now(),
        is_active=True
    ).order_by('fecha_evento')[:5]
    
    context = {
        'total_personas': total_personas,
        'personas_nuevas_mes': personas_nuevas_mes,
        'estados_stats': estados_stats,
        'seguimientos_pendientes': seguimientos_pendientes,
        'proximos_eventos': proximos_eventos,
    }
    
    return render(request, 'guias/dashboard_modern.html', context)


@login_required
def personas_list(request):
    """
    Lista de personas nuevas con filtros y búsqueda
    """
    personas = PersonaNueva.objects.filter(is_active=True)
    
    # Filtros
    estado = request.GET.get('estado')
    sede_id = request.GET.get('sede')
    search = request.GET.get('search')
    
    if estado:
        personas = personas.filter(estado=estado)
    
    if sede_id:
        personas = personas.filter(sede_id=sede_id)
    
    if search:
        personas = personas.filter(
            Q(nombre__icontains=search) |
            Q(apellido__icontains=search) |
            Q(email__icontains=search) |
            Q(telefono__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(personas.order_by('-fecha_registro'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones para filtros
    sedes = Sede.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'sedes': sedes,
        'estados': PersonaNueva.ESTADO_CHOICES,
        'filtros': {
            'estado': estado,
            'sede': sede_id,
            'search': search,
        }
    }
    
    return render(request, 'guias/personas_list_modern.html', context)


@login_required
def persona_detail(request, persona_id):
    """
    Detalle de una persona nueva
    """
    persona = get_object_or_404(PersonaNueva, id=persona_id, is_active=True)
    seguimientos = persona.seguimientos.all().order_by('-fecha_seguimiento')
    intereses = persona.intereses_ministerio.all()
    
    context = {
        'persona': persona,
        'seguimientos': seguimientos,
        'intereses': intereses,
    }
    
    return render(request, 'guias/persona_detail_modern.html', context)


@login_required
def crear_persona(request):
    """
    Crear nueva persona
    """
    if request.method == 'POST':
        try:
            # Crear persona
            persona = PersonaNueva.objects.create(
                nombre=request.POST.get('nombre'),
                apellido=request.POST.get('apellido'),
                email=request.POST.get('email', ''),
                telefono=request.POST.get('telefono', ''),
                fecha_nacimiento=request.POST.get('fecha_nacimiento') or None,
                genero=request.POST.get('genero', ''),
                direccion=request.POST.get('direccion', ''),
                ciudad=request.POST.get('ciudad', ''),
                codigo_postal=request.POST.get('codigo_postal', ''),
                sede_id=request.POST.get('sede') or None,
                estado=request.POST.get('estado', 'nuevo'),
                fecha_primera_visita=request.POST.get('fecha_primera_visita') or None,
                como_conocio=request.POST.get('como_conocio', ''),
                intereses=request.POST.get('intereses', ''),
                necesidades_especiales=request.POST.get('necesidades_especiales', ''),
                notas=request.POST.get('notas', ''),
                referido_por=request.POST.get('referido_por', ''),
                responsable_seguimiento_id=request.POST.get('responsable_seguimiento') or None,
            )
            
            messages.success(request, f'Persona {persona.nombre_completo} registrada exitosamente.')
            return redirect('guias:persona_detail', persona_id=persona.id)
            
        except Exception as e:
            messages.error(request, f'Error al crear la persona: {str(e)}')
    
    # Opciones para el formulario
    sedes = Sede.objects.filter(is_active=True)
    usuarios = request.user.__class__.objects.filter(is_active=True)
    
    context = {
        'sedes': sedes,
        'usuarios': usuarios,
        'estados': PersonaNueva.ESTADO_CHOICES,
        'generos': PersonaNueva.GENERO_CHOICES,
    }
    
    return render(request, 'guias/crear_persona_modern.html', context)


@login_required
def editar_persona(request, persona_id):
    """
    Editar persona existente
    """
    persona = get_object_or_404(PersonaNueva, id=persona_id, is_active=True)
    
    if request.method == 'POST':
        try:
            persona.nombre = request.POST.get('nombre')
            persona.apellido = request.POST.get('apellido')
            persona.email = request.POST.get('email', '')
            persona.telefono = request.POST.get('telefono', '')
            persona.fecha_nacimiento = request.POST.get('fecha_nacimiento') or None
            persona.genero = request.POST.get('genero', '')
            persona.direccion = request.POST.get('direccion', '')
            persona.ciudad = request.POST.get('ciudad', '')
            persona.codigo_postal = request.POST.get('codigo_postal', '')
            persona.sede_id = request.POST.get('sede') or None
            persona.estado = request.POST.get('estado', 'nuevo')
            persona.fecha_primera_visita = request.POST.get('fecha_primera_visita') or None
            persona.como_conocio = request.POST.get('como_conocio', '')
            persona.intereses = request.POST.get('intereses', '')
            persona.necesidades_especiales = request.POST.get('necesidades_especiales', '')
            persona.notas = request.POST.get('notas', '')
            persona.referido_por = request.POST.get('referido_por', '')
            persona.responsable_seguimiento_id = request.POST.get('responsable_seguimiento') or None
            persona.save()
            
            messages.success(request, f'Persona {persona.nombre_completo} actualizada exitosamente.')
            return redirect('guias:persona_detail', persona_id=persona.id)
            
        except Exception as e:
            messages.error(request, f'Error al actualizar la persona: {str(e)}')
    
    # Opciones para el formulario
    sedes = Sede.objects.filter(is_active=True)
    usuarios = request.user.__class__.objects.filter(is_active=True)
    
    context = {
        'persona': persona,
        'sedes': sedes,
        'usuarios': usuarios,
        'estados': PersonaNueva.ESTADO_CHOICES,
        'generos': PersonaNueva.GENERO_CHOICES,
    }
    
    return render(request, 'guias/editar_persona_modern.html', context)


@login_required
def agregar_seguimiento(request, persona_id):
    """
    Agregar seguimiento a una persona
    """
    persona = get_object_or_404(PersonaNueva, id=persona_id, is_active=True)
    
    if request.method == 'POST':
        try:
            seguimiento = Seguimiento.objects.create(
                persona=persona,
                tipo=request.POST.get('tipo'),
                fecha_seguimiento=request.POST.get('fecha_seguimiento'),
                descripcion=request.POST.get('descripcion'),
                resultado=request.POST.get('resultado', ''),
                proxima_accion=request.POST.get('proxima_accion', ''),
                fecha_proxima_accion=request.POST.get('fecha_proxima_accion') or None,
                realizado_por=request.user,
            )
            
            messages.success(request, 'Seguimiento agregado exitosamente.')
            return redirect('guias:persona_detail', persona_id=persona.id)
            
        except Exception as e:
            messages.error(request, f'Error al agregar seguimiento: {str(e)}')
    
    context = {
        'persona': persona,
        'tipos': Seguimiento.TIPO_CHOICES,
    }
    
    return render(request, 'guias/agregar_seguimiento_modern.html', context)


@login_required
@require_http_methods(["POST"])
def eliminar_persona(request, persona_id):
    """
    Eliminar persona (soft delete)
    """
    persona = get_object_or_404(PersonaNueva, id=persona_id, is_active=True)
    
    try:
        persona.is_active = False
        persona.save()
        messages.success(request, f'Persona {persona.nombre_completo} eliminada exitosamente.')
    except Exception as e:
        messages.error(request, f'Error al eliminar la persona: {str(e)}')
    
    return redirect('guias:personas_list')


# Vistas adicionales para eventos y ministerios
@login_required
def eventos_list(request):
    """
    Lista de eventos especiales
    """
    eventos = EventoEspecial.objects.filter(is_active=True)
    
    # Filtros
    tipo = request.GET.get('tipo')
    sede_id = request.GET.get('sede')
    
    if tipo:
        eventos = eventos.filter(tipo=tipo)
    
    if sede_id:
        eventos = eventos.filter(sede_id=sede_id)
    
    # Paginación
    paginator = Paginator(eventos.order_by('-fecha_evento'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones para filtros
    sedes = Sede.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'sedes': sedes,
        'tipos': EventoEspecial.TIPO_CHOICES,
        'filtros': {
            'tipo': tipo,
            'sede': sede_id,
        }
    }
    
    return render(request, 'guias/eventos_list_modern.html', context)


@login_required
def crear_evento(request):
    """
    Crear nuevo evento especial
    """
    if request.method == 'POST':
        try:
            evento = EventoEspecial.objects.create(
                nombre=request.POST.get('nombre'),
                tipo=request.POST.get('tipo'),
                descripcion=request.POST.get('descripcion', ''),
                fecha_evento=request.POST.get('fecha_evento'),
                lugar=request.POST.get('lugar', ''),
                sede_id=request.POST.get('sede') or None,
                responsable=request.user,
            )
            
            # Agregar personas invitadas
            personas_ids = request.POST.getlist('personas_invitadas')
            if personas_ids:
                evento.personas_invitadas.set(personas_ids)
            
            messages.success(request, f'Evento {evento.nombre} creado exitosamente.')
            return redirect('guias:eventos_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear el evento: {str(e)}')
    
    # Opciones para el formulario
    sedes = Sede.objects.filter(is_active=True)
    personas = PersonaNueva.objects.filter(is_active=True)
    
    context = {
        'sedes': sedes,
        'personas': personas,
        'tipos': EventoEspecial.TIPO_CHOICES,
    }
    
    return render(request, 'guias/crear_evento_modern.html', context)


@login_required
def ministerios_list(request):
    """
    Lista de ministerios disponibles
    """
    ministerios = Ministerio.objects.filter(is_active=True)
    
    # Filtros
    sede_id = request.GET.get('sede')
    if sede_id:
        ministerios = ministerios.filter(sede_id=sede_id)
    
    # Paginación
    paginator = Paginator(ministerios.order_by('nombre'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Opciones para filtros
    sedes = Sede.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'sedes': sedes,
        'filtros': {
            'sede': sede_id,
        }
    }
    
    return render(request, 'guias/ministerios_list_modern.html', context)


@login_required
def crear_ministerio(request):
    """
    Crear nuevo ministerio
    """
    if request.method == 'POST':
        try:
            ministerio = Ministerio.objects.create(
                nombre=request.POST.get('nombre'),
                descripcion=request.POST.get('descripcion', ''),
                responsable_id=request.POST.get('responsable') or None,
                sede_id=request.POST.get('sede') or None,
            )
            
            messages.success(request, f'Ministerio {ministerio.nombre} creado exitosamente.')
            return redirect('guias:ministerios_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear el ministerio: {str(e)}')
    
    # Opciones para el formulario
    sedes = Sede.objects.filter(is_active=True)
    usuarios = request.user.__class__.objects.filter(is_active=True)
    
    context = {
        'sedes': sedes,
        'usuarios': usuarios,
    }
    
    return render(request, 'guias/crear_ministerio_modern.html', context)


# API endpoints para AJAX
@login_required
def get_personas_ajax(request):
    """
    Obtener lista de personas para AJAX
    """
    search = request.GET.get('search', '')
    personas = PersonaNueva.objects.filter(is_active=True)
    
    if search:
        personas = personas.filter(
            Q(nombre__icontains=search) |
            Q(apellido__icontains=search) |
            Q(email__icontains=search)
        )
    
    data = []
    for persona in personas[:10]:  # Limitar a 10 resultados
        data.append({
            'id': persona.id,
            'nombre': persona.nombre_completo,
            'email': persona.email,
            'telefono': persona.telefono,
        })
    
    return JsonResponse(data, safe=False)