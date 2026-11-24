import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# En Docker se monta en /config/app.env (ENV_FILE); en desarrollo es backend/.env
ENV_PATH = Path(os.getenv("ENV_FILE") or Path(__file__).resolve().parent.parent / ".env")
load_dotenv(ENV_PATH)


def _bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "si", "sí", "yes", "on")


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://asistencia:asistencia@localhost:5432/asistencia"
)
# ---- ERP IGEA (app.igeaerp.com) ----
ERP_BASE_URL = os.getenv("ERP_BASE_URL", "https://app.igeaerp.com").rstrip("/")
ERP_ENDPOINT = "/source/source_frmAsistenciaPro.php"
ERP_URL = ERP_BASE_URL + ERP_ENDPOINT
# Áreas que se consultan si no se indica una; vacío = una sola consulta con area="" (todas)
ERP_AREAS = [a.strip() for a in os.getenv("ERP_AREAS", "").split(",") if a.strip()]
ERP_TIMEOUT = float(os.getenv("ERP_TIMEOUT", "30"))


def erp_phpsessid() -> str:
    """Lee la cookie de sesión en cada consulta, para poder renovarla en .env sin reiniciar.
    Nunca se envía al frontend ni se escribe en logs."""
    valor = dotenv_values(ENV_PATH).get("ERP_PHPSESSID") or os.getenv("ERP_PHPSESSID", "")
    return (valor or "").strip()


# ---- Inicio de sesión ----
# Clave para firmar los tokens de sesión. Si falta, se genera una al iniciar
# (las sesiones se pierden al reiniciar). Generar con: python -c "import secrets;print(secrets.token_urlsafe(48))"
SECRET_KEY = os.getenv("SECRET_KEY", "")
SESION_HORAS = float(os.getenv("SESION_HORAS", "12"))
# true cuando la web se sirve por HTTPS (la cookie solo viaja cifrada)
COOKIE_SECURE = _bool(os.getenv("COOKIE_SECURE"), False)
# Primer administrador (solo se crea si no hay ningún usuario)
ADMIN_USUARIO = os.getenv("ADMIN_USUARIO", "admin")
ADMIN_PASSWORD_INICIAL = os.getenv("ADMIN_PASSWORD_INICIAL", "")
# Sedes que se crean la primera vez: NOMBRE=ÁREA DEL ERP, separadas por coma
SEDES_INICIALES = os.getenv("SEDES_INICIALES", "CHORRILLOS=SEDE CHORRILLOS,TIZA=SEDE TIZA")

FOTO_BASE_URL = os.getenv("FOTO_BASE_URL", "").rstrip("/")
SYNC_ACTIVO = _bool(os.getenv("SYNC_ACTIVO"), True)
SYNC_HORAS = [h.strip() for h in os.getenv("SYNC_HORAS", "08:30,13:00,18:30").split(",") if h.strip()]
TZ_LOCAL = os.getenv("TZ_LOCAL", "America/Lima")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
