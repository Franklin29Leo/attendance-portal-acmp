from datetime import date, datetime, time

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Asistencia(Base):
    __tablename__ = "asistencias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # id que trae el sistema externo; NULL en los registros manuales
    external_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)
    fecha: Mapped[date] = mapped_column(Date, index=True)
    trabajador_id: Mapped[int | None] = mapped_column(Integer)
    trabajador_nombre: Mapped[str] = mapped_column(String(200))
    trabajador_dni: Mapped[str | None] = mapped_column(String(20), index=True)
    estado: Mapped[str | None] = mapped_column(String(40))
    hora_entrada: Mapped[time | None] = mapped_column(Time)
    hora_salida: Mapped[time | None] = mapped_column(Time)
    motivo_ausencia: Mapped[str | None] = mapped_column(Text)
    motivo_salida: Mapped[str | None] = mapped_column(Text)
    autorizado_por: Mapped[str | None] = mapped_column(String(200))
    observaciones: Mapped[str | None] = mapped_column(Text)
    foto_entrada: Mapped[str | None] = mapped_column(String(500))
    foto_salida: Mapped[str | None] = mapped_column(String(500))
    lat_entrada: Mapped[float | None] = mapped_column(Float)
    lng_entrada: Mapped[float | None] = mapped_column(Float)
    lat_salida: Mapped[float | None] = mapped_column(Float)
    lng_salida: Mapped[float | None] = mapped_column(Float)
    es_licencia: Mapped[int] = mapped_column(Integer, default=0)
    licencia_tipo: Mapped[str | None] = mapped_column(String(100))
    tienda_id: Mapped[int | None] = mapped_column(Integer)
    tienda_nombre: Mapped[str | None] = mapped_column(String(200), index=True)
    cliente_nombre: Mapped[str | None] = mapped_column(String(200))
    area: Mapped[str | None] = mapped_column(String(200))
    origen: Mapped[str] = mapped_column(String(20), default="MANUAL")  # API | JSON | MANUAL
    raw: Mapped[dict | None] = mapped_column(JSON)
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Importacion(Base):
    __tablename__ = "importaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    origen: Mapped[str] = mapped_column(String(20))  # API | API-AUTO | JSON
    fecha_consultada: Mapped[date | None] = mapped_column(Date)
    total: Mapped[int] = mapped_column(Integer, default=0)
    nuevos: Mapped[int] = mapped_column(Integer, default=0)
    actualizados: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(default=True)
    mensaje: Mapped[str | None] = mapped_column(Text)
