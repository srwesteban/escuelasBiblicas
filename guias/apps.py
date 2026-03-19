from django.apps import AppConfig


class GuiasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'guias'
    verbose_name = 'Guias - Personas Nuevas'
    
    def ready(self):
        # Importar señales si las hay
        pass