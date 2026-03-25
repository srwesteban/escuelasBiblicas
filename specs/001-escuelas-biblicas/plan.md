# Implementation Plan: Plataforma de Escuelas Biblicas

**Branch**: `001-escuelas-biblicas` | **Date**: 2026-03-19 | **Spec**: `/specs/001-escuelas-biblicas/spec.md`
**Input**: Feature specification from `/specs/001-escuelas-biblicas/spec.md`

## Summary

Implementar Hechos Hub como plataforma de Escuelas Biblicas multi-sede con flujo manual de matricula. La estrategia tecnica recomendada es evolucionar el monolito Django existente, concentrando autenticacion y roles en `core`, moviendo el dominio academico principal a `hechos`, y alineando la semantica del sistema con los conceptos `sede`, `escuela`, `nivel`, `grupo`, `solicitud de matricula` y `matricula aprobada`.

## Technical Context

**Language/Version**: Python 3.12 + Django 5.2.x  
**Primary Dependencies**: Django, django-allauth, Pillow  
**Storage**: SQLite en desarrollo local, con configuracion intercambiable para PostgreSQL futura  
**Testing**: Django test runner / unittest; pruebas de integracion para flujos criticos  
**Target Platform**: Aplicacion web server-rendered sobre navegador moderno  
**Project Type**: Aplicacion web monolitica modular Django  
**Performance Goals**: Flujos administrativos y academicos con respuesta percibida < 500 ms en entorno local para operaciones comunes  
**Constraints**: Mantener simplicidad, baja duplicacion, semantica clara, y compatibilidad alta con trabajo asistido por IA en Cursor  
**Scale/Scope**: Multiples sedes, decenas de escuelas por sede, cientos de estudiantes por nivel/grupo en una primera etapa

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- `Domain-First Semantics`: PASS. El plan usa `Escuelas Biblicas`, `coordinador`, `solicitud de matricula` y `matricula`.
- `Strict Role Separation`: PASS. Se mantienen tareas separadas entre Director, coordinador, profesor y estudiante.
- `Manual Enrollment Workflow Is Canonical`: PASS. La matricula se aprueba solo manualmente por profesor.
- `Modular Django Architecture With Low Duplication`: PASS con observacion. Requiere revisar conceptos legacy como `curso` y `ruta`.
- `Simplicity, Performance, and AI-Friendly Structure`: PASS. Se prioriza evolucion del monolito existente sobre reescritura.

## Project Structure

### Documentation (this feature)

```text
specs/001-escuelas-biblicas/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── implement.md
├── contracts/
│   └── http-surface.md
└── tasks.md
```

### Source Code (repository root)

```text
hechoshub/
├── settings.py
├── urls.py
└── db_config.py

core/
├── models.py
├── views.py
├── urls.py
└── management/commands/

hechos/
├── models.py
├── views.py
├── urls.py
├── admin.py
└── migrations/

templates/
├── base_modern.html
├── core/
├── account/
└── hechos/

static/
└── img/
```

**Structure Decision**: Mantener una aplicacion Django monolitica modular. `core` conserva autenticacion, usuarios, roles globales y sedes. `hechos` debe absorber y representar el dominio academico de Escuelas Biblicas. Las vistas publicas y de autenticacion permanecen en `templates/core/` y `templates/account/`. No se recomienda separar frontend/backend por ahora.

## Phase 0 Research Decisions

1. No crear un motor de pagos. El pago es un estado validado manualmente por el profesor.
2. Tratar `escuela` como termino de negocio principal. Si internamente existen modelos que hoy se comportan como `curso`, deben evaluarse para renombrar semanticamente o mapearse claramente.
3. Conservar la base swappable ya configurada, con SQLite local por defecto.
4. Priorizar server-rendered templates antes de introducir SPA o JS compleja.
5. Modelar `solicitud de matricula` como entidad separada de `matricula`, para mantener trazabilidad del proceso manual.

## Phase 1 Design Decisions

### Proposed Domain Mapping
- `core.User`: mantiene autenticacion, avatar y rol global.
- `core.Sede`: se conserva como sede.
- `hechos`: debe contener escuelas, niveles, grupos/ediciones, solicitudes, matriculas, notas y asistencia.
- Profesor y estudiante pueden seguir vinculados al usuario, pero sus permisos operativos deben depender de asignaciones reales a escuelas/grupos.

### Recommended Role Strategy
- `Director`: rol global visible.
- `coordinador`: rol global o perfil por sede, segun la implementacion mas simple.
- `profesor`: usuario con perfil academico y asignaciones a escuelas/grupos.
- `estudiante`: usuario con una o mas solicitudes/matriculas.

### Migration Strategy
- No eliminar de golpe el dominio actual.
- Primero introducir la semantica nueva en spec y plan.
- Luego decidir si se reutilizan modelos existentes o se crean modelos nuevos con migracion progresiva.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Ninguna por ahora | N/A | N/A |
