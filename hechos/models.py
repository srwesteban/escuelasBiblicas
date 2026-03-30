from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def default_anio_escuela():
    return timezone.now().year


class Estudiante(models.Model):
    """
    Perfil de estudiante en el módulo Hechos
    """
    class TipoDocumento(models.TextChoices):
        CC = "CC", _("Cedula de ciudadania")
        TI = "TI", _("Tarjeta de identidad")
        CE = "CE", _("Cedula de extranjeria")
        PAS = "PAS", _("Pasaporte")

    class PeticionArea(models.TextChoices):
        SALUD = "salud", _("Salud")
        FAMILIAR = "familiar", _("Familiar")
        FINANCIERA = "financiera", _("Financiera")
        EDUCACION = "educacion", _("Educación")
        LABORAL = "laboral", _("Laboral")
        OTRO = "otro", _("Otro")

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estudiante_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='estudiantes', null=True, blank=True)
    codigo_estudiante = models.CharField(max_length=20, blank=True, null=True)
    tipo_documento = models.CharField(max_length=3, choices=TipoDocumento.choices, default=TipoDocumento.CC)
    numero_documento = models.CharField(max_length=30, blank=True, default="")
    fecha_nacimiento = models.DateField(blank=True, null=True)
    direccion = models.TextField(blank=True)
    iglesia = models.CharField(max_length=200, blank=True)
    telefono_emergencia = models.CharField(max_length=20, blank=True)
    contacto_emergencia = models.CharField(max_length=100, blank=True)
    peticion_texto = models.TextField(blank=True, default="")
    peticion_area = models.CharField(
        max_length=20,
        choices=PeticionArea.choices,
        blank=True,
        default="",
    )
    notas_medicas = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Estudiante'
        verbose_name_plural = 'Estudiantes'
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} (Estudiante)"
    
    def save(self, *args, **kwargs):
        if not self.codigo_estudiante:
            # Generar código automático si no existe (único por sede)
            last_estudiante = Estudiante.objects.filter(sede=self.sede).order_by('-id').first()
            if last_estudiante and last_estudiante.codigo_estudiante:
                try:
                    last_num = int(last_estudiante.codigo_estudiante.split('-')[-1])
                    self.codigo_estudiante = f"EST-{last_num + 1:04d}"
                except:
                    self.codigo_estudiante = "EST-0001"
            else:
                self.codigo_estudiante = "EST-0001"
        super().save(*args, **kwargs)


class Profesor(models.Model):
    """
    Perfil de profesor en el módulo Hechos
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profesor_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='profesores', null=True, blank=True)
    codigo_profesor = models.CharField(max_length=20, blank=True, null=True)
    especialidad = models.CharField(max_length=200, blank=True)
    experiencia_anos = models.PositiveIntegerField(default=0)
    biografia = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Profesor'
        verbose_name_plural = 'Profesores'
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} (Profesor)"
    
    def save(self, *args, **kwargs):
        if not self.codigo_profesor:
            # Generar código automático si no existe (único por sede)
            last_profesor = Profesor.objects.filter(sede=self.sede).order_by('-id').first()
            if last_profesor and last_profesor.codigo_profesor:
                try:
                    last_num = int(last_profesor.codigo_profesor.split('-')[-1])
                    self.codigo_profesor = f"PROF-{last_num + 1:04d}"
                except:
                    self.codigo_profesor = "PROF-0001"
            else:
                self.codigo_profesor = "PROF-0001"
        super().save(*args, **kwargs)


class AdminEscuela(models.Model):
    """
    Perfil de administrador de escuela en el módulo Hechos
    """

    class TipoCoordinador(models.TextChoices):
        SEDE = 'sede', _('Coordinador de sede')
        ACADEMICO = 'academico', _('Coordinador académico')
        PEDAGOGICO = 'pedagogico', _('Coordinador pedagógico')
        FINANCIERO = 'financiero', _('Coordinador financiero')
        LOGISTICO = 'logistico', _('Coordinador logístico')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_escuela_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='admins_escuela', null=True, blank=True)
    cargo = models.CharField(max_length=200)
    tipo_coordinador = models.CharField(
        max_length=20,
        choices=TipoCoordinador.choices,
        default=TipoCoordinador.ACADEMICO,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Admin de Escuela'
        verbose_name_plural = 'Admins de Escuela'
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} (Admin - {self.sede.nombre})"

    @classmethod
    def cargo_para_tipo(cls, tipo: str, sede_nombre: str) -> str:
        label = dict(cls.TipoCoordinador.choices).get(tipo, '')
        if label:
            return f"{label} — {sede_nombre}"
        return f"Coordinador — {sede_nombre}"


class Escuela(models.Model):
    """
    Unidad académica principal visible para el estudiante.
    """

    class Ciclo(models.TextChoices):
        A = 'A', _('Ciclo A')
        B = 'B', _('Ciclo B')

    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='escuelas', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    anio = models.PositiveIntegerField(
        default=default_anio_escuela,
        verbose_name=_('Año'),
        help_text=_('Año de referencia (por defecto el año en curso).'),
    )
    ciclo = models.CharField(
        max_length=1,
        choices=Ciclo.choices,
        default=Ciclo.A,
        verbose_name=_('Ciclo'),
    )
    grupo = models.PositiveIntegerField(
        default=1,
        verbose_name=_('Grupo'),
    )
    maestro = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escuelas_dirigidas',
        verbose_name=_('Maestro asignado'),
        help_text=_('Profesor responsable; puede quedar por asignar hasta definirlo.'),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Escuela'
        verbose_name_plural = 'Escuelas'
        ordering = ['-anio', 'ciclo', 'grupo', 'nombre']
        unique_together = [['sede', 'nombre', 'anio', 'ciclo', 'grupo']]

    def __str__(self):
        return self.nombre

    def titulo_tarjeta(self) -> str:
        return f'{self.nombre} — {self.anio} · Ciclo {self.ciclo} · Grupo {self.grupo}'


class RutaEstudio(models.Model):
    """
    Niveles dinámicos que viven dentro de una escuela.
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='rutas_estudio', null=True, blank=True)
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name='niveles', null=True, blank=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    duracion_semanas = models.PositiveIntegerField(default=12)
    nivel = models.CharField(max_length=50, choices=[
        ('basico', 'Básico'),
        ('intermedio', 'Intermedio'),
        ('avanzado', 'Avanzado'),
    ], default='basico')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Nivel'
        verbose_name_plural = 'Niveles'
        ordering = ['escuela__nombre', 'nivel', 'nombre']
    
    def __str__(self):
        if self.escuela:
            return f"{self.escuela.nombre} - {self.nombre}"
        return self.nombre


