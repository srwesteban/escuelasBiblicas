# HechosHub - Sistema Modular para Escuelas Bíblicas

HechosHub es un sistema web modular desarrollado con Django que permite gestionar escuelas bíblicas de manera eficiente y organizada. El sistema está diseñado con una arquitectura modular donde existe un **core** central y se pueden registrar múltiples aplicaciones.

## 🚀 Características Principales

### Core (Sistema General)
- **Autenticación centralizada** usando el sistema de usuarios de Django
- **Modelo de usuario extendido** con roles y permisos
- **Roles globales**:
  - **Super Admin**: controla todo el sistema
  - **Admin de aplicación**: controla una aplicación específica
  - **Usuario**: acceso básico según permisos
- **Dashboard central** con navegación dinámica
- **Autenticación social** (Google, GitHub) con django-allauth

### Módulo Hechos (Escuelas Bíblicas)
- **Gestión de Estudiantes**: perfiles, matrículas, notas, asistencia
- **Gestión de Profesores**: perfiles, cursos, clases, calificaciones
- **Gestión de Cursos**: rutas de estudio, horarios, capacidad
- **Sistema de Asistencia**: registro por clase
- **Sistema de Notas**: calificaciones y evaluaciones
- **Dashboard específico** según el rol del usuario

## 🛠️ Tecnologías Utilizadas

- **Django 5.2.6** - Framework web
- **SQLite** - Base de datos
- **Bootstrap 5** - Framework CSS
- **django-allauth** - Autenticación social
- **Font Awesome** - Iconos
- **Python 3.12** - Lenguaje de programación

## 📋 Requisitos del Sistema

- Python 3.12+
- pip (gestor de paquetes de Python)
- Git (opcional, para clonar el repositorio)

## 🚀 Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone <url-del-repositorio>
cd HechosHub
```

### 2. Crear Entorno Virtual
```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar Dependencias
```bash
pip install django django-allauth pillow requests PyJWT cryptography
```

### 4. Configurar Base de Datos
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Inicializar Datos Básicos
```bash
python manage.py init_data
```

### 6. Ejecutar el Servidor
```bash
python manage.py runserver
```

## 🔐 Acceso al Sistema

### Credenciales por Defecto
- **URL**: http://localhost:8000
- **Admin**: http://localhost:8000/admin/
- **Usuario**: admin@hechoshub.com
- **Contraseña**: admin123

### Primer Acceso
1. Ve a http://localhost:8000
2. Inicia sesión con las credenciales por defecto
3. Explora el dashboard central
4. Accede al módulo "Hechos" desde el menú lateral

## 📱 Funcionalidades por Rol

### Super Administrador
- Acceso completo al sistema
- Gestión de usuarios y roles
- Configuración de módulos
- Acceso al panel de administración de Django

### Admin de Escuela
- Gestión de estudiantes, profesores y cursos
- Creación de rutas de estudio
- Asignación de matrículas
- Reportes y estadísticas

### Profesor
- Ver sus cursos asignados
- Crear y gestionar clases
- Tomar asistencia de estudiantes
- Asignar notas y calificaciones

### Estudiante
- Ver cursos matriculados
- Consultar notas y calificaciones
- Ver horarios de clases
- Revisar asistencia

## 🏗️ Arquitectura del Sistema

```
hechoshub/
├── hechoshub/          # Configuración principal
├── core/               # App central (usuarios, roles, dashboard)
├── hechos/             # App de escuelas bíblicas
├── templates/          # Templates HTML
├── static/            # Archivos estáticos (CSS, JS, imágenes)
├── media/             # Archivos subidos por usuarios
└── db.sqlite3         # Base de datos SQLite
```

## 🔧 Configuración Adicional

### Autenticación Social (Opcional)
Para configurar autenticación con Google o GitHub:

1. Ve al panel de administración: http://localhost:8000/admin/
2. Navega a "Social Applications"
3. Agrega una nueva aplicación social
4. Configura las credenciales de OAuth

### Personalización de Módulos
Para agregar nuevos módulos:

1. Crea una nueva app Django
2. Registra el módulo en `AppModule`
3. Configura permisos de usuario
4. Agrega las URLs correspondientes

## 📊 Modelos de Datos

### Core
- **User**: Usuario extendido con roles
- **AppModule**: Módulos del sistema
- **UserAppPermission**: Permisos por módulo

### Hechos
- **Estudiante**: Perfil de estudiante
- **Profesor**: Perfil de profesor
- **AdminEscuela**: Perfil de administrador
- **RutaEstudio**: Rutas de estudio disponibles
- **Curso**: Cursos específicos
- **Matricula**: Matrículas de estudiantes
- **Clase**: Sesiones de clase
- **Asistencia**: Registro de asistencia
- **Nota**: Calificaciones y evaluaciones

## 🎨 Personalización Visual

El sistema utiliza Bootstrap 5 con un tema personalizado. Los colores principales son:
- **Primario**: #2c3e50 (Azul oscuro)
- **Secundario**: #34495e (Gris oscuro)
- **Acento**: #3498db (Azul claro)
- **Éxito**: #27ae60 (Verde)
- **Advertencia**: #f39c12 (Naranja)
- **Peligro**: #e74c3c (Rojo)

## 🚀 Despliegue en Producción

Para desplegar en producción:

1. Configura una base de datos PostgreSQL o MySQL
2. Actualiza `settings.py` con configuración de producción
3. Configura variables de entorno para credenciales
4. Usa un servidor web como Nginx + Gunicorn
5. Configura SSL/HTTPS

## 📝 Comandos Útiles

```bash
# Crear superusuario
python manage.py createsuperuser

# Inicializar datos básicos
python manage.py init_data

# Recopilar archivos estáticos
python manage.py collectstatic

# Ejecutar pruebas
python manage.py test
```

## 🤝 Contribución

Para contribuir al proyecto:

1. Fork el repositorio
2. Crea una rama para tu feature
3. Realiza los cambios
4. Envía un Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo LICENSE para más detalles.

## 🆘 Soporte

Para soporte técnico o preguntas:
- Crea un issue en el repositorio
- Contacta al equipo de desarrollo
- Revisa la documentación de Django

---

**HechosHub** - Sistema Modular para Escuelas Bíblicas
Desarrollado con ❤️ para la comunidad cristiana
