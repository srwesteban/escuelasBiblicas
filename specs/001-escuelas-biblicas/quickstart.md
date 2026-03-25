# Quickstart - Plataforma de Escuelas Biblicas

## Objetivo
Validar rapidamente el MVP funcional del feature `001-escuelas-biblicas`.

## Preparacion
```bash
make migrate
make seed
make run
```

## Flujo de validacion esperado

### 1. Registro de estudiante
- abrir `/accounts/signup/`
- crear una cuenta nueva
- iniciar sesion con esa cuenta

### 2. Visualizacion de escuelas
- entrar a `/hechos/escuelas/`
- confirmar que el estudiante puede ver escuelas disponibles
- confirmar que no puede ingresar a una escuela sin matricula aprobada

### 3. Solicitud de matricula
- desde el listado de escuelas y grupos disponibles, solicitar matricula
- confirmar que la solicitud queda en estado `pendiente`

### 4. Aprobacion manual por profesor
- iniciar sesion como profesor
- abrir listado de solicitudes de sus escuelas
- aprobar una solicitud con pago validado manualmente
- confirmar que el cupo baja en una unidad

### 5. Acceso del estudiante
- volver a iniciar sesion como estudiante
- confirmar que ahora puede ingresar a la escuela aprobada
- validar visualizacion de notas y asistencia cuando existan datos

### 6. Administracion de sede
- iniciar sesion como coordinador
- crear escuela, nivel y grupo
- asignar profesor

### 7. Administracion global
- iniciar sesion como Director
- abrir `/director/`
- crear sede
- crear coordinador de la sede

## Resultado esperado
El sistema permite registro, solicitud de matricula, aprobacion manual por profesor, descuento de cupo y acceso restringido a Escuelas Biblicas aprobadas.
