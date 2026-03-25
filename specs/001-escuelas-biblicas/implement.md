# Implement Guide - Plataforma de Escuelas Biblicas

## Objetivo
Ejecutar la implementacion en orden minimo, reduciendo riesgo semantico y tecnico.

## Orden recomendado

### Fase 1
- alinear semantica visible del sistema con `Hechos Hub` y `Escuelas Biblicas`
- definir roles visibles y permisos base
- revisar conflicto entre modelos actuales y los conceptos nuevos

### Fase 2
- introducir `SolicitudMatricula`
- ajustar `Matricula` al nuevo flujo manual
- asegurar validacion de cupo al aprobar

### Fase 3
- construir experiencia del estudiante
- listado de escuelas
- solicitud de matricula
- acceso restringido

### Fase 4
- construir experiencia del profesor
- lista de solicitudes
- aprobacion/rechazo
- validacion manual de pago
- notas y asistencia

### Fase 5
- construir experiencia del coordinador
- crear escuelas
- crear niveles y grupos
- asignar profesores

### Fase 6
- construir experiencia del Director
- crear sedes
- crear coordinadores

## Principio de implementacion
No reescribir todo de una sola vez. Reusar la estructura actual donde sea razonable y refactorizar solo donde haya choque semantico o funcional fuerte.
