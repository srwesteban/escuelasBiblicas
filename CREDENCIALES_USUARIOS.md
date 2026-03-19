# 🔐 Credenciales de Usuarios - HechosHub

## 👑 **SUPERUSUARIO (Acceso Completo)**
- **Email**: `admin@hechoshub.com`
- **Contraseña**: `admin123`
- **Rol**: Super Admin
- **Acceso**: Todo el sistema + Panel Admin

---

## 🏢 **SISTEMA DE SEDES**

### 🏛️ **SEDE CENTRAL**
#### Admin de Sede
- **Email**: `admin@sedecentral.com`
- **Contraseña**: `password123`
- **Rol**: Admin de Escuela
- **Sede**: Sede Central
- **Acceso**: Gestión completa de la sede

#### Profesor
- **Email**: `profesor@sedecentral.com`
- **Contraseña**: `password123`
- **Rol**: Profesor
- **Sede**: Sede Central
- **Acceso**: Cursos, clases, asistencia, notas

#### Estudiante
- **Email**: `estudiante@sedecentral.com`
- **Contraseña**: `password123`
- **Rol**: Estudiante
- **Sede**: Sede Central
- **Acceso**: Cursos matriculados, notas, asistencia

---

## 👥 **APP GUIAS - PERSONAS NUEVAS**

### 🔐 **Administradores de Guias**
- **Email**: `admin@guias.com`
- **Contraseña**: `password123`
- **Rol**: Admin de Aplicación
- **Acceso**: Gestión completa de personas nuevas, eventos y ministerios

- **Email**: `coordinador@guias.com`
- **Contraseña**: `password123`
- **Rol**: Admin de Aplicación
- **Acceso**: Gestión completa de personas nuevas, eventos y ministerios

### 👤 **Usuario de Guias**
- **Email**: `voluntario@guias.com`
- **Contraseña**: `password123`
- **Rol**: Usuario
- **Acceso**: Ver y editar personas, agregar seguimientos

### 📊 **Datos de Prueba Guias**
- **10 personas nuevas** registradas
- **1 sede** (Sede Central)
- **Permisos asignados** correctamente
- **Dashboard dinámico** según permisos del usuario

### 🎯 **Funcionalidades Guias**
- ✅ **Dashboard** con estadísticas en tiempo real
- ✅ **Registro de personas nuevas** con formulario completo
- ✅ **Lista de personas** con filtros y búsqueda
- ✅ **Sistema de seguimiento** para cada persona
- ✅ **Gestión de eventos especiales** (bautismos, clases, etc.)
- ✅ **Gestión de ministerios** disponibles
- ✅ **Datos reutilizables** para otras aplicaciones

### 🔗 **URLs de Guias**
- **Dashboard**: `http://localhost:8000/guias/`
- **Lista de Personas**: `http://localhost:8000/guias/personas/`
- **Nueva Persona**: `http://localhost:8000/guias/personas/crear/`
- **Eventos**: `http://localhost:8000/guias/eventos/`
- **Ministerios**: `http://localhost:8000/guias/ministerios/`

---

## 🧹 **LIMPIEZA REALIZADA**
Los usuarios de prueba legacy han sido eliminados de la base de datos para mantener solo el sistema de sedes activo.

## 📊 **DATOS DE PRUEBA DISPONIBLES**

### **Sede Central**
- **16 Clases** distribuidas en 2 cursos
- **16 Asistencias** registradas
- **9 Notas** de evaluación
- **1 Estudiante** matriculado
- **1 Profesor** asignado
- **3 Rutas de Estudio** disponibles

---

## 🚀 **CÓMO USAR**

1. **Acceder** a http://localhost:8000
2. **Hacer login** con cualquiera de las credenciales
3. **Explorar** las funcionalidades según el rol

## 📱 **FUNCIONALIDADES POR ROL**

### **Super Admin**
- ✅ Acceso completo al sistema
- ✅ Panel de administración Django
- ✅ Gestión de usuarios y permisos
- ✅ Todos los módulos disponibles

