from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------- Asistencias ----------------
class AsistenciaCreate(BaseModel):
    """Registro manual. La sede la fija el servidor (la del usuario, o sede_id si es ADMIN)."""
    fecha: date
    trabajador_nombre: str = Field(min_length=1)
    trabajador_dni: str | None = None
    trabajador_id: int | None = None
    estado: str | None = "PUNTUAL"
    hora_entrada: time | None = None
    hora_salida: time | None = None
    motivo_ausencia: str | None = None
    observaciones: str | None = None
    sede_id: int | None = None


class AsistenciaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int | None
    fecha: date
    trabajador_nombre: str
    trabajador_dni: str | None
    trabajador_id: int | None
    estado: str | None
    hora_entrada: time | None
    hora_salida: time | None
    motivo_ausencia: str | None
    motivo_salida: str | None
    autorizado_por: str | None
    observaciones: str | None
    foto_entrada: str | None
    foto_salida: str | None
    lat_entrada: float | None
    lng_entrada: float | None
    es_licencia: int | None
    licencia_tipo: str | None
    tienda_id: int | None
    tienda_nombre: str | None
    cliente_nombre: str | None
    area: str | None
    origen: str
    actualizado: datetime | None


class ImportacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    momento: datetime
    origen: str
    fecha_consultada: date | None
    total: int
    nuevos: int
    actualizados: int
    ok: bool
    mensaje: str | None


class ResultadoImportacion(BaseModel):
    total: int
    nuevos: int
    actualizados: int
    omitidos: int
    errores: list[str] = []


# ---------------- Sedes ----------------
class SedeIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=100)
    area_erp: str = Field(min_length=2, max_length=200, description="Valor del campo 'area' en el ERP")
    activo: bool = True

    @field_validator("nombre", "area_erp")
    @classmethod
    def mayus(cls, v: str) -> str:
        return " ".join(v.split()).upper()


class SedeOut(SedeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------------- Usuarios y sesión ----------------
def _validar_password(v: str | None) -> str | None:
    if v is None:
        return v
    if len(v) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    if len(v.encode("utf-8")) > 72:
        raise ValueError("La contraseña es demasiado larga (máx. 72 bytes)")
    if v.isdigit() or v.isalpha():
        raise ValueError("La contraseña debe combinar letras y números")
    return v


class LoginIn(BaseModel):
    usuario: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class CambioPasswordIn(BaseModel):
    actual: str
    nueva: str

    @field_validator("nueva")
    @classmethod
    def _v(cls, v: str) -> str:
        return _validar_password(v)


class UsuarioBase(BaseModel):
    usuario: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    nombre: str = Field(min_length=1, max_length=100)
    apellido: str = Field(min_length=1, max_length=100)
    dni: str | None = Field(None, pattern=r"^\d{8}$", description="8 dígitos")
    rol: str = Field("USUARIO", pattern=r"^(ADMIN|USUARIO)$")
    sede_id: int | None = None
    activo: bool = True

    @field_validator("usuario")
    @classmethod
    def minus(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("dni", mode="before")
    @classmethod
    def dni_vacio(cls, v):
        return v or None


class UsuarioCreate(UsuarioBase):
    password: str
    @field_validator("password")
    @classmethod
    def _v(cls, v: str) -> str:
        return _validar_password(v)


class UsuarioUpdate(UsuarioBase):
    password: str | None = None  # vacío = no cambiar
    @field_validator("password", mode="before")
    @classmethod
    def _v(cls, v: str | None) -> str | None:
        return _validar_password(v or None)


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario: str
    nombre: str
    apellido: str
    dni: str | None
    rol: str
    sede_id: int | None
    sede: SedeOut | None
    activo: bool
    debe_cambiar_password: bool
    ultimo_acceso: datetime | None
