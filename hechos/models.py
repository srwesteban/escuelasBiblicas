from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Estudiante(models.Model):
    """
    Perfil de estudiante en el módulo Hechos
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='estudiante_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='estudiantes', null=True, blank=True)
    codigo_estudiante = models.CharField(max_length=20, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    direccion = models.TextField(blank=True)
    iglesia = models.CharField(max_length=200, blank=True)
    telefono_emergencia = models.CharField(max_length=20, blank=True)
    contacto_emergencia = models.CharField(max_length=100, blank=True)
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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_escuela_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='admins_escuela', null=True, blank=True)
    cargo = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Admin de Escuela'
        verbose_name_plural = 'Admins de Escuela'
        ordering = ['user__first_name', 'user__last_name']
    
    def __str__(self):
        return f"{self.user.get_full_name()} (Admin - {self.sede.nombre})"


class RutaEstudio(models.Model):
    """
    Rutas de estudio disponibles en la escuela bíblica
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='rutas_estudio', null=True, blank=True)
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
        verbose_name = 'Ruta de Estudio'
        verbose_name_plural = 'Rutas de Estudio'
        ordering = ['nivel', 'nombre']
    
    def __str__(self):
        return f"{self.nombre} ({self.get_nivel_display()})"


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
