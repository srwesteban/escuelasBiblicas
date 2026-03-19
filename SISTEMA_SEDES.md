# Sistema de Sedes - HechosHub

## Resumen de Cambios

Se ha implementado un sistema completo de sedes para el módulo Hechos, permitiendo que cada sede de la iglesia maneje sus datos de forma independiente.

## Cambios Realizados

### 1. Modelo Sede
- **Archivo**: `core/models.py`
- **Nuevo modelo**: `Sede`
- **Campos**:
  - `nombre`: Nombre de la sede
  - `direccion`: Dirección física
  - `telefono`: Teléfono de contacto
  - `email`: Email de contacto
  - `pastor_responsable`: Pastor a cargo
  - `descripcion`: Descripción adicional
  - `is_active`: Estado activo/inactivo

### 2. Actualización de Modelos Existentes
Todos los modelos del módulo `hechos` ahora incluyen una relación con `Sede`:

- **Estudiante**: Campo `sede` agregado
- **Profesor**: Campo `sede` agregado
- **AdminEscuela**: Campo `sede` agregado (reemplaza `escuela`)
- **RutaEstudio**: Campo `sede` agregado
- **Curso**: Campo `sede` agregado
- **Matricula**: Campo `sede` agregado
- **Clase**: Campo `sede` agregado
- **Asistencia**: Campo `sede` agregado
- **Nota**: Campo `sede` agregado

### 3. Actualización de Vistas
- **Archivo**: `hechos/views.py`
- **Función helper**: `get_user_sede()` para obtener la sede del usuario
- **Filtrado**: Todas las vistas ahora filtran por sede del usuario
- **Validación**: Verificación de que el usuario tenga una sede asignada

### 4. Actualización de Templates
- **Dashboard**: Muestra información de la sede actual
- **Listas**: Incluyen indicador de sede en los headers
- **Filtrado visual**: Los usuarios ven solo datos de su sede

### 5. Comandos de Gestión
- **`create_sedes`**: Crea sedes con datos de ejemplo
- **`assign_sedes`**: Asigna sedes a usuarios existentes

## Características del Sistema

### Independencia por Sede
- Cada sede maneja sus propios datos
- Estudiantes, profesores, cursos, etc. están aislados por sede
- Los usuarios solo ven información de su sede asignada

### Códigos Únicos por Sede
- Los códigos de estudiantes y profesores son únicos por sede
- Formato: `EST-0001`, `PROF-0001`, etc.
- Cada sede puede tener su propia secuencia

### Gestión de Usuarios
- Los usuarios pueden tener una sede asignada a nivel global
- Los perfiles específicos (estudiante, profesor, admin) también tienen sede
- Prioridad: Perfil específico > Sede global

## Uso del Sistema

### Crear una Nueva Sede
```bash
python manage.py create_sedes \
  --sede-nombre "Sede Sur" \
  --sede-direccion "Calle Sur 789, Ciudad" \
  --sede-telefono "+1-234-567-8902" \
  --sede-email "sur@iglesia.com" \
  --pastor "Pastor Carlos López"
```

### Asignar Sede a Usuarios Existentes
```bash
# Asignar a todos los usuarios sin sede
python manage.py assign_sedes

# Asignar a un usuario específico
python manage.py assign_sedes --user-id 1

# Asignar a una sede específica
python manage.py assign_sedes --sede-id 1
```

## Credenciales de Prueba

### Sede Central
- **Admin**: `admin_sede_central` / `password123`
- **Profesor**: `profesor_sede_central` / `password123`
- **Estudiante**: `estudiante_sede_central` / `password123`

### Sede Norte
- **Admin**: `admin_sede_norte` / `password123`
- **Profesor**: `profesor_sede_norte` / `password123`
- **Estudiante**: `estudiante_sede_norte` / `password123`

## Beneficios

1. **Aislamiento de Datos**: Cada sede mantiene sus datos separados
2. **Escalabilidad**: Fácil agregar nuevas sedes
3. **Seguridad**: Los usuarios solo acceden a datos de su sede
4. **Flexibilidad**: Cada sede puede tener su propia estructura
5. **Mantenimiento**: Gestión centralizada con datos independientes

## Próximos Pasos

1. **Migración de Datos Existentes**: Asignar sedes a usuarios existentes
2. **Configuración de Sedes**: Crear sedes para cada ubicación de la iglesia
3. **Capacitación**: Entrenar a los administradores de cada sede
4. **Monitoreo**: Supervisar el funcionamiento del sistema por sede

## Notas Técnicas

- Las migraciones se han aplicado correctamente
- Los campos `sede` son opcionales para compatibilidad con datos existentes
- Se recomienda asignar sedes a todos los usuarios antes de usar el sistema en producción
- El sistema mantiene la funcionalidad existente mientras agrega la nueva funcionalidad de sedes
