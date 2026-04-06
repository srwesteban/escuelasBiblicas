from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def generate_unique_username(model_class, email, exclude_pk=None):
    base_username = slugify((email or "").split("@")[0]) or "usuario"
    candidate = base_username
    counter = 1
    queryset = model_class.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    while queryset.filter(username=candidate).exists():
        counter += 1
        candidate = f"{base_username}{counter}"
    return candidate


class User(AbstractUser):
    """
    Modelo de usuario extendido para HechosHub
    """
    ROLES = [
        ('super_admin', 'Super Admin'),
        ('app_admin', 'Admin de Aplicación'),
        ('user', 'Usuario'),
    ]
    
    email = models.EmailField(_('email address'), unique=True)
    role = models.CharField(
        max_length=20,
        choices=ROLES,
        default='user',
        help_text='Rol global del usuario en el sistema'
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.TextField(blank=True, default="", verbose_name=_("Dirección"))
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    sede = models.ForeignKey('Sede', on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = generate_unique_username(self.__class__, self.email, exclude_pk=self.pk)
        super().save(*args, **kwargs)
    
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    def is_app_admin(self):
        return self.role == 'app_admin'
    
    def can_manage_app(self, app_name):
        """Verifica si el usuario puede gestionar una aplicación específica"""
        if self.is_super_admin():
            return True
        if self.is_app_admin():
            # Aquí se puede implementar lógica específica por aplicación
            return True
        return False


class AppModule(models.Model):
    """
    Modelo para registrar módulos/aplicaciones disponibles en el sistema
    """
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    url_name = models.CharField(max_length=100, help_text='Nombre de la URL del módulo')
    icon = models.CharField(max_length=50, default='fas fa-cube')
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Módulo de Aplicación'
        verbose_name_plural = 'Módulos de Aplicación'
        ordering = ['order', 'display_name']
    
    def __str__(self):
        return self.display_name


class Sede(models.Model):
    """
    Modelo para manejar las diferentes sedes de la iglesia
    """
    nombre = models.CharField(max_length=200)
    imagen_referencia = models.ImageField(upload_to='sedes/', blank=True, null=True)
    direccion = models.TextField(blank=True, default="")
    departamento = models.CharField(
        max_length=10,
        blank=True,
        default="",
        help_text="ID del departamento (Colombia), desde el formulario de sede.",
    )
    ciudad = models.CharField(max_length=120, blank=True, default="")
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    pastor_responsable = models.CharField(max_length=200, blank=True)
    foto_pastor = models.ImageField(upload_to='pastores/', blank=True, null=True)
    descripcion = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Sede'
        verbose_name_plural = 'Sedes'
        ordering = ['departamento', 'ciudad', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'departamento', 'ciudad'],
                name='core_sede_unique_nombre_ubicacion',
            ),
        ]
    
    def __str__(self):
        return self.nombre

    def ubicacion_completa(self) -> str:
        """Ciudad y departamento (Colombia) para mostrar en UI."""
        from core.colombia_geo import nombre_departamento

        ciu = (self.ciudad or "").strip()
        dep = (self.departamento or "").strip()
        if dep and ciu:
            return f"{ciu}, {nombre_departamento(dep)}"
        if ciu:
            return ciu
        return ""

    def titulo_con_ciudad(self) -> str:
        """Ej. «Hechos Norte: Pasto» para distinguir sedes con el mismo nombre."""
        ciu = (self.ciudad or "").strip()
        if ciu:
            return f"{self.nombre}: {ciu}"
        return self.nombre


class PastorSede(models.Model):
    """
    Pastores adicionales asociados a una sede.
    """
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='pastores_adicionales')
    nombre = models.CharField(max_length=200)
    foto = models.ImageField(upload_to='pastores/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Pastor de sede'
        verbose_name_plural = 'Pastores de sede'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} - {self.sede.nombre}"


class UserAppPermission(models.Model):
    """
    Permisos específicos de usuario por aplicación
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='app_permissions')
    app_module = models.ForeignKey(AppModule, on_delete=models.CASCADE)
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_manage = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Permiso de Usuario por App'
        verbose_name_plural = 'Permisos de Usuario por App'
        unique_together = ['user', 'app_module']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.app_module.display_name}"