class Curso(models.Model):
    """
    Plantilla de curso que puede tener múltiples ediciones
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='cursos', null=True, blank=True)
    ruta_estudio = models.ForeignKey(RutaEstudio, on_delete=models.CASCADE, related_name='cursos')
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=1, help_text="Orden en la secuencia de la ruta de estudio")
    duracion_semanas = models.PositiveIntegerField(default=4, help_text="Duración en semanas")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'
        ordering = ['ruta_estudio', 'orden', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} - {self.ruta_estudio.nombre}"

    @property
    def escuela(self):
        return self.ruta_estudio.escuela

    @property
    def nivel(self):
        return self.ruta_estudio
    
    @property
    def total_estudiantes_inscritos(self):
        """Total de estudiantes en todas las ediciones activas"""
        return EdicionCurso.objects.filter(
            curso=self, 
            is_active=True
        ).aggregate(
            total=models.Count('matriculas', filter=models.Q(matriculas__is_active=True))
        )['total'] or 0


class EdicionCurso(models.Model):
    """
    Edición específica de un curso (grupo de estudiantes)
    """
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='ediciones')
    nombre_edicion = models.CharField(max_length=200, help_text="Ej: Grupo A, Matutino, Vespertino")
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True, blank=True, related_name='ediciones_curso')
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    horario = models.CharField(max_length=100, help_text="Ej: Lunes y Miércoles 7:00 PM")
    aula = models.CharField(max_length=50, blank=True)
    cupo_maximo = models.PositiveIntegerField(default=30, help_text="Cupo máximo de estudiantes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Edición de Curso'
        verbose_name_plural = 'Ediciones de Curso'
        ordering = ['curso', 'fecha_inicio']
        unique_together = ['curso', 'nombre_edicion']
    
    def __str__(self):
        return f"{self.curso.nombre} - {self.nombre_edicion}"
    
    @property
    def estudiantes_inscritos(self):
        return self.matriculas.filter(is_active=True).count()
    
    @property
    def cupos_disponibles(self):
        return max(0, self.cupo_maximo - self.estudiantes_inscritos)
    
    @property
    def porcentaje_ocupacion(self):
        if self.cupo_maximo == 0:
            return 0
        return (self.estudiantes_inscritos / self.cupo_maximo) * 100


class SolicitudMatricula(models.Model):
    """
    Solicitud previa a la matrícula aprobada por el profesor.
    """
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]

    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='solicitudes_matricula')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='solicitudes_matricula')
    edicion_curso = models.ForeignKey(EdicionCurso, on_delete=models.CASCADE, related_name='solicitudes_matricula')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    pago_validado = models.BooleanField(default=False)
    observaciones = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_matricula_revisadas',
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Solicitud de Matrícula'
        verbose_name_plural = 'Solicitudes de Matrícula'
        ordering = ['-fecha_solicitud']
        unique_together = ['estudiante', 'edicion_curso']

    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} -> {self.edicion_curso}"


class NotificacionEstudiante(models.Model):
    class Tipo(models.TextChoices):
        APROBACION = 'aprobacion', _('Aprobación')
        RECHAZO = 'rechazo', _('Rechazo')
        INFO = 'info', _('Información')

    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='notificaciones')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.INFO)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField(blank=True)
    leida = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notificación de estudiante'
        verbose_name_plural = 'Notificaciones de estudiante'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.titulo}"


class SolicitudEspecialEstudiante(models.Model):
    class Tipo(models.TextChoices):
        SALUD = 'salud', _('Salud')
        FAMILIAR = 'familiar', _('Familiar')
        ECONOMICA = 'economica', _('Económica')
        ACADEMICA = 'academica', _('Académica')
        OTRA = 'otra', _('Otra')

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', _('Pendiente')
        ATENDIDA = 'atendida', _('Atendida')
        CERRADA = 'cerrada', _('Cerrada')

    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='solicitudes_especiales')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='solicitudes_especiales')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OTRA)
    asunto = models.CharField(max_length=180)
    descripcion = models.TextField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    observaciones = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_especiales_revisadas',
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Solicitud especial'
        verbose_name_plural = 'Solicitudes especiales'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.asunto}"


class Matricula(models.Model):
    """
    Matrícula de estudiantes en ediciones de cursos
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='matriculas', null=True, blank=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='matriculas')
    edicion_curso = models.ForeignKey(EdicionCurso, on_delete=models.CASCADE, related_name='matriculas', null=True, blank=True)
    fecha_matricula = models.DateTimeField(auto_now_add=True)
    periodo = models.CharField(max_length=20, default='2025-1', help_text="Período académico (ej: 2025-1, 2025-2)")
    estado = models.CharField(max_length=20, choices=[
        ('activa', 'Activa'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
        ('suspendida', 'Suspendida'),
    ], default='activa')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Matrícula'
        verbose_name_plural = 'Matrículas'
        unique_together = ['estudiante', 'edicion_curso']
        ordering = ['-fecha_matricula']
    
    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.edicion_curso.curso.nombre} ({self.edicion_curso.nombre_edicion})"
    
    @property
    def curso(self):
        """Propiedad para compatibilidad con código existente"""
        if self.edicion_curso:
            return self.edicion_curso.curso
        return None


