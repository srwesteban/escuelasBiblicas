import re

from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


def default_anio_escuela():
    return timezone.now().year


def _collapse_ws_lower(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _texto_redundante_con_ciclo_escuela(texto: str, escuela: "Escuela") -> bool:
    """True si el texto solo repite el ciclo (p. ej. 'Curso B', 'Ciclo B', 'B')."""
    if not escuela or not texto:
        return False
    t = _collapse_ws_lower(texto)
    c = (escuela.ciclo or "").strip().lower()
    if not c:
        return False
    if t == c:
        return True
    if t in (f"ciclo {c}", f"curso {c}"):
        return True
    return False


def _dedupe_partes_visuales(partes: list[str]) -> list[str]:
    """Evita repetir el mismo fragmento (p. ej. 'Grupo 1' dos veces por datos sucios)."""
    seen: set[str] = set()
    out: list[str] = []
    for p in partes:
        k = _collapse_ws_lower(p)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _filtrar_texto_sin_redundancia_escuela(texto: str, escuela: "Escuela") -> str:
    """
    Quita fragmentos separados por «·» que solo repiten el ciclo de la escuela.
    Así corrige datos legados tipo «Curso B · Ciclo A» en Curso.nombre.
    """
    if not texto or not escuela:
        return (texto or "").strip()
    chunks = [p.strip() for p in texto.split("·") if p.strip()]
    if not chunks:
        return ""
    kept: list[str] = []
    for ch in chunks:
        if _texto_redundante_con_ciclo_escuela(ch, escuela):
            continue
        kept.append(ch)
    return " · ".join(kept)


class Estudiante(models.Model):
    """
    Perfil de estudiante en el módulo Hechos
    """
    class Genero(models.TextChoices):
        NO_ESPECIFICADO = "no_especificado", _("No especificado")
        FEMENINO = "femenino", _("Femenino")
        MASCULINO = "masculino", _("Masculino")
        OTRO = "otro", _("Otro")

    class EstadoCivil(models.TextChoices):
        NO_ESPECIFICADO = "no_especificado", _("No especificado")
        SOLTERO = "soltero", _("Soltero(a)")
        CASADO = "casado", _("Casado(a)")
        UNION_LIBRE = "union_libre", _("Unión libre")
        DIVORCIADO = "divorciado", _("Divorciado(a)")
        VIUDO = "viudo", _("Viudo(a)")
        SEPARADO = "separado", _("Separado(a)")
        OTRO = "otro", _("Otro")

    class TipoDocumento(models.TextChoices):
        CC = "CC", _("Cédula de ciudadanía")
        TI = "TI", _("Tarjeta de identidad")
        CE = "CE", _("Cédula de extranjería")
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
    genero = models.CharField(
        max_length=20,
        choices=Genero.choices,
        default=Genero.NO_ESPECIFICADO,
    )
    estado_civil = models.CharField(
        max_length=20,
        choices=EstadoCivil.choices,
        default=EstadoCivil.NO_ESPECIFICADO,
    )
    tipo_documento = models.CharField(max_length=3, choices=TipoDocumento.choices, default=TipoDocumento.CC)
    numero_documento = models.CharField(max_length=30, blank=True, default="")
    fecha_nacimiento = models.DateField(blank=True, null=True)
    direccion = models.TextField(blank=True)
    telefono_emergencia = models.CharField(max_length=20, blank=True)
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
        COMBINADO = 'combinado', _('Coordinador (varias funciones)')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_escuela_profile')
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='admins_escuela', null=True, blank=True)
    cargo = models.CharField(max_length=200)
    tipo_coordinador = models.CharField(
        max_length=20,
        choices=TipoCoordinador.choices,
        default=TipoCoordinador.ACADEMICO,
    )
    capacidades_explicitas = models.BooleanField(
        default=False,
        help_text='Si es verdadero, los permisos en Hechos vienen solo de las capacidades asignadas (no del respaldo por tipo).',
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

    @classmethod
    def cargo_para_capacidades(cls, codigos_ordenados: list[str], sede_nombre: str) -> str:
        """Texto de cargo a partir de capacidades en orden (p. ej. académico y pedagógico)."""
        frag = {
            'academico': 'académico',
            'pedagogico': 'pedagógico',
            'financiero': 'financiero',
            'logistico': 'logístico',
        }
        parts = [frag[c] for c in codigos_ordenados if c in frag]
        if not parts:
            return f'Coordinador — {sede_nombre}'
        if len(parts) == 1:
            return f'Coordinador {parts[0]} — {sede_nombre}'
        if len(parts) == 2:
            return f'Coordinador {parts[0]} y {parts[1]} — {sede_nombre}'
        body = ', '.join(parts[:-1]) + f' y {parts[-1]}'
        return f'Coordinador {body} — {sede_nombre}'

    @classmethod
    def tipo_coordinador_desde_capacidades(cls, codigos: list[str]) -> str:
        """Un solo tipo enum a partir de la lista de códigos de capacidad."""
        mapa = {
            'academico': cls.TipoCoordinador.ACADEMICO,
            'pedagogico': cls.TipoCoordinador.PEDAGOGICO,
            'financiero': cls.TipoCoordinador.FINANCIERO,
            'logistico': cls.TipoCoordinador.LOGISTICO,
        }
        tipos_unicos: list[str] = []
        vistos: set[str] = set()
        for c in codigos:
            if c not in mapa:
                continue
            t = mapa[c]
            if t not in vistos:
                vistos.add(t)
                tipos_unicos.append(t)
        if len(tipos_unicos) == 0:
            return cls.TipoCoordinador.ACADEMICO
        if len(tipos_unicos) == 1:
            return tipos_unicos[0]
        return cls.TipoCoordinador.COMBINADO

    def sync_capacidades(self, codigos_ordenados: list[str]) -> None:
        """Reemplaza las capacidades asignadas por el orden indicado (solo códigos válidos)."""
        AdminEscuelaCapacidad.objects.filter(admin_escuela=self).delete()
        if codigos_ordenados:
            caps = {
                c.codigo: c
                for c in CapacidadCoordinador.objects.filter(codigo__in=codigos_ordenados)
            }
            for orden, codigo in enumerate(codigos_ordenados):
                cap = caps.get(codigo)
                if cap:
                    AdminEscuelaCapacidad.objects.create(
                        admin_escuela=self,
                        capacidad=cap,
                        orden=orden,
                    )
        self.capacidades_explicitas = True
        self.save(update_fields=['capacidades_explicitas'])

    def roles_codigos(self) -> list[str]:
        """Códigos de capacidad en orden; respaldo por tipo si no hay filas."""
        asigs = list(self.capacidad_asignaciones.all())
        if asigs:
            asigs.sort(key=lambda a: (a.orden, a.id))
            return [a.capacidad.codigo for a in asigs]
        if getattr(self, 'capacidades_explicitas', False):
            return []
        return list(capacidades_default_por_tipo(self.tipo_coordinador))

    def roles_display(self) -> str:
        """
        Etiquetas de rol legibles (p. ej. «Académico · Financiero»).
        Evita el genérico «varias funciones» cuando hay capacidades concretas.
        """
        labels = {
            'academico': 'Académico',
            'pedagogico': 'Pedagógico',
            'financiero': 'Financiero',
            'logistico': 'Logístico',
        }
        codes = self.roles_codigos()
        parts = [labels[c] for c in codes if c in labels]
        if parts:
            return ' · '.join(parts)
        if self.tipo_coordinador == self.TipoCoordinador.SEDE:
            return str(self.get_tipo_coordinador_display())
        if self.tipo_coordinador == self.TipoCoordinador.COMBINADO:
            # Sin capacidades cargadas: intenta sacar los roles del cargo guardado.
            cargo = (self.cargo or '').split('—')[0].strip()
            if cargo and 'varias funciones' not in cargo.casefold():
                return cargo.replace('Coordinador ', '').strip() or cargo
        return str(self.get_tipo_coordinador_display())


class CapacidadCoordinador(models.Model):
    """
    Catálogo de tareas que puede tener un coordinador (módulo Hechos).
    El código se usa en código Python para comprobar acceso.
    """
    codigo = models.SlugField(max_length=64, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Capacidad de coordinador'
        verbose_name_plural = 'Capacidades de coordinador'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class AdminEscuelaCapacidad(models.Model):
    """Capacidades asignadas a un AdminEscuela, con orden personalizado."""

    admin_escuela = models.ForeignKey(
        AdminEscuela,
        on_delete=models.CASCADE,
        related_name='capacidad_asignaciones',
    )
    capacidad = models.ForeignKey(
        CapacidadCoordinador,
        on_delete=models.CASCADE,
        related_name='asignaciones',
    )
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['orden', 'capacidad__orden', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['admin_escuela', 'capacidad'],
                name='hechos_adminescuela_capacidad_unique',
            ),
        ]

    def __str__(self):
        return f'{self.admin_escuela_id} → {self.capacidad.codigo}'


def capacidades_default_por_tipo(tipo: str) -> list[str]:
    """Valores iniciales según tipo de coordinador (etiqueta)."""
    m = {
        AdminEscuela.TipoCoordinador.ACADEMICO: ['academico'],
        AdminEscuela.TipoCoordinador.PEDAGOGICO: ['pedagogico'],
        AdminEscuela.TipoCoordinador.FINANCIERO: ['financiero'],
        AdminEscuela.TipoCoordinador.LOGISTICO: ['logistico'],
        AdminEscuela.TipoCoordinador.SEDE: [],
        AdminEscuela.TipoCoordinador.COMBINADO: [],
    }
    return list(m.get(tipo, []))


class EscuelaQuerySet(models.QuerySet):
    def vigentes(self):
        """Excluye escuelas cuya fecha de fin de clases ya pasó."""
        hoy = timezone.localdate()
        return self.filter(models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy))


