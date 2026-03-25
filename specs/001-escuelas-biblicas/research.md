# Research - Plataforma de Escuelas Biblicas

## Objetivo
Documentar decisiones iniciales antes de implementar el feature `001-escuelas-biblicas`.

## Decisiones tomadas

### 1. Mantener Django monolitico modular
Se reutiliza la arquitectura existente en lugar de dividir frontend/backend. Esto reduce complejidad, mejora velocidad de iteracion y mantiene el proyecto facil de navegar para humanos y agentes de IA.

### 2. El pago sera manual
No habra pasarela de pagos en el MVP. El profesor valida personalmente el pago y luego aprueba o rechaza la solicitud de matricula.

### 3. Solicitud y matricula son entidades distintas
`Solicitar matricula` no equivale a `matricular`. La solicitud representa el interes del estudiante; la matricula representa la aprobacion final con acceso habilitado.

### 4. La semantica oficial usara `escuela`
Aunque el proyecto actual tiene conceptos previos como `curso` o `ruta`, el lenguaje visible y la especificacion funcional deben hablar de `escuela`, `nivel` y `grupo`.

### 5. El profesor controla el acceso final
El profesor es quien revisa solicitudes de sus escuelas, valida el pago manual y decide si aprueba o rechaza. Solo al aprobar se descuenta un cupo.

## Riesgos detectados

- El dominio actual del proyecto contiene conceptos legacy que no coinciden totalmente con la semantica nueva.
- Puede haber solapamiento entre modelos actuales y los conceptos `escuela`, `nivel`, `grupo` y `solicitud`.
- El modulo `guias` existe pero no entra en el alcance actual.

## Recomendacion
Implementar por etapas, empezando por el flujo estudiante -> solicitud -> aprobacion profesor, y despues ajustar la administracion por sede y el modelo academico completo.
