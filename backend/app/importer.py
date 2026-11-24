"""Convierte la respuesta del GET en filas de la tabla asistencias (upsert por id externo)."""
import time
from datetime import date, datetime
from datetime import time as dtime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config
from .models import Asistencia, Importacion
from .schemas import ResultadoImportacion


def _txt(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _num(v: Any) -> float | None:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _int(v: Any) -> int | None:
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _hora(v: Any) -> dtime | None:
    s = _txt(v)
    if not s:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def _fecha(v: Any) -> date | None:
    s = _txt(v)
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def extraer_lista(payload: Any) -> list[dict]:
    """Acepta {"ok":true,"asistencias":[...]}, una lista directa o un único objeto."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("asistencias"), list):
            return [x for x in payload["asistencias"] if isinstance(x, dict)]
        if "trabajador_nombre" in payload:
            return [payload]
    raise ValueError("El JSON no tiene el formato esperado (se busca la lista 'asistencias').")


def mapear(item: dict) -> dict:
    return {
        "external_id": _int(item.get("id")),
        "fecha": _fecha(item.get("fecha")),
        "trabajador_id": _int(item.get("trabajador_id")),
        "trabajador_nombre": _txt(item.get("trabajador_nombre")) or "(sin nombre)",
        "trabajador_dni": _txt(item.get("trabajador_dni")),
        "estado": _txt(item.get("estado")),
        "hora_entrada": _hora(item.get("hora_entrada")),
        "hora_salida": _hora(item.get("hora_salida")),
        "motivo_ausencia": _txt(item.get("motivo_ausencia")),
        "motivo_salida": _txt(item.get("motivo_salida")),
        "autorizado_por": _txt(item.get("autorizado_por")),
        "observaciones": _txt(item.get("observaciones")),
        "foto_entrada": _txt(item.get("foto_entrada")),
        "foto_salida": _txt(item.get("foto_salida")),
        "lat_entrada": _num(item.get("lat_entrada")),
        "lng_entrada": _num(item.get("lng_entrada")),
        "lat_salida": _num(item.get("lat_salida")),
        "lng_salida": _num(item.get("lng_salida")),
        "es_licencia": _int(item.get("es_licencia")) or 0,
        "licencia_tipo": _txt(item.get("licencia_tipo")),
        "tienda_id": _int(item.get("tienda_id")),
        "tienda_nombre": _txt(item.get("tienda_nombre")),
        "cliente_nombre": _txt(item.get("cliente_nombre")),
        "area": _txt(item.get("area")),
        "raw": item,
    }


def importar(db: Session, payload: Any, origen: str, fecha_consultada: date | None = None,
             solo_area: str | None = None) -> ResultadoImportacion:
    """origen: 'JSON', 'API' o 'API-AUTO'. Si el registro ya existe (mismo id externo) se actualiza.
    solo_area: si se indica, se omiten los registros de otras áreas (usuarios de una sede)."""
    items = extraer_lista(payload)
    origen_fila = "API" if origen.startswith("API") else origen
    nuevos = actualizados = omitidos = 0
    errores: list[str] = []

    for n, item in enumerate(items, start=1):
        datos = mapear(item)
        if datos["fecha"] is None:
            omitidos += 1
            errores.append(f"Registro {n}: sin fecha válida")
            continue
        if solo_area and (datos["area"] or "").upper() != solo_area.upper():
            omitidos += 1
            errores.append(f"Registro {n}: es de otra sede ({datos['area'] or 'sin área'})")
            continue
        existente = None
        if datos["external_id"] is not None:
            existente = db.scalar(select(Asistencia).where(Asistencia.external_id == datos["external_id"]))
        if existente and solo_area and (existente.area or "").upper() != solo_area.upper():
            omitidos += 1
            errores.append(f"Registro {n}: pertenece a otra sede")
            continue
        if existente:
            for k, v in datos.items():
                setattr(existente, k, v)
            existente.origen = origen_fila
            actualizados += 1
        else:
            db.add(Asistencia(**datos, origen=origen_fila))
            nuevos += 1
        db.flush()

    res = ResultadoImportacion(
        total=len(items), nuevos=nuevos, actualizados=actualizados, omitidos=omitidos, errores=errores[:20]
    )
    db.add(Importacion(origen=origen, fecha_consultada=fecha_consultada, total=res.total,
                       nuevos=nuevos, actualizados=actualizados, ok=True,
                       mensaje="; ".join(errores[:5]) or None))
    db.commit()
    return res


# ---------------- Consulta al ERP IGEA ----------------
class ErpError(RuntimeError):
    """Error al consultar el ERP (conexión, HTTP o respuesta inválida)."""


class ErpSesionExpirada(ErpError):
    """La cookie PHPSESSID falta, venció o fue rechazada."""


MSG_SESION = ("La sesión del ERP no es válida o expiró. Inicia sesión en app.igeaerp.com, "
              "copia la cookie PHPSESSID y actualiza ERP_PHPSESSID en backend/.env.")


def _parece_login(texto: str) -> bool:
    t = texto[:4000].lower()
    return "<html" in t or "<!doctype" in t or "login" in t or "iniciar sesi" in t


def consultar_erp(fecha_inicio: date, fecha_fin: date | None = None, area: str = "",
                  trabajador_id: int | str | None = None, estado: str | None = None,
                  cliente_id: int | str | None = None) -> dict:
    """GET a source_frmAsistenciaPro.php?op=listar. Devuelve el JSON ({"ok":true,"asistencias":[...]})."""
    sesion = config.erp_phpsessid()
    if not sesion:
        raise ErpSesionExpirada("Falta ERP_PHPSESSID en backend/.env. " + MSG_SESION)

    params = {
        "op": "listar",
        "fecha_inicio": fecha_inicio.isoformat(),
        "fecha_fin": (fecha_fin or fecha_inicio).isoformat(),
        "trabajador_id": "" if trabajador_id in (None, "") else str(trabajador_id),
        "estado": estado or "",
        "cliente_id": "" if cliente_id in (None, "") else str(cliente_id),
        "area": area or "",
        "_": str(int(time.time() * 1000)),  # evita caché, igual que jQuery
    }
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "es-419,es;q=0.9",
        "Referer": f"{config.ERP_BASE_URL}/main.php",
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
    }
    # La cookie viaja solo en esta petición servidor→ERP; no se registra en logs.
    try:
        with httpx.Client(timeout=config.ERP_TIMEOUT, follow_redirects=False) as c:
            r = c.get(config.ERP_URL, params=params, headers=headers, cookies={"PHPSESSID": sesion})
    except httpx.TimeoutException:
        raise ErpError(f"El ERP no respondió en {config.ERP_TIMEOUT:.0f} s.")
    except httpx.HTTPError as e:
        raise ErpError(f"No se pudo conectar con el ERP: {type(e).__name__}")

    if r.is_redirect or r.status_code in (401, 403, 419, 440):
        raise ErpSesionExpirada(MSG_SESION)
    if r.status_code >= 400:
        raise ErpError(f"El ERP respondió HTTP {r.status_code}.")

    try:
        data = r.json()
    except ValueError:
        if _parece_login(r.text):
            raise ErpSesionExpirada(MSG_SESION)
        raise ErpError("El ERP devolvió una respuesta que no es JSON.")

    if not isinstance(data, dict):
        raise ErpError("Respuesta inesperada del ERP (no es un objeto JSON).")
    if data.get("ok") is not True:
        detalle = str(data.get("mensaje") or data.get("msg") or data.get("error") or "")
        if "sesi" in detalle.lower() or "login" in detalle.lower():
            raise ErpSesionExpirada(MSG_SESION)
        raise ErpError(f"El ERP respondió ok={data.get('ok')!r}. {detalle}".strip())
    if not isinstance(data.get("asistencias"), list):
        raise ErpError("La respuesta del ERP no trae la lista 'asistencias'.")
    return data


def sincronizar(db: Session, fecha_inicio: date, fecha_fin: date | None = None, area: str = "",
                origen: str = "API", **filtros) -> ResultadoImportacion:
    """Consulta el ERP y guarda el resultado con importar(). Los fallos quedan en el historial."""
    try:
        data = consultar_erp(fecha_inicio, fecha_fin, area, **filtros)
    except ErpError as e:
        db.rollback()
        rango = f"{fecha_inicio}" + (f" a {fecha_fin}" if fecha_fin and fecha_fin != fecha_inicio else "")
        db.add(Importacion(origen=origen, fecha_consultada=fecha_inicio, ok=False,
                           mensaje=f"[{area or 'todas'} · {rango}] {e}"[:1000]))
        db.commit()
        raise
    return importar(db, data, origen, fecha_inicio)