class Escuela(models.Model):
    """
    Unidad académica principal visible para el estudiante.
    Oferta operativa (fechas, cupo, horario, modalidad) vive en este registro.
    """

    class Ciclo(models.TextChoices):
        A = 'A', _('Ciclo A')
        B = 'B', _('Ciclo B')

    class Modalidad(models.TextChoices):
        PRESENCIAL = 'presencial', _('Presencial')
        VIRTUAL = 'virtual', _('Virtual')
        HIBRIDA = 'hibrida', _('Híbrida')

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
    maestro = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escuelas_dirigidas',
        verbose_name=_('Maestro asignado'),
        help_text=_('Profesor responsable; puede quedar por asignar hasta definirlo.'),
    )
    fecha_inicio = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Inicio de clases'),
    )
    fecha_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name=_('Fin de clases'),
    )
    modalidad = models.CharField(
        max_length=16,
        choices=Modalidad.choices,
        default=Modalidad.PRESENCIAL,
        help_text=_('Modalidad de la escuela: presencial, virtual o híbrida.'),
    )
    horario = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text=_('Ej: Lunes y Miércoles 7:00 PM'),
    )
    aula = models.CharField(max_length=50, blank=True, default='')
    cupo_maximo = models.PositiveIntegerField(
        default=30,
        help_text=_('Cupo máximo de estudiantes. 0 = indefinido (sin límite).'),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EscuelaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Escuela'
        verbose_name_plural = 'Escuelas'
        ordering = ['-anio', 'ciclo', 'nombre']

    def __str__(self):
        return self.nombre

    @property
    def ha_finalizado(self) -> bool:
        return bool(self.fecha_fin and self.fecha_fin < timezone.localdate())

    def titulo_tarjeta(self) -> str:
        return f'{self.nombre} — {self.anio} · Ciclo {self.ciclo}'

    def linea_identificacion_pedagogica(self) -> str:
        parts: list[str] = [self.get_ciclo_display(), (self.nombre or '').strip()]
        parts = _dedupe_partes_visuales([p for p in parts if p])
        return ' · '.join(parts) if parts else '—'

    @property
    def tiene_cupo_definido(self) -> bool:
        """False cuando el cupo es 0 / vacío: se trata como indefinido (sin tope)."""
        return bool(self.cupo_maximo and int(self.cupo_maximo) > 0)

    @property
    def estudiantes_inscritos(self) -> int:
        return self.matriculas.filter(is_active=True).count()

    @property
    def cupos_disponibles(self) -> int:
        if not self.tiene_cupo_definido:
            # Sin tope: siempre hay cupo para validaciones de matrícula.
            return 10**9
        return max(0, int(self.cupo_maximo) - self.estudiantes_inscritos)

    @property
    def porcentaje_ocupacion(self) -> float:
        if not self.tiene_cupo_definido:
            return 0.0
        return (self.estudiantes_inscritos / self.cupo_maximo) * 100.0

    def esta_llena(self) -> bool:
        """True solo si hay cupo definido y ya se alcanzó o superó."""
        if not self.tiene_cupo_definido:
            return False
        return self.estudiantes_inscritos >= int(self.cupo_maximo)

    @property
    def profesor(self):
        """Alias de ``maestro`` para plantillas/código que hablaban de «profesor de la edición»."""
        return self.maestro


class EscuelaHorario(models.Model):
    """Días y hora de clase de una escuela (sustituye horarios por edición)."""

    class DiaSemana(models.IntegerChoices):
        LUNES = 0, _("Lunes")
        MARTES = 1, _("Martes")
        MIERCOLES = 2, _("Miércoles")
        JUEVES = 3, _("Jueves")
        VIERNES = 4, _("Viernes")
        SABADO = 5, _("Sábado")
        DOMINGO = 6, _("Domingo")

    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="estructura_horarios",
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices)
    hora = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Horario de escuela")
        verbose_name_plural = _("Horarios de escuela")
        ordering = ["escuela", "dia_semana", "hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["escuela", "dia_semana"],
                name="uniq_escuela_dia_semana",
            )
        ]

    def __str__(self):
        return f"{self.escuela} · {self.get_dia_semana_display()} {self.hora}"


