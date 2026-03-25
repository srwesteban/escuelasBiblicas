# Tasks: Plataforma de Escuelas Biblicas

**Input**: Design documents from `/specs/001-escuelas-biblicas/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/http-surface.md

**Tests**: Incluir pruebas de integracion para flujos criticos de matricula y permisos antes de cerrar cada historia.

**Organization**: Tasks grouped by user story for independent delivery.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Preparar base semantica y tecnica del feature

- [x] T001 Crear o ajustar documentacion funcional base en `specs/001-escuelas-biblicas/`
- [x] T002 Revisar y mapear el dominio actual de `hechos/models.py` frente a `escuela`, `nivel`, `grupo`, `solicitud`
- [x] T003 [P] Revisar nombres visibles en `templates/` y rutas para alinear semantica de Escuelas Biblicas

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura obligatoria antes de historias de usuario

- [x] T004 Definir estrategia de roles y permisos base en `core/models.py` y/o perfiles relacionados
- [x] T005 Definir entidades academicas faltantes o adaptaciones en `hechos/models.py`
- [x] T006 [P] Preparar migraciones para sedes, escuelas, niveles, grupos/ediciones, solicitudes y matriculas
- [ ] T007 [P] Preparar estructura de vistas/rutas base para estudiante, profesor, coordinador y Director en `core/urls.py` y `hechos/urls.py`
- [x] T008 Preparar reglas de acceso para escuelas aprobadas y solicitudes pendientes

**Checkpoint**: Fundacion lista para implementar historias

---

## Phase 3: User Story 1 - Registro, solicitud y acceso del estudiante (Priority: P1) 🎯 MVP

**Goal**: Permitir al estudiante registrarse, ver escuelas y solicitar matricula.

**Independent Test**: Un estudiante nuevo puede registrarse, iniciar sesion, ver escuelas y dejar una solicitud pendiente sin tener acceso aun.

### Implementation for User Story 1

- [x] T009 [US1] Ajustar flujo de registro/login visible en `templates/account/`
- [x] T010 [US1] Crear listado visible de escuelas en `hechos/views.py`, `hechos/urls.py` y `templates/hechos/`
- [x] T011 [US1] Implementar entidad y logica de `SolicitudMatricula` en `hechos/models.py`
- [x] T012 [US1] Implementar accion `Solicitar matricula` desde el estudiante
- [x] T013 [US1] Bloquear acceso a escuelas no aprobadas en vistas del estudiante
- [x] T014 [US1] Crear panel de `mis solicitudes` y `mis escuelas`

**Checkpoint**: El estudiante puede registrarse y solicitar matricula.

---

## Phase 4: User Story 2 - Aprobacion manual por profesor (Priority: P1)

**Goal**: Permitir al profesor aprobar o rechazar solicitudes y controlar cupos.

**Independent Test**: Un profesor asignado puede aprobar una solicitud, validar pago manualmente y habilitar acceso al estudiante.

### Implementation for User Story 2

- [ ] T015 [US2] Crear panel de solicitudes del profesor en `hechos/views.py` y `templates/hechos/`
- [ ] T016 [US2] Implementar aprobacion manual de solicitud y creacion de matricula
- [ ] T017 [US2] Implementar rechazo de solicitud
- [ ] T018 [US2] Descontar cupo al aprobar y validar que no se apruebe sin cupo
- [ ] T019 [US2] Restringir al profesor a sus escuelas/grupos asignados

**Checkpoint**: El flujo manual de matricula funciona extremo a extremo.

---

## Phase 5: User Story 3 - Administracion academica por sede (Priority: P2)

**Goal**: Permitir al coordinador crear y estructurar la oferta academica de su sede.

**Independent Test**: Un coordinador puede crear una escuela, su nivel, su grupo y asignar un profesor.

### Implementation for User Story 3

- [ ] T020 [US3] Crear dashboard del coordinador por sede
- [ ] T021 [US3] Implementar creacion/edicion de escuelas
- [ ] T022 [US3] Implementar niveles y grupos
- [ ] T023 [US3] Implementar asignacion de profesor a escuela o grupo
- [ ] T024 [US3] Implementar generacion de credenciales para profesores

**Checkpoint**: La sede puede operar su estructura academica.

---

## Phase 6: User Story 4 - Gobierno global por Director (Priority: P3)

**Goal**: Permitir administracion multi-sede desde un rol global.

**Independent Test**: Un Director crea una sede y un coordinador que luego opera solo esa sede.

### Implementation for User Story 4

- [x] T025 [US4] Ajustar semantica visible del rol global `Director`
- [x] T026 [US4] Implementar gestion de sedes
- [x] T027 [US4] Implementar creacion de coordinadores por sede
- [x] T028 [US4] Crear dashboard global de direccion

**Checkpoint**: La plataforma soporta gobierno multi-sede.

---

## Phase 7: User Story 5 - Notas y asistencia del estudiante (Priority: P3)

**Goal**: Permitir seguimiento academico visible para estudiante y operable por profesor.

**Independent Test**: Un profesor registra notas/asistencia y el estudiante matriculado las puede consultar.

### Implementation for User Story 5

- [ ] T029 [US5] Ajustar configuracion de notas por profesor
- [ ] T030 [US5] Implementar carga de notas por escuela/grupo
- [ ] T031 [US5] Implementar registro de asistencia
- [ ] T032 [US5] Implementar vistas del estudiante para notas y asistencia

**Checkpoint**: El estudiante puede ver su progreso academico.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Mejoras globales del feature

- [x] T033 [P] Limpiar semantica legacy visible en templates, rutas y textos
- [x] T034 [P] Revisar comandos de carga de datos para alinearlos al dominio nuevo
- [ ] T035 Documentar flujo final en `README.md` o documentacion funcional
- [ ] T036 Ejecutar validacion de `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup primero
- Foundational bloquea todas las historias
- US1 y US2 son el MVP real
- US3 depende de la fundacion, pero puede empezar despues del modelo base
- US4 y US5 pueden ir despues del flujo principal

### MVP First

1. Completar Phase 1
2. Completar Phase 2
3. Completar User Story 1
4. Completar User Story 2
5. Validar flujo real de matricula

### Parallel Opportunities

- T003, T006 y T007 pueden trabajarse en paralelo
- En fases posteriores, vistas y semantica visible pueden avanzar junto a modelos si no chocan en archivos
