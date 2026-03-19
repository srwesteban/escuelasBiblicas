from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, AppModule, UserAppPermission


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_verified', 'is_active', 'created_at')
    list_filter = ('role', 'is_verified', 'is_active', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'username')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        ('Permisos', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
        ('Grupos', {'fields': ('groups', 'user_permissions')}),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'date_joined', 'last_login')
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(AppModule)
class AppModuleAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'is_active', 'order', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'display_name', 'description')
    ordering = ('order', 'display_name')
    
    fieldsets = (
        (None, {'fields': ('name', 'display_name', 'description')}),
        ('Configuración', {'fields': ('url_name', 'icon', 'is_active', 'order')}),
    )


@admin.register(UserAppPermission)
class UserAppPermissionAdmin(admin.ModelAdmin):
    list_display = ('user', 'app_module', 'can_view', 'can_edit', 'can_delete', 'can_manage', 'created_at')
    list_filter = ('can_view', 'can_edit', 'can_delete', 'can_manage', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'app_module__display_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('user', 'app_module')}),
        ('Permisos', {'fields': ('can_view', 'can_edit', 'can_delete', 'can_manage')}),
    )