class NivelProgramaPlantilla(models.Model):
    """
    Catálogo global de niveles del programa de formación.
    Todas las sedes reciben copias (NivelPrograma) generadas desde aquí.
    """

    jerarquia = models.PositiveIntegerField(
        verbose_name=_("Nivel"),
        help_text=_(
            "0 = Fundamentos; 1, 2, 3… ordenan el programa. Único en todo el sistema."
        ),
    )
    nombre = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Nombre"),
        help_text=_("Texto descriptivo mostrado como «Nivel N: nombre»."),
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name=_("Descripción del nivel"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Nivel del programa (plantilla global)")
        verbose_name_plural = _("Niveles del programa (plantillas globales)")
        ordering = ["jerarquia", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["jerarquia"],
                name="uniq_hechos_nivel_programa_plantilla_jerarquia",
            ),
        ]

    def __str__(self) -> str:
        return self.titulo_acordeon()

    def titulo_acordeon(self) -> str:
        j = self.jerarquia
        n = j + 1
        base = (self.nombre or "").strip()
        if j == 0:
            label = base or "Fundamentos"
            return f"Nivel {n}: {label}"
        if base:
            return f"Nivel {n}: {base}"
        return f"Nivel {n}"


class EscuelaProgramaPlantilla(models.Model):
    """
    Catálogo global de escuelas del programa (por nivel).
    Cada sede recibe filas EscuelaPrograma alineadas a estas plantillas.
    """

    nivel_plantilla = models.ForeignKey(
        NivelProgramaPlantilla,
        on_delete=models.CASCADE,
        related_name="escuelas",
        verbose_name=_("Nivel"),
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(
        blank=True,
        verbose_name=_("Descripción"),
    )
    tiene_matricula = models.BooleanField(
        default=False,
        verbose_name=_("Tiene matrícula"),
    )
    costo_matricula_cop = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Costo de matrícula (COP)"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Escuela del programa (plantilla global)")
        verbose_name_plural = _("Escuelas del programa (plantillas globales)")
        ordering = ["nivel_plantilla__jerarquia", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["nivel_plantilla", "nombre"],
                name="uniq_hechos_escuela_programa_plantilla_nivel_nombre",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nivel_plantilla} — {self.nombre}"


