# HechosHub

Sistema web (Django) para gestionar **escuelas bíblicas** por sede: matrículas, asistencia, notas, coordinadores y catálogo de formación.

## Requisitos

- Python **3.12+**
- pip / venv
- Git (opcional)

## Arranque rápido (desarrollo local)

### 1. Clonar e instalar

```bash
git clone <url-del-repositorio>
cd escuelasBiblicas

python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Variables de entorno

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Para desarrollo local puedes dejar `DATABASE_URL` vacío: se usa **SQLite** (`db.sqlite3`).

Si usas Postgres (Neon, Supabase, etc.), pon la cadena en `DATABASE_URL` dentro de `.env`.

### 3. Migrar y cargar datos base

```bash
python manage.py migrate

# Catálogo de Formación global (niveles + escuelas plantilla)
python manage.py ensure_programa_global

# Cuentas de prueba + una sede (borra usuarios/sedes previos)
python manage.py reset_datos_prueba --yes
```

### 4. Servidor

```bash
python manage.py runserver
```

Abre: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

El login pide **número de documento** (no correo).

---

## Acceso de prueba

Tras `reset_datos_prueba`, todos usan la misma contraseña:

**Contraseña:** `Prueba2026!`

| Rol | Documento |
|-----|-----------|
| Director | `1000000001` |
| Coordinador de sede | `1000000011` |
| Coordinador académico | `1000000012` |
| Coordinador pedagógico | `1000000013` |
| Coordinador financiero | `1000000014` |
| Coordinador logístico | `1000000015` |
| Profesor | `1000000020` |
| Estudiante | `1000000030` |
| Coordinador (varios roles) | `1000000040` |

El usuario `1000000040` es un coordinador **combinado** (académico + pedagógico + financiero + logístico) en la misma sede de prueba.

---

## Formación global (niveles y escuelas)

La pantalla del director **Formación global** (`/director/programa-escuelas/`) usa plantillas globales:

- `NivelProgramaPlantilla` — niveles (Fundamentos, Sanos y Libres, Equipados, Liderando, Desarrollando llamado, …)
- `EscuelaProgramaPlantilla` — escuelas de cada nivel

Ese catálogo vive en código en `hechos/catalogo_formacion.py` y se carga/actualiza con:

```bash
python manage.py ensure_programa_global
```

**Importante**

- Corre `ensure_programa_global` después de `migrate` en una BD nueva (o al cambiar de base).
- `reset_datos_prueba` **no borra** ese catálogo: solo recrea sedes y usuarios.
- Si editas niveles/escuelas en la UI y quieres que queden en el repo para la próxima BD, actualiza `catalogo_formacion.py` y vuelve a correr el comando.

---

## Qué hace cada rol (resumen)

| Rol | Enfoque |
|-----|---------|
| **Director** | Sedes, Formación global, directorios, estadísticas, admin Django |
| **Coordinador de sede** | Info y equipo de la sede |
| **Académico** | Matrículas, bandeja, directorios de personas |
| **Pedagógico** | Crear / editar escuelas, profesores |
| **Financiero** | Ingresos, eventos, recaudos |
| **Logístico** | Salones, inventario |
| **Profesor** | Sus escuelas, asistencia, notas, ofrendas |
| **Estudiante** | Escuelas, horario, certificados |

---

## Comandos útiles

```bash
python manage.py migrate
python manage.py ensure_programa_global
python manage.py reset_datos_prueba --yes
python manage.py sync_estudiante_documentos   # alinea documento User ↔ perfil
python manage.py check
python manage.py runserver
```

Con Make (macOS/Linux; el Makefile apunta a `.venv`):

```bash
make setup
make migrate
make run
```

---

## Estructura del proyecto

```
hechoshub/     # settings, URLs raíz, config de BD
core/          # usuarios, sedes, director, directorios
hechos/        # escuelas, matrículas, asistencia, notas, coordinadores
ofrendas/      # ofrendas (profesor)
templates/     # HTML
static/        # CSS/JS/imágenes
media/         # archivos locales (si no usas S3)
```

---

## Base de datos y archivos

- **Sin `DATABASE_URL`:** SQLite local.
- **Con `DATABASE_URL`:** Postgres/MySQL según la URL (ver `.env.example`).
- **Archivos subidos:** sin variables `S3_*` → carpeta `media/`. Con `S3_*` completas → storage S3-compatible (útil en hosts con disco efímero). Detalle en `.env.example`.

---

## Producción (mínimo)

1. Completa en `.env` (o en el panel del host): `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`.
2. Si el disco no es persistente, configura también `S3_*`.
3. `migrate` → `ensure_programa_global` → `collectstatic`.
4. Sirve con Gunicorn (hay `Procfile` / `render.yaml` de referencia).

---

**HechosHub** — escuelas bíblicas por sede.
