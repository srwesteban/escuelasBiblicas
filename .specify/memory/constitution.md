# Hechos Hub Constitution

## Core Principles

### I. Domain-First Semantics
Every change MUST preserve the official language of the platform. The visible product name is `Hechos Hub`, the academic area is `Escuelas Biblicas`, `Registrarse` means account creation, `Iniciar sesion` means access, `Solicitar matricula` means requesting entry, and `Matricular` means the professor's manual approval. If a technical term conflicts with the business meaning, business meaning wins.

### II. Strict Role Separation
Permissions and flows MUST respect the declared responsibilities of `adminDirector`, `coordinador`, `profesor`, and `estudiante`. Features may not blur these roles for convenience. The professor validates payment manually and approves enrollment; the coordinator administers sede-level structure; the adminDirector governs the full platform.

### III. Manual Enrollment Workflow Is Canonical
Student access to a school MUST never be automatic. The canonical flow is: student registers, student requests enrollment, professor validates payment manually, professor approves or rejects, and only approval grants access and consumes a slot. Any future automation must explicitly state how it preserves this rule.

### IV. Modular Django Architecture With Low Duplication
The repository MUST remain a clear Django modular application. `core` owns authentication, users, roles, and shared platform concerns. `hechos` owns the Escuelas Biblicas academic domain. Legacy or duplicate flows should be reduced, not expanded. New features should favor reuse and semantic clarity over parallel implementations.

### V. Simplicity, Performance, and AI-Friendly Structure
The codebase MUST remain easy to navigate for humans and AI agents. Prefer explicit naming, thin views, coherent models, low duplication, and predictable file placement. Avoid premature complexity, unnecessary abstractions, and hidden behavior. Development should keep local execution fast and configuration easy to inspect.

## Technical and Product Constraints

- Primary stack: Django web application with server-rendered templates.
- Primary development database: local SQLite; database configuration must remain swappable for future environments.
- Authentication baseline: email-based sign-up and login.
- Public pages, authentication views, and internal academic flows should remain semantically separated.
- Manual payment validation is in scope; online payments are out of scope unless explicitly specified in a future feature.
- User-facing terminology must be reviewed when old concepts like `curso` or `ruta` conflict with the new academic domain.

## Workflow and Quality Gates

- Each significant feature MUST start in Spec Kit with `constitution`, `specify`, `plan`, and `tasks` artifacts before implementation.
- Specs MUST include user stories, business rules, acceptance scenarios, and the key entities involved.
- Plans MUST document how the feature maps onto the current Django modules and identify any legacy conflicts before coding.
- Tasks MUST be grouped by user story so the MVP can be implemented incrementally.
- Business-critical flows such as enrollment approval, role permissions, attendance, and grading SHOULD have test coverage before the feature is considered complete.

## Governance

This constitution overrides ad hoc practices when there is conflict. Any change to role behavior, business terminology, or enrollment rules requires updating the relevant Spec Kit artifacts first. Complexity must be justified in the plan. Features that violate these principles must document why the simpler compliant alternative was rejected.

**Version**: 1.0.0 | **Ratified**: 2026-03-19 | **Last Amended**: 2026-03-19