class NivelPrograma(models.Model):
    """
    Nivel del programa de formación por sede (número de nivel + nombre descriptivo).
    El título mostrado es siempre «Nivel N: …» (p. ej. Nivel 0: Fundamentos).
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="niveles_programa",
    )
    plantilla = models.ForeignKey(
        NivelProgramaPlantilla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="niveles_en_sedes",
        verbose_name=_("Plantilla global"),
        help_text=_("Si existe, esta fila proviene del catálogo compartido por todas las sedes."),
    )
    jerarquia = models.PositiveIntegerField(
        verbose_name=_("Nivel"),
        help_text=_(
            "Número entero: 0 = Fundamentos, 1, 2, 3… ordenan el programa. Debe ser único por sede."
        ),
    )
    nombre = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Nombre"),
        help_text=_(
            "Texto descriptivo (ej. Sanos y Libres). Se muestra junto al número como «Nivel N: nombre»."
        ),
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name=_("Descripción del nivel"),
        help_text=_(
            "Texto opcional que se muestra en el acordeón de escuelas (enfoque, propósito del nivel)."
        ),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Nivel (programa)")
        verbose_name_plural = _("Niveles (programa)")
        ordering = ["jerarquia", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "jerarquia"],
                name="uniq_hechos_nivel_programa_sede_jerarquia",
            ),
            models.UniqueConstraint(
                fields=["sede", "plantilla"],
                condition=Q(plantilla__isnull=False),
                name="uniq_hechos_nivel_programa_sede_plantilla",
            ),
        ]

    def __str__(self) -> str:
        return self.titulo_acordeon()

    def titulo_acordeon(self) -> str:
        j = self.jerarquia
        n = j + 1
        base = (self.nombre or "").strip()
        if j == 0:
            label = base or "Fundamentos"
            return f"Nivel {n}: {label}"
        if base:
            return f"Nivel {n}: {base}"
        return f"Nivel {n}"


class EscuelaPrograma(models.Model):
    """
    Definición de escuela en el programa de formación (nivel, nombre, descripción).
    Distinto de Escuela: esa es la instancia operativa por año y ciclo en la sede.
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="escuelas_programa",
    )
    nivel_programa = models.ForeignKey(
        NivelPrograma,
        on_delete=models.PROTECT,
        related_name="escuelas",
        verbose_name=_("Nivel"),
    )
    plantilla = models.ForeignKey(
        EscuelaProgramaPlantilla,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escuelas_en_sedes",
        verbose_name=_("Plantilla global"),
        help_text=_("Si existe, esta fila proviene del catálogo compartido por todas las sedes."),
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(
        blank=True,
        verbose_name=_("Descripción"),
        help_text=_("Texto libre sobre esta escuela en el programa."),
    )
    tiene_matricula = models.BooleanField(
        default=False,
        verbose_name=_("Tiene matrícula"),
        help_text=_("Si aplica cobro de matrícula para esta escuela."),
    )
    costo_matricula_cop = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Costo de matrícula (COP)"),
        help_text=_("Pesos colombianos enteros. Obligatorio cuando «Tiene matrícula» está activo."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Escuela (programa)"
        verbose_name_plural = "Escuelas (programa)"
        ordering = ["nivel_programa__jerarquia", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["sede", "nivel_programa", "nombre"],
                name="uniq_hechos_escuela_programa_sede_nivel_prog_nombre",
            ),
            models.UniqueConstraint(
                fields=["sede", "plantilla"],
                condition=Q(plantilla__isnull=False),
                name="uniq_hechos_escuela_programa_sede_plantilla",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nivel_programa.titulo_acordeon()} — {self.nombre}"

    @property
    def nombre_para_catalogo(self) -> str:
        """Nombre canónico en catálogo global (plantilla); vacío si la fila no tiene plantilla."""
        p = self.plantilla
        if p is not None:
            return (p.nombre or "").strip()
        return ""


class Salon(models.Model):
    """
    Espacio físico de la sede (aula, salón, auditorio) con cupo de plazas.
    """

    sede = models.ForeignKey(
        'core.Sede',
        on_delete=models.CASCADE,
        related_name='salones',
    )
    nombre = models.CharField(max_length=200, verbose_name=_('Nombre'))
    codigo = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_('Código'),
        help_text=_('Opcional (ej. A-101).'),
    )
    capacidad_plazas = models.PositiveIntegerField(
        verbose_name=_('Capacidad (plazas)'),
        help_text=_('Número máximo de personas o asientos.'),
    )
    escuela = models.ForeignKey(
        'Escuela',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salones_asignados',
        verbose_name=_('Escuela asignada'),
        help_text=_('Como máximo un salón por escuela; escuela de la misma sede (opcional).'),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Salón')
        verbose_name_plural = _('Salones')
        ordering = ['sede', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['sede', 'nombre'],
                name='uniq_hechos_salon_nombre_por_sede',
            ),
            models.UniqueConstraint(
                fields=['escuela'],
                condition=models.Q(escuela__isnull=False),
                name='uniq_hechos_un_salon_por_escuela',
            ),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.capacidad_plazas} plazas)'


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
        esc = getattr(self.ruta_estudio, 'escuela_id', None)
        if not esc:
            return 0
        return Matricula.objects.filter(escuela_id=esc, is_active=True).count()


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
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name='solicitudes_matricula')
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
        unique_together = ['estudiante', 'escuela']

    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} -> {self.escuela}"