class Clase(models.Model):
    """
    Sesiones/clases de una edición de curso
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='clases', null=True, blank=True)
    edicion_curso = models.ForeignKey(EdicionCurso, on_delete=models.CASCADE, related_name='clases', null=True, blank=True)
    numero_clase = models.PositiveIntegerField()
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    fecha_clase = models.DateTimeField()
    duracion_minutos = models.PositiveIntegerField(default=90)
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True, blank=True, related_name='clases')
    aula = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Clase'
        verbose_name_plural = 'Clases'
        unique_together = ['edicion_curso', 'numero_clase']
        ordering = ['edicion_curso', 'numero_clase']
    
    def __str__(self):
        return f"{self.edicion_curso.curso.nombre} ({self.edicion_curso.nombre_edicion}) - Clase {self.numero_clase}: {self.titulo}"
    
    @property
    def curso(self):
        """Propiedad para compatibilidad con código existente"""
        if self.edicion_curso:
            return self.edicion_curso.curso
        return None


class Asistencia(models.Model):
    """
    Registro de asistencia de estudiantes a clases
    """
    ESTADO_CHOICES = [
        ('presente', 'Presente'),
        ('ausente', 'Ausente'),
        ('tarde', 'Tarde'),
        ('justificado', 'Justificado'),
    ]
    
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='asistencias', null=True, blank=True)
    clase = models.ForeignKey(Clase, on_delete=models.CASCADE, related_name='asistencias')
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='asistencias')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='ausente')
    observaciones = models.TextField(blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Asistencia'
        verbose_name_plural = 'Asistencias'
        unique_together = ['clase', 'estudiante']
        ordering = ['clase__fecha_clase', 'estudiante__user__first_name']
    
    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.clase.titulo} ({self.get_estado_display()})"


class Nota(models.Model):
    """
    Notas de estudiantes en cursos
    """
    TIPO_CHOICES = [
        ('parcial', 'Parcial'),
        ('final', 'Final'),
        ('tarea', 'Tarea'),
        ('participacion', 'Participación'),
        ('otro', 'Otro'),
    ]
    
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='notas', null=True, blank=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='notas')
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='notas')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    puntaje_obtenido = models.DecimalField(max_digits=5, decimal_places=2)
    puntaje_maximo = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    fecha_evaluacion = models.DateField()
    profesor = models.ForeignKey(Profesor, on_delete=models.SET_NULL, null=True, blank=True, related_name='notas_asignadas')
    observaciones = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        ordering = ['-fecha_evaluacion', 'estudiante__user__first_name']
    
    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.titulo} ({self.puntaje_obtenido}/{self.puntaje_maximo})"
    
    @property
    def porcentaje(self):
        if self.puntaje_maximo > 0:
            return (self.puntaje_obtenido / self.puntaje_maximo) * 100
        return 0
