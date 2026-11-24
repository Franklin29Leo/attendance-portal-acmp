import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import Body, Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import config
from .database import Base, SessionLocal, engine, get_db
from .importer import ErpError, ErpSesionExpirada, importar, sincronizar
from .models import Asistencia, Importacion
from .schemas import AsistenciaCreate, AsistenciaOut, ImportacionOut, ResultadoImportacion

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("asistencia")
TZ = ZoneInfo(config.TZ_LOCAL)
scheduler = BackgroundScheduler(timezone=TZ)


def hoy() -> date:
    return datetime.now(TZ).date()


def tarea_automatica():
    """Consulta al ERP el día actual, una vez por cada área de ERP_AREAS (o todas si está vacío)."""
    db = SessionLocal()
    try:
        for area in config.ERP_AREAS or [""]:
            try:
                r = sincronizar(db, hoy(), area=area, origen="API-AUTO")
                log.info("Carga automática [%s]: %s registros, %s nuevos, %s actualizados",
                         area or "todas", r.total, r.nuevos, r.actualizados)
            except ErpError as e:
                log.error("Carga automática [%s] falló: %s", area or "todas", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if config.SYNC_ACTIVO:
        for h in config.SYNC_HORAS:
            hh, mm = h.split(":")
            scheduler.add_job(tarea_automatica, CronTrigger(hour=int(hh), minute=int(mm), timezone=TZ),
                              id=f"sync-{h}", replace_existing=True)
        scheduler.start()
        log.info("Carga automática programada a las %s", ", ".join(config.SYNC_HORAS))
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Asistencia por sedes", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


# ---------- Consulta ----------
@app.get("/api/asistencias", response_model=list[AsistenciaOut])
def listar(
    fecha: date | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    sede: str | None = None,
    estado: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Asistencia)
    if fecha:
        stmt = stmt.where(Asistencia.fecha == fecha)
    if desde:
        stmt = stmt.where(Asistencia.fecha >= desde)
    if hasta:
        stmt = stmt.where(Asistencia.fecha <= hasta)
    if sede:
        stmt = stmt.where(Asistencia.tienda_nombre == sede)
    if estado:
        stmt = stmt.where(Asistencia.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Asistencia.trabajador_nombre.ilike(like), Asistencia.trabajador_dni.ilike(like)))
    stmt = stmt.order_by(Asistencia.fecha.desc(), Asistencia.tienda_nombre,
                         Asistencia.hora_entrada.asc().nulls_last(), Asistencia.trabajador_nombre)
    return db.scalars(stmt.limit(5000)).all()


@app.get("/api/resumen")
def resumen(fecha: date | None = None, sede: str | None = None, db: Session = Depends(get_db)):
    fecha = fecha or hoy()
    stmt = select(Asistencia.estado, func.count()).where(Asistencia.fecha == fecha)
    if sede:
        stmt = stmt.where(Asistencia.tienda_nombre == sede)
    filas = db.execute(stmt.group_by(Asistencia.estado)).all()
    por_estado = {(e or "SIN ESTADO"): n for e, n in filas}
    return {"fecha": fecha, "total": sum(por_estado.values()), "por_estado": por_estado}


@app.get("/api/sedes", response_model=list[str])
def sedes(db: Session = Depends(get_db)):
    return [s for s in db.scalars(select(Asistencia.tienda_nombre).distinct().order_by(Asistencia.tienda_nombre)) if s]


@app.get("/api/estados", response_model=list[str])
def estados(db: Session = Depends(get_db)):
    base = {"PUNTUAL", "TARDANZA", "FALTA", "LICENCIA", "VACACIONES", "PERMISO"}
    base |= {e for e in db.scalars(select(Asistencia.estado).distinct()) if e}
    return sorted(base)


@app.get("/api/trabajadores")
def trabajadores(db: Session = Depends(get_db)):
    """Lista única de trabajadores ya vistos (para autocompletar el registro manual)."""
    filas = db.execute(
        select(Asistencia.trabajador_dni, Asistencia.trabajador_nombre, Asistencia.trabajador_id,
               Asistencia.tienda_nombre, Asistencia.area)
        .order_by(Asistencia.fecha.desc())
    ).all()
    vistos: dict[str, dict] = {}
    for dni, nombre, tid, sede, area in filas:
        clave = dni or nombre
        if clave not in vistos:
            vistos[clave] = {"dni": dni, "nombre": nombre, "trabajador_id": tid, "sede": sede, "area": area}
    return sorted(vistos.values(), key=lambda x: x["nombre"] or "")