class NotificacionEstudiante(models.Model):
    class Tipo(models.TextChoices):
        APROBACION = 'aprobacion', _('Aprobación')
        RECHAZO = 'rechazo', _('Rechazo')
        INFO = 'info', _('Información')
        CERTIFICADO = 'certificado', _('Certificado')

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
        verbose_name = _('Solicitud')
        verbose_name_plural = _('Solicitudes')
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.asunto}"


class QuejaReclamo(models.Model):
    class Tipo(models.TextChoices):
        QUEJA = "queja", _("Queja")
        RECLAMO = "reclamo", _("Reclamo")
        SUGERENCIA = "sugerencia", _("Sugerencia")
        SOLICITUD = "solicitud", _("Solicitud")
        FELICITACION = "felicitacion", _("Felicitación")

    class Estado(models.TextChoices):
        RECIBIDA = "recibida", _("Recibida")
        EN_PROCESO = "en_proceso", _("En proceso")
        CERRADA = "cerrada", _("Cerrada")

    sede = models.ForeignKey("core.Sede", on_delete=models.CASCADE, related_name="quejas_reclamos")
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name="quejas_reclamos")
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.QUEJA)
    asunto = models.CharField(max_length=180)
    mensaje = models.TextField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.RECIBIDA)
    asignado_a = models.ForeignKey(
        AdminEscuela,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quejas_reclamos_asignadas",
        help_text=_("Coordinador académico asignado en el momento de envío."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Queja/Reclamo"
        verbose_name_plural = "Quejas y reclamos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.asunto}"


class Matricula(models.Model):
    """
    Matrícula de estudiantes por escuela operativa.
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='matriculas', null=True, blank=True)
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='matriculas')
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name='matriculas')
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
        unique_together = ['estudiante', 'escuela']
        ordering = ['-fecha_matricula']
    
    def __str__(self):
        return f"{self.estudiante.user.get_full_name()} - {self.escuela.nombre}"
    
    @property
    def curso(self):
        """Primer curso activo de la ruta de esta escuela (compatibilidad)."""
        if not self.escuela_id:
            return None
        return (
            Curso.objects.filter(ruta_estudio__escuela_id=self.escuela_id, is_active=True)
            .order_by('orden', 'id')
            .first()
        )


class Clase(models.Model):
    """
    Sesiones/clases de una escuela
    """
    sede = models.ForeignKey('core.Sede', on_delete=models.CASCADE, related_name='clases', null=True, blank=True)
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name='clases')
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
        unique_together = ['escuela', 'numero_clase']
        ordering = ['escuela', 'numero_clase']
    
    def __str__(self):
        return f"{self.escuela.nombre} - Clase {self.numero_clase}: {self.titulo}"
    
    @property
    def curso(self):
        if not self.escuela_id:
            return None
        return (
            Curso.objects.filter(ruta_estudio__escuela_id=self.escuela_id, is_active=True)
            .order_by('orden', 'id')
            .first()
        )


class ActividadEscuela(models.Model):
    """
    Actividad publicada por el docente para una escuela (patrón tipo tarea/assignment de LMS).
    """

    class Tipo(models.TextChoices):
        TAREA = "tarea", _("Tarea o trabajo escrito")
        ENTREGA_ARCHIVO = "entrega_archivo", _("Entrega de archivo")
        CUESTIONARIO = "cuestionario", _("Cuestionario breve")
        FORO = "foro", _("Foro o discusión")
        LECTURA = "lectura", _("Lectura / material de estudio")
        OTRO = "otro", _("Otro")

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="actividades_escuela",
    )
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="actividades",
    )
    creada_por = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_publicadas",
    )
    tipo = models.CharField(
        max_length=32,
        choices=Tipo.choices,
        default=Tipo.TAREA,
    )
    titulo = models.CharField(max_length=220)
    instrucciones = models.TextField(blank=True)
    fecha_limite = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Fecha límite"),
        help_text=_("Opcional. Hasta cuándo deben entregar o completar el trabajo."),
    )
    puntos_posibles = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Puntos posibles"),
        help_text=_("Opcional, si calificas esta actividad."),
    )
    material_adjunto = models.FileField(
        upload_to="actividades_escuela/%Y/%m/",
        blank=True,
        null=True,
        verbose_name=_("Material de apoyo"),
        help_text=_("PDF u otro archivo para los estudiantes (opcional)."),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Actividad de escuela")
        verbose_name_plural = _("Actividades de escuela")

    def __str__(self):
        return f"{self.titulo} ({self.escuela.nombre})"


class EntregaActividad(models.Model):
    """
    Evidencia del estudiante para una actividad (texto y/o archivo), evaluable por el docente.
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="entregas_actividad",
    )
    actividad = models.ForeignKey(
        ActividadEscuela,
        on_delete=models.CASCADE,
        related_name="entregas",
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name="entregas_actividades",
    )
    texto = models.TextField(
        blank=True,
        verbose_name=_("Respuesta o comentario"),
        help_text=_("Escribe aquí tu trabajo o explicación."),
    )
    archivo = models.FileField(
        upload_to="actividades/%Y/%m/",
        blank=True,
        null=True,
        verbose_name=_("Archivo de evidencia"),
        help_text=_("PDF, Word u otro formato permitido (opcional si ya escribiste respuesta)."),
        validators=[
            FileExtensionValidator(
                allowed_extensions=("pdf", "doc", "docx", "odt", "txt", "rtf", "png", "jpg", "jpeg", "webp"),
            )
        ],
    )
    enviado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    puntaje_asignado = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Puntaje"),
    )
    comentario_docente = models.TextField(blank=True, verbose_name=_("Retroalimentación del docente"))
    evaluado_en = models.DateTimeField(null=True, blank=True)
    evaluado_por = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entregas_evaluadas",
    )

    class Meta:
        verbose_name = _("Entrega de actividad")
        verbose_name_plural = _("Entregas de actividades")
        constraints = [
            models.UniqueConstraint(
                fields=("actividad", "estudiante"),
                name="uniq_entrega_actividad_por_estudiante",
            )
        ]
        ordering = ["-actualizado_en"]

    def __str__(self):
        return f"{self.estudiante} → {self.actividad.titulo}"


