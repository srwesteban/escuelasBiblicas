# Requerimientos Resumidos

## Objetivo
Convertir `HechosHub` en una plataforma tipo portal universitario, adaptada a una iglesia, donde una persona pueda:

- conocer la iglesia y sus sedes
- ver oferta formativa y actividades
- inscribirse a escuela biblica, eventos o procesos
- consultar su avance, clases, notas y asistencia
- permitir a lideres y administradores gestionar todo desde un panel interno

## Vision Funcional
El sistema debe comportarse como una "universidad de iglesia":

- portal publico institucional
- catalogo de programas, rutas y cursos
- admision o inscripcion de alumnos
- gestion academica interna
- seguimiento pastoral y administrativo

## Roles Minimos
- visitante: ve informacion publica
- estudiante: consulta cursos, asistencia, notas, progreso y horarios
- profesor: gestiona clases, asistencia, evaluaciones y observaciones
- administrador academico: crea rutas, cursos, grupos, profesores y estudiantes
- super admin: controla todo el sistema, modulos, usuarios y sedes

## Modulos MVP

### 1. Portal Publico
- pagina de inicio
- quienes somos
- sedes
- oferta academica o rutas de estudio
- calendario de eventos
- formulario de contacto / interes / oracion
- acceso a iniciar sesion

### 2. Admisiones / Inscripciones
- formulario de aspirante
- captura de datos personales y sede
- seleccion de programa o ruta
- estado de solicitud: pendiente, aprobada, rechazada

### 3. Gestion Academica
- rutas de estudio
- cursos
- ediciones o grupos
- horarios
- asignacion de profesor
- matriculas

### 4. Portal del Estudiante
- dashboard
- materias activas
- progreso por ruta
- asistencia
- notas
- historial

### 5. Portal del Profesor
- dashboard
- grupos asignados
- registro de asistencia
- carga de notas
- observaciones por alumno

### 6. Administracion
- usuarios
- roles
- sedes
- modulos
- reportes basicos

## Reglas de Negocio Iniciales
- un usuario puede pertenecer a una sede
- un estudiante puede estar inscrito en una o varias ediciones de curso
- cada edicion tiene cupo, horario, fechas y profesor
- solo profesor o admin pueden cargar asistencia y notas
- el estudiante solo puede ver su propia informacion
- super admin puede ver todas las sedes

## Requerimientos No Funcionales
- interfaz simple, limpia y responsive
- autenticacion por email
- base local para desarrollo y base intercambiable a futuro
- permisos por rol y por modulo
- estructura lista para crecer por sedes y nuevos modulos

## Lo Que Ya Existe y Conviene Reusar
- usuarios con roles globales
- sedes
- estudiantes, profesores y admin escuela
- rutas, cursos, clases, matriculas, asistencia y notas
- modulo guias para seguimiento de personas

## Pendientes por Confirmar
1. ¿La prioridad principal es escuela biblica, instituto, discipulado o todo junto?
2. ¿Necesitas pagos, becas o solo inscripcion manual?
3. ¿Quieres inscripcion publica abierta o aprobacion interna antes de activar alumno?
4. ¿Habra periodos academicos por semestre, trimestre o cursos continuos?
5. ¿Quieres que el portal publico reemplace la web principal o solo sea un acceso interno con landing?

## Recomendacion de MVP
Primero construir:

- portal publico
- admisiones
- dashboard de estudiante
- dashboard de profesor
- panel academico por sede

Despues agregar:

- reportes avanzados
- documentos descargables
- pagos
- integraciones externas

