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
from .auth import area_de, datos_iniciales, router as auth_router, usuario_actual
from .models import Asistencia, Importacion, Sede, Usuario
from .schemas import AsistenciaCreate, AsistenciaOut, ImportacionOut, ResultadoImportacion

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("asistencia")
TZ = ZoneInfo(config.TZ_LOCAL)
scheduler = BackgroundScheduler(timezone=TZ)


def hoy() -> date:
    return datetime.now(TZ).date()


def areas_activas(db: Session) -> list[str]:
    """Áreas del ERP de las sedes activas; si no hay sedes, ERP_AREAS o "" (todas)."""
    areas = list(db.scalars(select(Sede.area_erp).where(Sede.activo.is_(True)).order_by(Sede.nombre)))
    return areas or config.ERP_AREAS or [""]


def tarea_automatica():
    """Consulta al ERP el día actual, una vez por cada sede activa."""
    db = SessionLocal()
    try:
        for area in areas_activas(db):
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
    with SessionLocal() as db:
        datos_iniciales(db)
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
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)


# ---------- Consulta ----------
# Todas las rutas piden sesión (usuario_actual). Un USUARIO solo ve su sede (area_de).
@app.get("/api/asistencias", response_model=list[AsistenciaOut])
def listar(
    fecha: date | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    sede_id: int | None = None,
    estado: str | None = None,
    q: str | None = None,
    u: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    stmt = select(Asistencia)
    area = area_de(u, db, sede_id)
    if area:
        stmt = stmt.where(Asistencia.area == area)
    if fecha:
        stmt = stmt.where(Asistencia.fecha == fecha)
    if desde:
        stmt = stmt.where(Asistencia.fecha >= desde)
    if hasta:
        stmt = stmt.where(Asistencia.fecha <= hasta)
    if estado:
        stmt = stmt.where(Asistencia.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Asistencia.trabajador_nombre.ilike(like), Asistencia.trabajador_dni.ilike(like)))
    stmt = stmt.order_by(Asistencia.fecha.desc(), Asistencia.tienda_nombre,
                         Asistencia.hora_entrada.asc().nulls_last(), Asistencia.trabajador_nombre)
    return db.scalars(stmt.limit(5000)).all()