class ArchivoRecursoEscuela(models.Model):
    """
    Material de apoyo que el docente de la escuela comparte con estudiantes matriculados en esa escuela.
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="archivos_recurso_escuela",
    )
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="archivos_recurso",
    )
    titulo = models.CharField(max_length=220, verbose_name=_("Título"))
    descripcion = models.TextField(
        blank=True,
        verbose_name=_("Descripción"),
        help_text=_("Opcional. Indica para qué sirve el archivo."),
    )
    archivo = models.FileField(
        upload_to="recursos_escuela/%Y/%m/",
        verbose_name=_("Archivo"),
        validators=[
            FileExtensionValidator(
                allowed_extensions=(
                    "pdf",
                    "doc",
                    "docx",
                    "odt",
                    "txt",
                    "rtf",
                    "ppt",
                    "pptx",
                    "xls",
                    "xlsx",
                    "png",
                    "jpg",
                    "jpeg",
                    "webp",
                    "zip",
                ),
            )
        ],
    )
    subido_por = models.ForeignKey(
        Profesor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archivos_recurso_publicados",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Archivo recurso de escuela")
        verbose_name_plural = _("Archivos recurso por escuela")

    def __str__(self):
        return f"{self.titulo} ({self.escuela_id})"


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
    Notas de estudiantes por escuela operativa
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
    escuela = models.ForeignKey(Escuela, on_delete=models.CASCADE, related_name='notas_legacy')
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

    @property
    def curso(self):
        """Compat: primer curso de la ruta de la escuela."""
        if not self.escuela_id:
            return None
        return (
            Curso.objects.filter(ruta_estudio__escuela_id=self.escuela_id, is_active=True)
            .order_by('orden', 'id')
            .first()
        )


class EscuelaGrillaAsistenciaConfig(models.Model):
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="grilla_asistencia_configs",
    )
    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="grilla_asistencia_configs",
    )
    num_columnas = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Configuración grilla de asistencia")
        verbose_name_plural = _("Configuraciones grilla de asistencia")
        constraints = [
            models.UniqueConstraint(
                fields=("escuela", "sede"),
                name="uniq_grilla_asistencia_config_escuela_sede",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.escuela_id} · {self.sede_id}"


class AsistenciaGrillaCelda(models.Model):
    class Valor(models.TextChoices):
        ASISTIO = "A", _("Asistió (A)")
        ESTADO_P = "P", _("P")
        INASISTENCIA = "N", _("Inasistencia (N)")

    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="grilla_asistencia_celdas",
    )
    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="grilla_asistencia_celdas",
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name="grilla_asistencia_celdas",
    )
    columna = models.PositiveIntegerField(
        verbose_name=_("Columna"),
        help_text=_("1 = primer registro, 2 = segundo, etc."),
    )
    valor = models.CharField(max_length=1, choices=Valor.choices)
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grilla_asistencia_registros",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Celda grilla asistencia")
        verbose_name_plural = _("Celdas grilla asistencia")
        ordering = ["columna", "estudiante__user__last_name"]
        unique_together = [("escuela", "estudiante", "columna")]

    def __str__(self) -> str:
        return f"{self.estudiante_id} col {self.columna}"


class EscuelaGrillaNotasConfig(models.Model):
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="grilla_notas_configs",
    )
    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="grilla_notas_configs",
    )
    num_columnas = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Configuración grilla de notas")
        verbose_name_plural = _("Configuraciones grilla de notas")
        constraints = [
            models.UniqueConstraint(
                fields=("escuela", "sede"),
                name="uniq_grilla_notas_config_escuela_sede",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.escuela_id} · {self.sede_id}"


class NotasGrillaCelda(models.Model):
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="grilla_notas_celdas",
    )
    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="grilla_notas_celdas",
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name="grilla_notas_celdas",
    )
    columna = models.PositiveIntegerField(
        verbose_name=_("Columna"),
        help_text=_("1 = Nota 1, 2 = Nota 2, …"),
    )
    valor = models.CharField(max_length=64, blank=True)
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="grilla_notas_registros",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Celda grilla notas")
        verbose_name_plural = _("Celdas grilla notas")
        ordering = ["columna", "estudiante__user__last_name"]
        unique_together = [("escuela", "estudiante", "columna")]

    def __str__(self) -> str:
        return f"{self.estudiante_id} col {self.columna}"


class NotasGrillaEstadoFinal(models.Model):
    class Estado(models.TextChoices):
        VACIO = "", _("—")
        APROBADO = "aprobado", _("Aprobado")
        NO_APROBADO = "no_aprobado", _("No aprobado")

    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="grilla_notas_estados_finales",
    )
    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="grilla_notas_estados_finales",
    )
    estudiante = models.ForeignKey(
        Estudiante,
        on_delete=models.CASCADE,
        related_name="grilla_notas_estados_finales",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        blank=True,
        default=Estado.VACIO,
    )
    certificado_activo = models.BooleanField(default=False)
    certificado_emitido_en = models.DateTimeField(null=True, blank=True)
    certificado_emitido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Estado final grilla notas")
        verbose_name_plural = _("Estados finales grilla notas")
        unique_together = [("escuela", "estudiante")]

    def __str__(self) -> str:
        return f"{self.estudiante_id} · {self.estado or '—'}"


class Ofrenda(models.Model):
    """
    Registro de ofrendas realizadas en el contexto de una escuela (maestro/profesor).
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="ofrendas_hechos",
    )
    escuela = models.ForeignKey(
        Escuela,
        on_delete=models.CASCADE,
        related_name="ofrendas",
        help_text=_("Escuela a la que corresponde la ofrenda."),
    )
    fecha = models.DateField(default=timezone.now)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    descripcion = models.CharField(max_length=220, blank=True, default="")
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ofrendas_registradas",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ofrenda"
        verbose_name_plural = "Ofrendas"
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["sede", "escuela", "fecha"], name="hechos_ofre_sede_id_0dc687_idx"),
        ]

    def __str__(self):
        return f"{self.escuela.nombre} · {self.fecha} · {self.valor}"


