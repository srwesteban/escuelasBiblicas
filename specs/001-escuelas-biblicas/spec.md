# Feature Specification: Plataforma de Escuelas Biblicas

**Feature Branch**: `001-escuelas-biblicas`  
**Created**: 2026-03-19  
**Status**: In Progress  
**Input**: User description: "Hechos Hub es una plataforma de Escuelas Biblicas con sedes, coordinadores, profesores, estudiantes y matricula manual aprobada por profesor"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registro, solicitud y acceso del estudiante (Priority: P1)

Como estudiante, quiero registrarme, iniciar sesion, ver escuelas disponibles y solicitar matricula para poder ingresar a una Escuela Biblica cuando un profesor apruebe mi solicitud.

**Why this priority**: Sin este flujo no existe ingreso de nuevos estudiantes ni valor academico minimo para la plataforma.

**Independent Test**: Puede probarse creando una cuenta de estudiante, visualizando escuelas, generando una solicitud pendiente y verificando que el alumno no pueda ingresar a la escuela hasta ser aprobado.

**Acceptance Scenarios**:

1. **Given** un visitante sin cuenta, **When** se registra con email y contrasena validos, **Then** el sistema crea su cuenta y permite iniciar sesion.
2. **Given** un estudiante autenticado, **When** visualiza el listado de escuelas, **Then** puede ver todas las escuelas publicadas y sus cupos visibles.
3. **Given** un estudiante autenticado que no esta matriculado, **When** solicita matricula a una escuela, **Then** el sistema registra la solicitud con estado `pendiente`.
4. **Given** un estudiante con solicitud pendiente, **When** intenta ingresar a la escuela, **Then** el sistema niega acceso hasta que exista una matricula aprobada.

---

### User Story 2 - Aprobacion manual de matricula por profesor (Priority: P1)

Como profesor, quiero ver las solicitudes de matricula de mis escuelas, validar manualmente el pago y aceptar o rechazar estudiantes para controlar el acceso real a cada escuela.

**Why this priority**: La aprobacion manual por profesor es la regla de negocio central y define el modelo operativo del sistema.

**Independent Test**: Puede probarse con un profesor asignado a una escuela que revisa una solicitud pendiente, la aprueba, verifica el descuento de cupo y confirma que el estudiante obtiene acceso.

**Acceptance Scenarios**:

1. **Given** un profesor asignado a una escuela, **When** consulta las solicitudes pendientes de esa escuela, **Then** ve solo las solicitudes correspondientes a sus escuelas.
2. **Given** una solicitud pendiente y cupo disponible, **When** el profesor valida manualmente el pago y aprueba la solicitud, **Then** la solicitud cambia a `aprobada`, el estudiante queda matriculado y el cupo se reduce en una unidad.
3. **Given** una solicitud pendiente, **When** el profesor la rechaza, **Then** la solicitud cambia a `rechazada` y el estudiante sigue sin acceso.

---

### User Story 3 - Administracion academica por sede (Priority: P2)

Como coordinador de sede, quiero crear escuelas, definir niveles y grupos, parametrizar cupos y fechas, y asignar profesores para operar academicamente mi sede.

**Why this priority**: Sin estructura academica administrable por sede, los profesores y estudiantes no tendrian una operacion ordenada.

**Independent Test**: Puede probarse creando una sede con un coordinador, una escuela con fechas y cupos, un nivel, un grupo y un profesor asignado.

**Acceptance Scenarios**:

1. **Given** un coordinador autenticado, **When** crea una escuela en su sede, **Then** el sistema guarda nombre, cupo, fechas y relaciones de sede.
2. **Given** una escuela creada, **When** el coordinador crea niveles y grupos, **Then** estos quedan asociados correctamente a la escuela.
3. **Given** una escuela, nivel o grupo y un profesor existente, **When** el coordinador asigna el profesor, **Then** el profesor puede gestionar esa estructura academica.

---

### User Story 4 - Gobierno global por Director (Priority: P3)

Como Director, quiero crear sedes y coordinadores para operar varias sedes dentro de una sola plataforma.

**Why this priority**: Da soporte al crecimiento multi-sede, pero puede implementarse despues del flujo academico principal.

**Independent Test**: Puede probarse creando una sede nueva y un coordinador asociado que luego accede solo a esa sede.

**Acceptance Scenarios**:

1. **Given** un Director autenticado, **When** crea una sede, **Then** la sede queda disponible para uso administrativo.
2. **Given** una sede creada, **When** el Director crea un coordinador de esa sede, **Then** el coordinador queda vinculado a esa sede y con permisos limitados a ella.

---

### User Story 5 - Seguimiento academico del estudiante (Priority: P3)