# ---------- Registro manual ----------
@app.post("/api/asistencias", response_model=AsistenciaOut, status_code=201)
def crear(datos: AsistenciaCreate, db: Session = Depends(get_db)):
    a = Asistencia(**datos.model_dump(), origen="MANUAL")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@app.put("/api/asistencias/{aid}", response_model=AsistenciaOut)
def editar(aid: int, datos: AsistenciaCreate, db: Session = Depends(get_db)):
    a = db.get(Asistencia, aid)
    if not a:
        raise HTTPException(404, "No existe")
    for k, v in datos.model_dump().items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return a


@app.delete("/api/asistencias/{aid}", status_code=204)
def borrar(aid: int, db: Session = Depends(get_db)):
    a = db.get(Asistencia, aid)
    if not a:
        raise HTTPException(404, "No existe")
    db.delete(a)
    db.commit()


# ---------- Carga manual de JSON ----------
@app.post("/api/importar/json", response_model=ResultadoImportacion)
def importar_json(payload: dict | list = Body(...), db: Session = Depends(get_db)):
    try:
        return importar(db, payload, "JSON")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/importar/archivo", response_model=ResultadoImportacion)
async def importar_archivo(archivo: UploadFile = File(...), db: Session = Depends(get_db)):
    contenido = (await archivo.read()).decode("utf-8-sig")
    try:
        return importar(db, json.loads(contenido), "JSON")
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"El archivo no es un JSON válido: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- Consulta al ERP (manual o programada) ----------
@app.post("/api/importar/consulta", response_model=ResultadoImportacion)
def importar_consulta(
    fecha: date | None = Query(None, description="fecha_inicio; por defecto hoy"),
    hasta: date | None = Query(None, description="fecha_fin; por defecto igual a fecha"),
    area: str | None = Query(None, description="Área del ERP (ej. SEDE CHORRILLOS); por defecto ERP_AREAS"),
    estado: str | None = Query(None, description="Filtro estado del ERP (opcional)"),
    trabajador_id: int | None = Query(None, description="Filtro trabajador_id del ERP (opcional)"),
    cliente_id: int | None = Query(None, description="Filtro cliente_id del ERP (opcional)"),
    db: Session = Depends(get_db),
):
    inicio = fecha or hoy()
    fin = hasta or inicio
    if fin < inicio or (fin - inicio).days > 62:
        raise HTTPException(400, "Rango inválido (máximo 62 días)")
    areas = [area] if area is not None else (config.ERP_AREAS or [""])
    total = ResultadoImportacion(total=0, nuevos=0, actualizados=0, omitidos=0)
    for a in areas:
        try:
            r = sincronizar(db, inicio, fin, area=a, estado=estado,
                            trabajador_id=trabajador_id, cliente_id=cliente_id)
        except ErpSesionExpirada as e:
            raise HTTPException(401, str(e))
        except ErpError as e:
            raise HTTPException(502, f"Error consultando el ERP ({a or 'todas las áreas'}): {e}")
        total.total += r.total
        total.nuevos += r.nuevos
        total.actualizados += r.actualizados
        total.omitidos += r.omitidos
        total.errores += r.errores
    return total


@app.get("/api/importaciones", response_model=list[ImportacionOut])
def importaciones(db: Session = Depends(get_db)):
    return db.scalars(select(Importacion).order_by(Importacion.id.desc()).limit(30)).all()


@app.get("/api/config")
def ver_config():
    proximas = []
    if scheduler.running:
        proximas = sorted(j.next_run_time.isoformat() for j in scheduler.get_jobs() if j.next_run_time)
    return {
        "api_configurada": True,
        "api_url": config.ERP_URL,
        "erp_areas": config.ERP_AREAS,
        "sesion_configurada": bool(config.erp_phpsessid()),  # solo si existe; nunca el valor
        "sync_activo": scheduler.running,
        "sync_horas": config.SYNC_HORAS,
        "proximas": proximas,
        "foto_base_url": config.FOTO_BASE_URL,
        "zona": config.TZ_LOCAL,
    }


# ---------- Frontend compilado (solo en producción / Docker) ----------
# Si existe la carpeta con el build de Vite, la sirve en la misma app y puerto que la API.
# En desarrollo no existe y el frontend lo sirve `npm run dev`.
STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parent.parent / "static"))
if (STATIC_DIR / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{ruta:path}", include_in_schema=False)
    def spa(ruta: str):
        if ruta.startswith("api/"):
            raise HTTPException(404, "No existe")
        archivo = (STATIC_DIR / ruta).resolve()
        if ruta and archivo.is_file() and STATIC_DIR.resolve() in archivo.parents:
            return FileResponse(archivo)
        return FileResponse(STATIC_DIR / "index.html")
