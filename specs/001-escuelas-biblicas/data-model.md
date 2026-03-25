# Data Model - Plataforma de Escuelas Biblicas

## Entidades principales

### User
- id
- email
- password
- role
- sede_id opcional
- is_active

## Roles visibles
- Director
- coordinador
- profesor
- estudiante

### Sede
- id
- nombre
- direccion
- telefono
- email
- is_active

### Escuela
- id
- sede_id
- nombre
- descripcion
- cupo_total
- cupo_disponible
- fecha_inicio
- fecha_fin
- is_active

### Nivel
- id
- escuela_id
- nombre
- descripcion opcional
- orden opcional
- is_active

### Grupo
- id
- nivel_id
- nombre
- profesor_id
- cupo_total
- cupo_disponible
- is_active

### ProfesorProfile
- id
- user_id
- sede_id
- especialidad opcional
- is_active

### EstudianteProfile
- id
- user_id
- sede_id opcional
- telefono opcional
- is_active

### SolicitudMatricula
- id
- estudiante_id
- escuela_id
- nivel_id opcional
- grupo_id opcional
- estado: pendiente | aprobada | rechazada
- fecha_solicitud
- observaciones opcional

### Matricula
- id
- estudiante_id
- escuela_id
- nivel_id
- grupo_id
- profesor_aprobador_id
- solicitud_id
- pago_validado_manual: bool
- fecha_aprobacion
- estado: activa | cancelada | finalizada

### ConfiguracionNotas
- id
- escuela_id o grupo_id
- cantidad_notas
- creado_por_profesor_id

### Nota
- id
- matricula_id
- titulo
- orden
- valor
- puntaje_obtenido
- fecha_registro

### Asistencia
- id
- matricula_id
- fecha
- estado: presente | ausente | tarde | justificado
- registrado_por_profesor_id

## Relaciones
- una sede tiene muchas escuelas
- una escuela tiene muchos niveles
- un nivel tiene muchos grupos
- un grupo tiene un profesor asignado
- un estudiante puede tener muchas solicitudes
- una solicitud aprobada produce una matricula
- una matricula habilita acceso a la escuela
- una matricula tiene notas y asistencias

## Reglas de integridad
- no se puede aprobar una solicitud si no hay cupos disponibles
- una solicitud aprobada debe generar una matricula activa
- un estudiante no debe tener matriculas activas duplicadas para la misma escuela/nivel/grupo
- solo el profesor asignado o un rol superior puede registrar notas y asistencia
- solo usuarios con matricula aprobada pueden acceder al contenido academico
