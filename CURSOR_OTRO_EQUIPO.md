# Handoff para otro Cursor / otra máquina (HechosHub)

Lee esto primero para levantar el proyecto y conectar Django a Supabase sin adivinar URLs ni claves.

## 1. Código y rama

```bash
git clone https://github.com/srwesteban/escuelasBiblicas.git
cd escuelasBiblicas
git checkout 001-escuelas-biblicas
git pull
```

(Si el remoto es otro, usa el que corresponda.)

## 2. Python y dependencias

- Python **3.12** (hay `.python-version` en el repo).
- Entorno virtual e instalación:

```bash
python3.12 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Variables de entorno (obligatorio)

1. Copia el ejemplo y edita **solo en tu máquina** (nunca subas `.env` a git; está en `.gitignore`).

```bash
cp .env.example .env
```

2. En `.env` define al menos:
   - `DJANGO_SECRET_KEY` (cualquier string largo en local).
   - `DJANGO_DEBUG=true`
   - `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`

3. **Base de datos Supabase → `DATABASE_URL`**

   - En [Supabase Dashboard](https://supabase.com/dashboard/project/rwajorebhxokoahiqnws) abre **Connect** (o **Project Settings → Database**).
   - Elige **Session pooler** (recomendado en macOS / redes sin IPv6 fiable).
   - Copia la URI completa y pégala como `DATABASE_URL` en `.env`.

   La conexión **directa** `db.<ref>.supabase.co:5432` suele ser **solo IPv6**; si ves `failed to resolve host`, no uses esa: usa la del **Session pooler** (`aws-0-<region>.pooler.supabase.com`, usuario `postgres.<project_ref>`).

4. **Contraseña con caracteres especiales** (`+ * , @`…): codifícala para la URL:

```bash
python3 -c "from urllib.parse import quote; print(quote('TU_PASSWORD_AQUI', safe=''))"
```

Sustituye en `DATABASE_URL` el fragmento de contraseña por el resultado (por ejemplo `7sXdTJ%2B%2A%2CLtgJg-`).

5. **Opcional (API / cliente JS, no es la password de Postgres)**

   - `SUPABASE_URL=https://rwajorebhxokoahiqnws.supabase.co`
   - `SUPABASE_ANON_KEY=` la clave **publishable / anon** del panel (formato `sb_publishable_...` o anon legacy). No sirve como `DATABASE_URL`.

## 4. Comprobar Django

```bash
source .venv/bin/activate
python manage.py check
python manage.py migrate
python manage.py runserver
```

Si la base en Supabase **ya tiene** el esquema y datos migrados, `migrate` debería indicar que no hay cambios pendientes.

## 5. Datos locales de prueba (SQLite)

Si trabajas **sin** `DATABASE_URL` (solo SQLite), puedes sembrar usuarios de demo:

```bash
python manage.py seed_local_data
```

Credenciales de prueba: ver `CREDENCIALES_USUARIOS.md` y comentarios en `seed_local_data`.

## 6. Archivos de referencia en el repo

| Archivo | Uso |
|--------|-----|
| `.env.example` | Plantilla de variables (sin secretos). |
| `hechoshub/db_config.py` | Parsea `DATABASE_URL` y `sslmode` en query string. |
| `hechoshub/settings.py` | Si usas pooler **transaction** en `db.*.supabase.co:6543`, ajusta cursores automáticamente. |

## 7. Proyecto Supabase (referencia)

- **Project ref:** `rwajorebhxokoahiqnws`
- **URL API:** `https://rwajorebhxokoahiqnws.supabase.co`

---

## 8. Si “falla” algo: git pull vs base de datos

### `git pull`

- Si el mensaje es **`Already up to date`**, está bien: no hay commits nuevos en el remoto.
- Si falla el pull, suele ser por:
  - **Cambios locales sin commitear** → `git status`; guarda o haz stash: `git stash -u`, luego `git pull`, luego `git stash pop`.
  - **Rama distinta** → `git branch` y asegúrate de estar en `001-escuelas-biblicas`: `git checkout 001-escuelas-biblicas && git pull`.
  - **HTTPS sin permisos** → GitHub pide token o SSH; configura credenciales o usa `git@github.com:...`.
  - **Conflicto de merge** → Git indica archivos en conflicto; resuélvelos y `git commit`.

### Error al arrancar Django (no es `git pull`)

Mensajes como **`FATAL: Tenant or user not found`** al hacer `runserver` o `migrate` vienen del **pooler de Supabase**, no de Git.

Significa casi siempre que el **`DATABASE_URL` no coincide con tu proyecto**:

1. Abre el dashboard del proyecto → **Connect** → **Session pooler**.
2. Copia la URI **entera** que muestra Supabase (host `aws-0-**REGION**.pooler.supabase.com`, usuario `postgres.**project_ref**`).
3. **No** uses una región copiada de un ejemplo (`us-east-1`, etc.) si no es la que muestra **tu** panel: una región incorrecta produce exactamente `Tenant or user not found`.
4. Vuelve a codificar la contraseña en la URL si tiene caracteres especiales (apartado 3).

Mientras ajustas `.env`, puedes probar solo SQLite comentando o quitando `DATABASE_URL` y usando `DB_ENGINE=sqlite` / `DB_NAME=db.sqlite3` como en `.env.example`.

### Aviso de Homebrew en la terminal (`/opt/homebrew/bin/brew`)

Si aparece `no such file or directory: /opt/homebrew/bin/brew` en macOS Intel, Homebrew suele estar en `/usr/local/bin/brew`. Revisa tu `~/.zprofile` o `~/.zshrc` y corrige la ruta, o instala Homebrew en la ruta que espera el archivo.

---

Si algo falla al conectar, revisa en orden: URI del **Session pooler** (copiada del panel, región correcta), usuario `postgres.<ref>`, password codificada, `sslmode=require` en la URL, y que el proyecto Supabase esté activo.
