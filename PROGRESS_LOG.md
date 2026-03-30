# Progress Log

## Estado actual (sesion)

### 1) Coordinador de sede - Escuelas
- Se agrego filtro en tiempo real en `core/coordinador_sede_escuelas.html` por:
  - nombre
  - anio (fecha de referencia)
  - ciclo
  - grupo
- Incluye contador visible y mensaje de "sin resultados".

### 2) Edicion de escuela
- Se corrigio error por plantilla duplicada en `core/coordinador_sede_escuela_form.html`.
- Resultado: la ruta de editar escuela vuelve a renderizar correctamente.

### 3) Rol coordinador pedagogico (Hechos)
- Se simplifico UX para enfoque en profesores.
- Se ajustaron permisos y navegacion para evitar dependencia de `hechos/dashboard` en este rol.
- `hechos/dashboard` para pedagogico redirige a `hechos/profesores/`.

### 4) Profesores (Hechos)
- Se rediseno `hechos/profesores/` con estilo mas claro y orientado a operacion.
- Se corrigieron inconsistencias de datos/consultas en vista de profesores.
- Alta de profesor:
  - se elimino campo username manual
  - username ahora se genera automaticamente desde email
  - se agrego campo foto con vista previa minimalista
  - se elimino bloque/campos solicitados (especialidad, experiencia, biografia) del alta
  - se desactivo autocompletado del formulario cuando fue pedido

### 5) Detalle de profesor
- Se creo plantilla faltante `hechos/detalle_profesor.html` (resolviendo `TemplateDoesNotExist`).
- Luego se simplifico quitando especialidad, experiencia y biografia de esa vista.

### 6) Landing inicio
- En `core/inicio.html` se cambio texto "Matricularse" por "Registrase" (segun solicitud literal).

### 7) Signup de cuentas
- Se rehizo `account/signup.html` como formulario unico y completo (sin pasos).
- Se agregaron campos de persona e identificacion al signup via `StudentSignupForm`.
- Se incluyeron etiquetas visuales de obligatorio/opcional con asteriscos y "(Opcional)".
- Cambios de copy: "Celular" y "Celular de emergencia".

## Migraciones nuevas

- `hechos/migrations/0015_estudiante_documento.py`
  - agrega `tipo_documento`
  - agrega `numero_documento`

## Pendientes recomendados

- Ejecutar migraciones:
  - `python manage.py migrate`
- Probar flujo completo:
  - registro en `/accounts/signup/`
  - login
  - redireccion segun rol pedagogico
  - CRUD de profesores