@app.get("/api/resumen")
def resumen(fecha: date | None = None, sede_id: int | None = None,
            u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    fecha = fecha or hoy()
    stmt = select(Asistencia.estado, func.count()).where(Asistencia.fecha == fecha)
    area = area_de(u, db, sede_id)
    if area:
        stmt = stmt.where(Asistencia.area == area)
    filas = db.execute(stmt.group_by(Asistencia.estado)).all()
    por_estado = {(e or "SIN ESTADO"): n for e, n in filas}
    return {"fecha": fecha, "total": sum(por_estado.values()), "por_estado": por_estado}


@app.get("/api/estados", response_model=list[str])
def estados(_: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    base = {"PUNTUAL", "TARDANZA", "FALTA", "LICENCIA", "VACACIONES", "PERMISO"}
    base |= {e for e in db.scalars(select(Asistencia.estado).distinct()) if e}
    return sorted(base)


@app.get("/api/trabajadores")
def trabajadores(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Lista única de trabajadores ya vistos (para autocompletar el registro manual)."""
    stmt = select(Asistencia.trabajador_dni, Asistencia.trabajador_nombre, Asistencia.trabajador_id,
                  Asistencia.tienda_nombre, Asistencia.area).order_by(Asistencia.fecha.desc())
    area = area_de(u, db)
    if area:
        stmt = stmt.where(Asistencia.area == area)
    vistos: dict[str, dict] = {}
    for dni, nombre, tid, sede, ar in db.execute(stmt).all():
        clave = dni or nombre
        if clave not in vistos:
            vistos[clave] = {"dni": dni, "nombre": nombre, "trabajador_id": tid, "sede": sede, "area": ar}
    return sorted(vistos.values(), key=lambda x: x["nombre"] or "")


# ---------- Registro manual ----------
def _sede_para(u: Usuario, sede_id: int | None, db: Session) -> Sede:
    if u.rol != "ADMIN":
        if not u.sede:
            raise HTTPException(403, "Tu usuario no tiene sede asignada")
        return u.sede
    s = db.get(Sede, sede_id) if sede_id else None
    if not s:
        raise HTTPException(400, "Elige la sede")
    return s


def _asistencia_propia(aid: int, u: Usuario, db: Session) -> Asistencia:
    a = db.get(Asistencia, aid)
    area = area_de(u, db)
    if not a or (area and (a.area or "").upper() != area.upper()):
        raise HTTPException(404, "No existe")
    return a


@app.post("/api/asistencias", response_model=AsistenciaOut, status_code=201)
def crear(datos: AsistenciaCreate, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    sede = _sede_para(u, datos.sede_id, db)
    a = Asistencia(**datos.model_dump(exclude={"sede_id"}), area=sede.area_erp, tienda_nombre=sede.nombre,
                   origen="MANUAL", autorizado_por=f"{u.nombre} {u.apellido}")
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@app.put("/api/asistencias/{aid}", response_model=AsistenciaOut)
def editar(aid: int, datos: AsistenciaCreate, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    a = _asistencia_propia(aid, u, db)
    for k, v in datos.model_dump(exclude={"sede_id"}).items():
        setattr(a, k, v)
    if u.rol == "ADMIN" and datos.sede_id:
        sede = _sede_para(u, datos.sede_id, db)
        if (a.area or "").upper() != sede.area_erp:
            a.area, a.tienda_nombre = sede.area_erp, sede.nombre
    db.commit()
    db.refresh(a)
    return a


@app.delete("/api/asistencias/{aid}", status_code=204)
def borrar(aid: int, u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.delete(_asistencia_propia(aid, u, db))
    db.commit()


# ---------- Carga manual de JSON ----------
@app.post("/api/importar/json", response_model=ResultadoImportacion)
def importar_json(payload: dict | list = Body(...), u: Usuario = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    try:
        return importar(db, payload, "JSON", solo_area=area_de(u, db))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/importar/archivo", response_model=ResultadoImportacion)
async def importar_archivo(archivo: UploadFile = File(...), u: Usuario = Depends(usuario_actual),
                           db: Session = Depends(get_db)):
    contenido = (await archivo.read()).decode("utf-8-sig")
    try:
        return importar(db, json.loads(contenido), "JSON", solo_area=area_de(u, db))
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"El archivo no es un JSON válido: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))


# ---------- Consulta al ERP (manual o programada) ----------
@app.post("/api/importar/consulta", response_model=ResultadoImportacion)
def importar_consulta(
    fecha: date | None = Query(None, description="fecha_inicio; por defecto hoy"),
    hasta: date | None = Query(None, description="fecha_fin; por defecto igual a fecha"),
    sede_id: int | None = Query(None, description="Sede a consultar (ADMIN); por defecto todas las activas"),
    estado: str | None = Query(None, description="Filtro estado del ERP (opcional)"),
    trabajador_id: int | None = Query(None, description="Filtro trabajador_id del ERP (opcional)"),
    cliente_id: int | None = Query(None, description="Filtro cliente_id del ERP (opcional)"),
    u: Usuario = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    inicio = fecha or hoy()
    fin = hasta or inicio
    if fin < inicio or (fin - inicio).days > 62:
        raise HTTPException(400, "Rango inválido (máximo 62 días)")
    area = area_de(u, db, sede_id)
    areas = [area] if area else areas_activas(db)
    total = ResultadoImportacion(total=0, nuevos=0, actualizados=0, omitidos=0)
    for a in areas:
        try:
            r = sincronizar(db, inicio, fin, area=a, estado=estado,
                            trabajador_id=trabajador_id, cliente_id=cliente_id)
        except ErpSesionExpirada as e:
            # 424 (y no 401) para no confundirlo con la sesión de esta web
            raise HTTPException(424, str(e))
        except ErpError as e:
            raise HTTPException(502, f"Error consultando el ERP ({a or 'todas las áreas'}): {e}")
        total.total += r.total
        total.nuevos += r.nuevos
        total.actualizados += r.actualizados
        total.omitidos += r.omitidos
        total.errores += r.errores
    return total


@app.get("/api/importaciones", response_model=list[ImportacionOut])
def importaciones(_: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    return db.scalars(select(Importacion).order_by(Importacion.id.desc()).limit(30)).all()


@app.get("/api/config")
def ver_config(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    proximas = []
    if scheduler.running:
        proximas = sorted(j.next_run_time.isoformat() for j in scheduler.get_jobs() if j.next_run_time)
    return {
        "api_configurada": True,
        "api_url": config.ERP_URL,
        "erp_areas": [area_de(u, db)] if u.rol != "ADMIN" else areas_activas(db),
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
