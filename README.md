# Asistencia por sedes

React + Vite (frontend) · FastAPI (backend) · PostgreSQL.

Pantallas:
1. **Asistencias**: por día (◀ ▶ / Hoy), filtro por sede, estado y búsqueda por nombre o DNI. Tarjetas con el total por estado, hora de entrada y salida, y detalle con foto y ubicación.
2. **Registro manual**: formulario que autocompleta al trabajador (DNI, sede) con los que ya están en la base. También sirve para editar.
3. **Cargar JSON**: pegar la respuesta del GET o subir el archivo `.json`/`.txt`.
4. **Consulta automática**: botón "Consultar y cargar" (un día o un rango) e historial de cargas. Además, el backend consulta solo el día actual a las horas de `SYNC_HORAS`.

Los registros se identifican por el `id` del sistema externo: volver a cargar el mismo día **actualiza** (por ejemplo, la hora de salida) y no duplica.

## Inicio de sesión y sedes

- Contraseñas guardadas con **bcrypt** (hash con sal; nunca en texto). La sesión es un token firmado (`SECRET_KEY`) en una cookie `httpOnly` que JavaScript no puede leer; dura `SESION_HORAS`.
- Roles: **Administrador** (todas las sedes; gestiona usuarios y sedes en "Usuarios y sedes") y **Usuario de sede** (solo ve, registra, importa y consulta al ERP su propia sede).
- Cada sede tiene su **área en el ERP** (ej. `SEDE CHORRILLOS`), que debe coincidir con el campo `area` de IGEA.
- Primer ingreso: usuario `admin` con `ADMIN_PASSWORD_INICIAL` (o la contraseña temporal que aparece en el log del backend). Se pide cambiarla al entrar.
- 5 intentos fallidos bloquean ese usuario 5 minutos. Cambiar la contraseña o desactivar un usuario cierra sus sesiones.
- Para que la contraseña también viaje cifrada por la red, sirve la web por **HTTPS** (proxy inverso) y pon `COOKIE_SECURE=true`.

## 1. Base de datos

Con Docker: `docker compose up -d`.
Sin Docker: instala PostgreSQL y crea la base:
```sql
CREATE USER asistencia WITH PASSWORD 'asistencia';
CREATE DATABASE asistencia OWNER asistencia;
```
Las tablas se crean solas al iniciar el backend.

## 2. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # y edita ASISTENCIA_API_URL, cabeceras, horas
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```
Documentación de la API: http://localhost:8000/docs

Variables principales en `backend/.env`:
| Variable | Uso |
|---|---|
| `DATABASE_URL` | Conexión a PostgreSQL |
| `ERP_BASE_URL` | `https://app.igeaerp.com` (consulta `source/source_frmAsistenciaPro.php?op=listar`) |
| `ERP_AREAS` | Áreas a consultar, separadas por coma (ej. `SEDE CHORRILLOS`); vacío = todas |
| `ERP_PHPSESSID` | Cookie de sesión del ERP. **Secreta**; se relee en cada consulta, al vencer solo se reemplaza |
| `FOTO_BASE_URL` | Dominio para mostrar `foto_entrada` (viene como ruta relativa) |
| `SYNC_ACTIVO`, `SYNC_HORAS` | Carga automática diaria, p. ej. `08:30,09:30,13:00,18:30` |

> Cuando la sesión del ERP vence, la consulta responde "La sesión del ERP no es válida o expiró": entra a app.igeaerp.com, copia la cookie `PHPSESSID` (F12 → Aplicación → Cookies) y pégala en `ERP_PHPSESSID`.
>
> Si corres uvicorn con varios workers, la carga programada se ejecuta una vez por worker. Usa 1 worker.

## 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```
Abre http://localhost:5173 (Vite redirige `/api` al backend en el puerto 8000).
Para producción: `npm run build` y sirve `frontend/dist`; si el backend está en otro dominio, define `VITE_API_URL` al compilar y agrégalo a `CORS_ORIGINS`.

## Despliegue en Ubuntu Server con Docker (puerto 8001)

Dos contenedores: `app` (FastAPI + frontend compilado, en el puerto **8001**) y `db` (PostgreSQL 16, interno y sin puerto expuesto).

1. Instalar Docker en el servidor (una sola vez):
   ```bash
   curl -fsSL https://get.docker.com | sudo sh
   sudo usermod -aG docker $USER   # cerrar sesión y volver a entrar
   ```
2. Copiar el proyecto al servidor (sin `node_modules`, `.venv` ni `dist`), por ejemplo desde Windows:
   ```powershell
   scp -r Dockerfile .dockerignore docker-compose.yml backend frontend config usuario@IP-SERVIDOR:~/asistencia-sedes/
   ```
   (o con `git clone` si el proyecto está en un repositorio).
3. Configurar en el servidor:
   ```bash
   cd ~/asistencia-sedes
   cp config/app.env.example config/app.env
   nano config/app.env      # clave de PostgreSQL (en los 2 lugares) y ERP_PHPSESSID
   chmod 600 config/app.env
   ```
4. Levantar:
   ```bash
   docker compose up -d --build
   docker compose logs -f app      # debe decir "Uvicorn running on http://0.0.0.0:8001"
   ```
5. Abrir el puerto si el servidor usa ufw: `sudo ufw allow 8001/tcp`
6. Entrar desde cualquier PC de la red: `http://IP-SERVIDOR:8001` (API: `/docs`).

Operación:
| Tarea | Comando |
|---|---|
| Renovar la sesión del ERP | editar `ERP_PHPSESSID` en `config/app.env` (no requiere reinicio) |
| Cambiar otras variables | editar `config/app.env` y `docker compose up -d` |
| Actualizar el código | copiar los cambios y `docker compose up -d --build` |
| Ver logs | `docker compose logs -f app` |
| Respaldo de la BD | `docker compose exec db pg_dump -U asistencia asistencia > respaldo_$(date +%F).sql` |
| Restaurar respaldo | `docker compose exec -T db psql -U asistencia asistencia < respaldo.sql` |

Los datos quedan en el volumen `pgdata`; `docker compose down` no los borra (`down -v` sí).
