# Spec Kit - Specify

## Nombre de la iniciativa
Hechos Hub - Plataforma de Escuelas Biblicas

## Resumen
Hechos Hub sera una plataforma para administrar Escuelas Biblicas por sedes. Permitira registrar estudiantes, recibir solicitudes de matricula, aprobarlas manualmente, controlar cupos, organizar escuelas por periodos y grupos, y gestionar asistencia y notas.

## Problema
La operacion academica de las Escuelas Biblicas requiere un sistema centralizado que permita:

- administrar sedes
- crear escuelas por sede
- organizar periodos y grupos
- gestionar profesores
- recibir solicitudes de matricula
- aprobar manualmente estudiantes segun pago recibido
- dar acceso solo a estudiantes aprobados
- registrar asistencia y notas

## Objetivo
Construir una plataforma que funcione como portal academico de iglesia, con roles claros y flujo manual de matricula, manteniendo una experiencia simple, rapida y facil de ampliar.

## Alcance inicial

### Incluye
- sedes
- coordinadores por sede
- escuelas
- periodos
- grupos
- profesores
- estudiantes
- registro e inicio de sesion
- solicitudes de matricula
- aprobacion manual de matricula
- control de cupos
- asistencia
- notas

### No incluye por ahora
- pagos en linea
- integracion con pasarelas
- automatizacion contable
- reporteria avanzada

## Roles

### adminDirector
- administra todo el sistema
- crea sedes
- crea coordinadores por sede
- tiene acceso global

### coordinador
- administra una sede especifica
- crea escuelas
- configura cupos
- configura fechas de inicio y fin
- configura periodos y grupos
- asigna profesores
- crea credenciales de profesores

### profesor
- administra las escuelas que tiene asignadas
- ve solicitudes de matricula de sus escuelas
- valida manualmente el pago recibido
- acepta o rechaza estudiantes
- al aceptar descuenta un cupo
- define cantidad de notas
- registra notas
- registra asistencia

### estudiante
- se registra
- inicia sesion
- ve las escuelas disponibles
- solicita matricularse a una escuela
- solo accede a escuelas aprobadas
- ve notas y asistencia de sus escuelas

## Lenguaje oficial
- sistema: `Hechos Hub`
- area academica principal: `Escuelas Biblicas`
- crear cuenta: `Registrarse`
- entrar al sistema: `Iniciar sesion`
- pedir ingreso: `Solicitar matricula`
- aprobar ingreso manualmente: `Matricular`

## Modelo funcional

### Jerarquia academica
- una sede tiene muchas escuelas
- una escuela puede tener varios periodos
- un periodo puede tener varios grupos

### Ejemplo
- Sede: Hechos Norte
- Escuela: Primeros Pasos
- Periodo: Ciclo 2
- Grupo: Grupo A

## Flujo principal de matricula
1. el estudiante se registra
2. el estudiante inicia sesion
3. el estudiante visualiza escuelas disponibles
4. el estudiante solicita matricula a una escuela
5. la solicitud queda en estado pendiente
6. el profesor revisa las solicitudes de la escuela
7. el profesor valida manualmente el pago
8. el profesor acepta o rechaza la solicitud
9. si acepta:
- el estudiante queda matriculado
- se habilita acceso a la escuela
- se descuenta un cupo
10. si rechaza:
- la solicitud queda rechazada
- el estudiante no obtiene acceso

## Reglas de negocio
- la matricula no es automatica
- el pago se valida manualmente por el profesor
- el estudiante solo entra a escuelas aprobadas
- un cupo solo se descuenta cuando la solicitud es aprobada
- cada rol tiene tareas separadas
- el coordinador no reemplaza al profesor en la aprobacion de matricula
- el profesor solo puede gestionar sus escuelas asignadas
- el adminDirector puede ver todas las sedes y toda la operacion

## Historias de usuario base

### HU-01 Registro
Como visitante, quiero registrarme en la plataforma para luego poder iniciar sesion y solicitar matricula.

### HU-02 Ver escuelas
Como estudiante, quiero ver las escuelas disponibles para decidir a cual solicitar ingreso.

### HU-03 Solicitar matricula
Como estudiante, quiero solicitar matricula a una escuela para entrar al proceso de aprobacion.

### HU-04 Aprobar estudiante
Como profesor, quiero revisar solicitudes pendientes y aprobar estudiantes que ya pagaron para habilitarles acceso.

### HU-05 Rechazar estudiante
Como profesor, quiero rechazar solicitudes no aprobadas para mantener control de acceso y cupos.

### HU-06 Gestionar escuelas por sede
Como coordinador, quiero crear escuelas, periodos, grupos y asignar profesores para administrar mi sede.

### HU-07 Gestionar sedes
Como adminDirector, quiero crear sedes y coordinadores para operar multiples sedes desde una sola plataforma.

### HU-08 Registrar asistencia
Como profesor, quiero registrar asistencia para llevar seguimiento de cada estudiante.

### HU-09 Registrar notas
Como profesor, quiero definir notas y calificarlas para evaluar el avance de los estudiantes.

### HU-10 Consultar progreso
Como estudiante, quiero ver mis notas y asistencias para conocer mi progreso.

## Criterios de aceptacion base

### Registro
- el usuario puede crear cuenta con email y contrasena
- despues del registro puede iniciar sesion

### Solicitud de matricula
- un estudiante autenticado puede solicitar ingreso a una escuela
- la solicitud queda pendiente hasta revision del profesor

### Aprobacion
- el profesor puede ver solicitudes de sus escuelas
- el profesor puede aprobar o rechazar
- al aprobar se habilita acceso y se descuenta cupo

### Acceso restringido
- el estudiante ve todas las escuelas disponibles
- solo puede entrar a las escuelas donde fue aprobado

### Gestion academica
- el coordinador puede crear escuelas, periodos y grupos
- puede asignar un profesor a una escuela o grupo

## Consideraciones tecnicas
- mantener arquitectura Django modular
- separar claramente `core`, `hechos` y cualquier modulo futuro
- usar nombres consistentes en vistas, rutas y templates
- evitar logica legacy que no coincida con el dominio actual
- priorizar rendimiento simple sobre complejidad prematura
- mantener compatibilidad con trabajo asistido por IA en Cursor mediante estructura clara, nombres semanticos y baja duplicacion

## Riesgos actuales
- el proyecto todavia mezcla conceptos previos como cursos, rutas y escuela biblica
- hay comandos legacy que pueden no coincidir con el dominio nuevo
- parte de la semantica visible y tecnica aun necesita alinearse

## Resultado esperado del MVP
Al finalizar el MVP, una iglesia debe poder operar varias sedes, publicar escuelas, registrar estudiantes, recibir solicitudes de matricula, aprobarlas manualmente y gestionar asistencia y notas desde una sola plataforma.