Como estudiante matriculado, quiero ver mis notas y asistencias para conocer mi progreso dentro de la escuela aprobada.

**Why this priority**: Completa la experiencia academica del alumno, pero depende de la matricula y aprobacion previas.

**Independent Test**: Puede probarse con un estudiante matriculado y registros existentes de notas y asistencia visibles solo para el propio alumno.

**Acceptance Scenarios**:

1. **Given** un estudiante matriculado, **When** ingresa a su escuela aprobada, **Then** puede consultar sus notas registradas.
2. **Given** un estudiante matriculado, **When** consulta su asistencia, **Then** ve solo los registros correspondientes a su matricula.

---

### Edge Cases

- ¿Que pasa si un profesor intenta aprobar una solicitud cuando ya no hay cupos disponibles?
- ¿Que pasa si un estudiante solicita matricula dos veces a la misma escuela y al mismo nivel/grupo?
- ¿Que pasa si un profesor no esta asignado a la escuela pero intenta ver solicitudes?
- ¿Que pasa si una escuela cambia fechas o cupo despues de tener solicitudes pendientes?
- ¿Que pasa si un estudiante fue aprobado en una escuela pero el nivel o grupo cambia?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema MUST permitir que un visitante se registre mediante email y contrasena.
- **FR-002**: El sistema MUST permitir inicio de sesion despues del registro.
- **FR-003**: El sistema MUST mostrar al estudiante el listado de escuelas disponibles.
- **FR-004**: El sistema MUST permitir que un estudiante autenticado solicite matricula a una escuela.
- **FR-005**: El sistema MUST guardar cada solicitud con un estado al menos entre `pendiente`, `aprobada` y `rechazada`.
- **FR-006**: El sistema MUST impedir que un estudiante acceda a una escuela si no tiene matricula aprobada.
- **FR-007**: El sistema MUST permitir que un profesor vea solo las solicitudes de las escuelas que tiene asignadas.
- **FR-008**: El sistema MUST permitir que un profesor apruebe o rechace manualmente una solicitud.
- **FR-009**: El sistema MUST descontar un cupo cuando una solicitud es aprobada.
- **FR-010**: El sistema MUST registrar que la validacion del pago es manual y realizada por el profesor antes de aprobar.
- **FR-011**: El sistema MUST permitir al coordinador crear escuelas dentro de su sede.
- **FR-012**: El sistema MUST permitir parametrizar cupos y fechas de inicio y fin por escuela.
- **FR-013**: El sistema MUST permitir crear niveles y grupos dentro de una escuela.
- **FR-014**: El sistema MUST permitir asignar profesores a escuelas, niveles o grupos segun el diseno final.
- **FR-015**: El sistema MUST permitir al Director crear sedes.
- **FR-016**: El sistema MUST permitir al Director crear coordinadores por sede.
- **FR-017**: El sistema MUST permitir al profesor definir la cantidad de notas a registrar por su escuela o grupo.
- **FR-018**: El sistema MUST permitir al profesor registrar notas de estudiantes matriculados.
- **FR-019**: El sistema MUST permitir al profesor registrar asistencia de estudiantes matriculados.
- **FR-020**: El sistema MUST permitir al estudiante ver solo sus propias notas y asistencias.

### Key Entities *(include if feature involves data)*

- **Sede**: Representa una ubicacion operativa como Hechos Norte o Hechos Centro.
- **Coordinador**: Usuario encargado de la administracion academica de una sede especifica.
- **Escuela**: Unidad academica principal, por ejemplo `Primeros Pasos`.
- **Nivel**: Etapa formativa que vive dentro de una escuela y organiza la progresion academica.
- **Grupo**: Subdivision operativa de una escuela dentro de un nivel.
- **Profesor**: Usuario responsable de administrar escuelas asignadas, solicitudes, notas y asistencia.
- **Estudiante**: Usuario que se registra, solicita matricula y accede a escuelas aprobadas.
- **SolicitudMatricula**: Peticion de ingreso a una escuela antes de la aprobacion manual.
- **Matricula**: Aprobacion formal del estudiante en una escuela, asociada al acceso habilitado.
- **Nota**: Evaluacion registrada por profesor para un estudiante matriculado.
- **Asistencia**: Registro de presencia o ausencia del estudiante matriculado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un estudiante puede completar registro, login y solicitud de matricula en menos de 5 minutos sin ayuda administrativa.
- **SC-002**: Un profesor puede revisar y aprobar una solicitud pendiente en menos de 1 minuto desde su panel.
- **SC-003**: El 100% de estudiantes sin matricula aprobada son bloqueados al intentar entrar a escuelas restringidas.
- **SC-004**: Cada aprobacion de matricula reduce exactamente un cupo disponible y deja trazabilidad del estado final.