class PresupuestoEvento(models.Model):
    """
    Plan de la sede: evento o partida y cuánto dinero se destina (presupuesto / asignación).
    Distinto de las ofrendas que registran los maestros día a día.
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="presupuestos_evento",
    )
    nombre = models.CharField(
        max_length=200,
        help_text=_("Nombre del evento o del gasto previsto (ej. retiro, materiales, refrigerio)."),
    )
    fecha_evento = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Fecha del evento"),
        help_text=_("Opcional. Fecha prevista en que ocurre o se liquida el gasto."),
    )
    monto_destinado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Monto a destinar"),
        help_text=_("Cuánto dinero de la sede planeas usar para este evento o partida."),
    )
    notas = models.TextField(blank=True, default="", verbose_name=_("Notas"))
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="presupuestos_evento_creados",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Presupuesto de evento")
        verbose_name_plural = _("Presupuestos de eventos")
        ordering = ["-fecha_evento", "-created_at", "-id"]

    def __str__(self):
        return f"{self.nombre} · {self.monto_destinado}"


class RecaudoOcasional(models.Model):
    """
    Ingreso puntual que registra el coordinador financiero: donación extra, sobrante de evento,
    venta ocasional, etc. No sustituye las ofrendas que anotan los maestros por escuela.
    """

    sede = models.ForeignKey(
        "core.Sede",
        on_delete=models.CASCADE,
        related_name="recaudos_ocasionales",
    )
    fecha = models.DateField(default=timezone.now, verbose_name=_("Fecha"))
    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name=_("Monto"),
        help_text=_("Valor del ingreso recaudado."),
    )
    concepto = models.CharField(
        max_length=200,
        verbose_name=_("Concepto"),
        help_text=_("En pocas palabras: qué es este dinero (ej. sobrante retiro, donación puntual)."),
    )
    detalle = models.TextField(blank=True, default="", verbose_name=_("Detalle"))
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recaudos_ocasionales_registrados",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Recaudo ocasional")
        verbose_name_plural = _("Recaudos ocasionales")
        ordering = ["-fecha", "-created_at", "-id"]
        indexes = [
            models.Index(fields=["sede", "fecha"], name="hechos_recaud_sede_fecha_idx"),
        ]

    def __str__(self):
        return f"{self.concepto} · {self.fecha} · {self.monto}"
