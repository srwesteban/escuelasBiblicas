# HTTP Surface - Plataforma de Escuelas Biblicas

## Publico

### GET `/inicio/`
- muestra landing publica

### GET `/accounts/signup/`
- muestra registro de estudiante

### POST `/accounts/signup/`
- crea cuenta de usuario

### GET `/accounts/login/`
- muestra login

### POST `/accounts/login/`
- autentica usuario

## Estudiante

### GET `/hechos/escuelas/`
- lista escuelas disponibles

### POST `/hechos/escuelas/{edicion_id}/solicitar-matricula/`
- crea solicitud de matricula

### GET `/hechos/mis-solicitudes/`
- lista solicitudes del estudiante

### GET `/hechos/`
- lista escuelas aprobadas para el estudiante

### GET `/mis-notas/`
- muestra notas del estudiante

### GET `/mi-asistencia/`
- muestra asistencia del estudiante

## Profesor

### GET `/profesor/escuelas/`
- lista escuelas o grupos asignados

### GET `/profesor/solicitudes/`
- lista solicitudes pendientes de sus escuelas

### POST `/profesor/solicitudes/{id}/aprobar/`
- aprueba solicitud y crea matricula

### POST `/profesor/solicitudes/{id}/rechazar/`
- rechaza solicitud

### GET `/profesor/notas/`
- panel de notas

### POST `/profesor/notas/`
- registra notas

### GET `/profesor/asistencia/`
- panel de asistencia

### POST `/profesor/asistencia/`
- registra asistencia

## Coordinador

### GET `/coordinacion/`
- dashboard de sede

### GET `/coordinacion/escuelas/`
- lista escuelas de su sede

### POST `/coordinacion/escuelas/`
- crea escuela

### POST `/coordinacion/niveles/`
- crea nivel

### POST `/coordinacion/grupos/`
- crea grupo

### POST `/coordinacion/profesores/`
- crea profesor y credenciales

## Director

### GET `/director/`
- dashboard global

### POST `/direccion/sedes/`
- crea sede

### POST `/direccion/sedes/{sede_id}/coordinadores/crear/`
- crea coordinador de sede

## Nota
Las rutas exactas pueden ajustarse al estilo actual del proyecto, pero la superficie funcional debe cubrir estos contratos.
