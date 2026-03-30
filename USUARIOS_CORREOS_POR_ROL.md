# Usuarios desde la base de datos

Generado: 2026-03-30T04:57:49+00:00
Total usuarios: 24

Actualizar este archivo:

```bash
python manage.py export_usuarios_roles
```

**Rol** = campo `User.role` en `core`. **Perfil Hechos** = `AdminEscuela`, `Profesor` o `Estudiante` si existe.

## `super_admin`

| Correo | Activo | staff | superuser | Perfil Hechos | Módulos (vista) |
|--------|--------|-------|-----------|---------------|-----------------|
| super2@local.test | True | True | True | — | — |
| super1@local.test | True | True | True | — | — |

## `app_admin`

| Correo | Activo | staff | superuser | Perfil Hechos | Módulos (vista) |
|--------|--------|-------|-----------|---------------|-----------------|
| coordinadorpedagogico@local.test | True | True | False | AdminEscuela (Coordinador pedagógico) | hechos |
| coordinadorsedecentro@local.test | True | True | False | AdminEscuela (Coordinador de sede) | hechos |
| pedagogico@local.test | False | True | False | AdminEscuela (Coordinador pedagógico) | hechos |
| zabi@local.test | True | True | False | AdminEscuela (Coordinador pedagógico) | hechos |
| carolviteri@local.test | True | True | False | AdminEscuela (Coordinador académico) | hechos |
| coordinadorsede@local.test | True | True | False | AdminEscuela (Coordinador de sede) | hechos |
| guias.admin2@local.test | True | True | False | — | guias |
| guias.admin1@local.test | True | True | False | — | guias |
| hechos.admin2@local.test | False | True | False | AdminEscuela (Coordinador académico) | hechos |
| hechos.admin1@local.test | False | True | False | AdminEscuela (Coordinador académico) | hechos |

## `user`

| Correo | Activo | staff | superuser | Perfil Hechos | Módulos (vista) |
|--------|--------|-------|-----------|---------------|-----------------|
| profesorhechonorte@local.test | True | False | False | Profesor | — |
| cinco@local.test | True | False | False | Estudiante | hechos |
| cuatro@local.test | True | False | False | Estudiante | hechos |
| estudiantetres@local.test | True | False | False | Estudiante | hechos |
| nuevo@local.test | True | False | False | Estudiante | hechos |
| william@local.test | True | False | False | Profesor | — |
| guias.user2@local.test | True | False | False | — | guias |
| guias.user1@local.test | True | False | False | — | guias |
| estudiante2@local.test | True | False | False | Estudiante | hechos |
| estudiante1@local.test | True | False | False | Estudiante | hechos |
| profesor2@local.test | True | False | False | Profesor | hechos |
| profesor1@local.test | True | False | False | Profesor | hechos |
