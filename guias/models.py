from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class PersonaNueva(models.Model):
    """
    Modelo para registrar personas nuevas en la iglesia
    """
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('visitante', 'Visitante'),
        ('interesado', 'Interesado'),
        ('miembro', 'Miembro'),
        ('inactivo', 'Inactivo'),
    ]
    
    GENERO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
    ]
    
    # Información personal
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    email = models.EmailField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES, blank=True)
    
    # Información de contacto
    direccion = models.TextField(blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    codigo_postal = models.CharField(max_length=10, blank=True)
    
    # Información de la iglesia
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='personas_nuevas', null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='nuevo')
    fecha_primera_visita = models.DateField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    # Información adicional
    como_conocio = models.CharField(max_length=200, blank=True, help_text="¿Cómo conoció la iglesia?")
    intereses = models.TextField(blank=True, help_text="Intereses espirituales o ministerios")
    necesidades_especiales = models.TextField(blank=True, help_text="Necesidades especiales o solicitudes")
    notas = models.TextField(blank=True, help_text="Notas adicionales")
    
    # Referencias
    referido_por = models.CharField(max_length=200, blank=True, help_text="Persona que lo refirió")
    responsable_seguimiento = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                               related_name='personas_seguimiento', 
                                               help_text="Persona responsable del seguimiento")
    
    # Control
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Persona Nueva'
        verbose_name_plural = 'Personas Nuevas'
        ordering = ['-fecha_registro', 'nombre', 'apellido']
    
    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"
    
    @property
    def edad(self):
        if self.fecha_nacimiento:
            from datetime import date
            today = date.today()
            return today.year - self.fecha_nacimiento.year - (
                (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
        return None


class Seguimiento(models.Model):
    """
    Registro de seguimiento a personas nuevas
    """
    TIPO_CHOICES = [
        ('llamada', 'Llamada telefónica'),
        ('visita', 'Visita personal'),
        ('email', 'Correo electrónico'),
        ('mensaje', 'Mensaje de texto'),
        ('reunion', 'Reunión'),
        ('evento', 'Evento especial'),
        ('otro', 'Otro'),
    ]
    
    persona = models.ForeignKey(PersonaNueva, on_delete=models.CASCADE, related_name='seguimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    fecha_seguimiento = models.DateTimeField()
    descripcion = models.TextField()
    resultado = models.TextField(blank=True, help_text="Resultado del seguimiento")
    proxima_accion = models.TextField(blank=True, help_text="Próxima acción a realizar")
    fecha_proxima_accion = models.DateField(blank=True, null=True)
    
    # Responsable del seguimiento
    realizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                    related_name='seguimientos_realizados')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Seguimiento'
        verbose_name_plural = 'Seguimientos'
        ordering = ['-fecha_seguimiento']
    
    def __str__(self):
        return f"{self.persona.nombre_completo} - {self.get_tipo_display()} ({self.fecha_seguimiento.strftime('%d/%m/%Y')})"


class EventoEspecial(models.Model):
    """
    Eventos especiales para personas nuevas (bautismos, clases de nuevos miembros, etc.)
    """
    TIPO_CHOICES = [
        ('bautismo', 'Bautismo'),
        ('clase_nuevos', 'Clase de Nuevos Miembros'),
        ('retiro', 'Retiro'),
        ('conferencia', 'Conferencia'),
        ('servicio_especial', 'Servicio Especial'),
        ('otro', 'Otro'),
    ]
    
    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descripcion = models.TextField(blank=True)
    fecha_evento = models.DateTimeField()
    lugar = models.CharField(max_length=200, blank=True)
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='eventos_especiales', null=True, blank=True)
    
    # Participantes
    personas_invitadas = models.ManyToManyField(PersonaNueva, related_name='eventos_invitado', blank=True)
    personas_confirmadas = models.ManyToManyField(PersonaNueva, related_name='eventos_confirmado', blank=True)
    
    # Organización
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='eventos_responsable')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Evento Especial'
        verbose_name_plural = 'Eventos Especiales'
        ordering = ['-fecha_evento']
    
    def __str__(self):
        return f"{self.nombre} - {self.fecha_evento.strftime('%d/%m/%Y')}"
    
    @property
    def total_invitados(self):
        return self.personas_invitadas.count()
    
    @property
    def total_confirmados(self):
        return self.personas_confirmadas.count()
    
    @property
    def porcentaje_confirmacion(self):
        if self.total_invitados == 0:
            return 0
        return (self.total_confirmados / self.total_invitados) * 100


class Ministerio(models.Model):
    """
    Ministerios disponibles para personas nuevas
    """
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='ministerios_responsable')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='ministerios', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Ministerio'
        verbose_name_plural = 'Ministerios'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class InteresMinisterio(models.Model):
    """
    Intereses de personas nuevas en ministerios específicos
    """
    persona = models.ForeignKey(PersonaNueva, on_delete=models.CASCADE, related_name='intereses_ministerio')
    ministerio = models.ForeignKey(Ministerio, on_delete=models.CASCADE, related_name='personas_interesadas')
    nivel_interes = models.CharField(max_length=20, choices=[
        ('bajo', 'Bajo'),
        ('medio', 'Medio'),
        ('alto', 'Alto'),
    ], default='medio')
    notas = models.TextField(blank=True)
    fecha_interes = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Interés en Ministerio'
        verbose_name_plural = 'Intereses en Ministerios'
        unique_together = ['persona', 'ministerio']
        ordering = ['-fecha_interes']
    
    def __str__(self):
        return f"{self.persona.nombre_completo} - {self.ministerio.nombre} ({self.get_nivel_interes_display()})"