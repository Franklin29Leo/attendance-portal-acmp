from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class AsistenciaBase(BaseModel):
    fecha: date
    trabajador_nombre: str = Field(min_length=1)
    trabajador_dni: str | None = None
    trabajador_id: int | None = None
    estado: str | None = "PUNTUAL"
    hora_entrada: time | None = None
    hora_salida: time | None = None
    motivo_ausencia: str | None = None
    observaciones: str | None = None
    tienda_nombre: str | None = None
    area: str | None = None


class AsistenciaCreate(AsistenciaBase):
    pass


class AsistenciaOut(AsistenciaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: int | None
    motivo_salida: str | None
    autorizado_por: str | None
    foto_entrada: str | None
    foto_salida: str | None
    lat_entrada: float | None
    lng_entrada: float | None
    es_licencia: int | None
    licencia_tipo: str | None
    tienda_id: int | None
    cliente_nombre: str | None
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