### **Admin de Escuelas**
- ✅ Gestión de estudiantes
- ✅ Gestión de profesores
- ✅ Gestión de cursos
- ✅ Gestión de rutas de estudio
- ✅ Gestión de matrículas
- ✅ Dashboard específico

### **Profesores**
- ✅ Ver sus cursos asignados
- ✅ Crear y gestionar clases
- ✅ Tomar asistencia
- ✅ Registrar notas
- ✅ Dashboard con estadísticas

### **Estudiantes**
- ✅ Ver cursos matriculados
- ✅ Ver notas y calificaciones
- ✅ Ver asistencia
- ✅ Dashboard personal

---

## 🔧 **COMANDOS ÚTILES**

### **Gestión de Sedes**
```bash
# Crear nueva sede con datos de ejemplo
python manage.py create_sedes \
  --sede-nombre "Sede Sur" \
  --sede-direccion "Calle Sur 789, Ciudad" \
  --sede-telefono "+1-234-567-8902" \
  --sede-email "sur@iglesia.com" \
  --pastor "Pastor Carlos López"

# Asignar sede a usuarios existentes
python manage.py assign_sedes

# Asignar sede específica a usuario específico
python manage.py assign_sedes --user-id 1 --sede-id 1
```

### **Limpieza de Base de Datos**
```bash
# Ver usuarios que serían eliminados (dry-run)
python manage.py cleanup_users --dry-run

# Eliminar usuarios sin sede asignada
python manage.py cleanup_users --force

# Limpiar TODOS los datos y dejar solo Sede Central
python manage.py cleanup_all_data --force
```

### **Corrección de Emails**
```bash
# Ver emails que serían corregidos (dry-run)
python manage.py fix_emails --dry-run

# Corregir emails con guiones bajos
python manage.py fix_emails
```

### **Datos de Prueba**
```bash
# Crear clases, asistencias y notas de prueba para todas las sedes
python manage.py create_clases_prueba

# Crear datos de prueba para una sede específica
python manage.py create_clases_prueba --sede-id 1
```

### **Gestión de Usuarios (Legacy)**
```bash
# Crear admin de escuelas adicional
python manage.py create_admin_escuela --email nuevo@ejemplo.com --password nueva123

# Inicializar datos del sistema
python manage.py init_data

# Crear datos de ejemplo
python manage.py create_sample_data
```

---

## 🎯 **RECOMENDACIÓN DE PRUEBA**

### **Sistema de Sedes (Activo)**
Para probar el sistema de sedes:

1. **Iniciar** con **Admin de Sede** (`admin@sedecentral.com`)
2. **Explorar** el dashboard de la sede
3. **Gestionar** estudiantes, profesores y cursos de la sede
4. **Cambiar** a **Profesor** (`profesor@sedecentral.com`)
5. **Probar** gestión de clases, asistencia y notas
6. **Cambiar** a **Estudiante** (`estudiante@sedecentral.com`)
7. **Verificar** acceso a cursos, notas y asistencia

### **Super Admin (Acceso Global)**
Para gestión global del sistema:

1. **Iniciar** con el **Super Admin** (`admin@hechoshub.com`)
2. **Explorar** el dashboard central
3. **Acceder** al panel de administración Django
4. **Gestionar** sedes y usuarios globalmente

### **App Guias (Personas Nuevas)**
Para probar el sistema de Guias:

1. **Iniciar** con **Admin de Guias** (`admin@guias.com`)
2. **Explorar** el dashboard de Guias con estadísticas
3. **Revisar** la lista de personas de prueba
4. **Crear** una nueva persona con el formulario completo
5. **Probar** el sistema de seguimiento
6. **Cambiar** a **Usuario de Guias** (`voluntario@guias.com`)
7. **Verificar** permisos limitados según el rol
8. **Explorar** gestión de eventos y ministerios

**¡Disfruta explorando HechosHub!** 🎉
