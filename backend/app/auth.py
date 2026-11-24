"""Inicio de sesión, usuarios y sedes.

- Contraseñas: hash bcrypt (con sal), nunca se guardan ni se devuelven en texto.
- Sesión: token JWT firmado (HS256) en cookie httpOnly + SameSite=Lax (JavaScript no puede leerla).
- Cada usuario USUARIO pertenece a una sede y solo ve/modifica datos de esa sede; ADMIN ve todas.
"""
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import Sede, Usuario
from .schemas import (CambioPasswordIn, LoginIn, SedeIn, SedeOut, UsuarioCreate, UsuarioOut,
                      UsuarioUpdate)

log = logging.getLogger("asistencia.auth")

COOKIE = "asistencia_sesion"
ALG = "HS256"
SECRET = config.SECRET_KEY or secrets.token_urlsafe(48)
if not config.SECRET_KEY:
    log.warning("SECRET_KEY no configurada: se usa una temporal y las sesiones se cerrarán al reiniciar.")

# ---------------- Contraseñas ----------------
_HASH_FALSO = bcrypt.hashpw(b"x", bcrypt.gensalt()).decode()


def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode()


def verificar_password(p: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(p.encode("utf-8")[:72], h.encode())
    except ValueError:
        return False


# ---------------- Bloqueo por intentos fallidos ----------------
MAX_INTENTOS, BLOQUEO_SEG = 5, 300
_fallos: dict[str, tuple[int, float]] = {}


def _bloqueado(clave: str) -> int:
    n, hasta = _fallos.get(clave, (0, 0.0))
    return int(hasta - time.time()) if n >= MAX_INTENTOS and hasta > time.time() else 0


def _registrar_fallo(clave: str):
    n, hasta = _fallos.get(clave, (0, 0.0))
    if hasta and hasta <= time.time():
        n = 0
    n += 1
    _fallos[clave] = (n, time.time() + BLOQUEO_SEG if n >= MAX_INTENTOS else 0.0)


# ---------------- Token / cookie ----------------
def _crear_token(u: Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    datos = {"sub": str(u.id), "v": u.version_sesion, "iat": ahora,
             "exp": ahora + timedelta(hours=config.SESION_HORAS)}
    return jwt.encode(datos, SECRET, algorithm=ALG)


def _poner_cookie(resp: Response, token: str):
    resp.set_cookie(COOKIE, token, max_age=int(config.SESION_HORAS * 3600), httponly=True,
                    samesite="lax", secure=config.COOKIE_SECURE, path="/")


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Inicia sesión")
    try:
        datos = jwt.decode(token, SECRET, algorithms=[ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "La sesión expiró, vuelve a iniciar sesión")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sesión inválida")
    u = db.get(Usuario, int(datos["sub"]))
    if not u or not u.activo or u.version_sesion != datos.get("v"):
        raise HTTPException(401, "Sesión inválida")
    return u


def solo_admin(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "ADMIN":
        raise HTTPException(403, "Solo el administrador puede hacer esto")
    return u


def area_de(u: Usuario, db: Session, sede_id: int | None = None) -> str | None:
    """Área del ERP a la que se limita la consulta. USUARIO: siempre la suya. ADMIN: la elegida o None (todas)."""
    if u.rol != "ADMIN":
        if not u.sede:
            raise HTTPException(403, "Tu usuario no tiene sede asignada")
        return u.sede.area_erp
    if sede_id:
        s = db.get(Sede, sede_id)
        if not s:
            raise HTTPException(404, "Sede no existe")
        return s.area_erp
    return None


# ---------------- Endpoints de sesión ----------------
router = APIRouter(prefix="/api")


@router.post("/auth/login", response_model=UsuarioOut)
def login(datos: LoginIn, request: Request, resp: Response, db: Session = Depends(get_db)):
    nombre = datos.usuario.strip().lower()
    clave = f"{nombre}|{request.client.host if request.client else ''}"
    if (seg := _bloqueado(clave)):
        raise HTTPException(429, f"Demasiados intentos. Espera {seg // 60 + 1} min.")
    u = db.scalar(select(Usuario).where(Usuario.usuario == nombre))
    ok = verificar_password(datos.password, u.password_hash if u else _HASH_FALSO)  # mismo tiempo exista o no
    if not u or not ok or not u.activo:
        _registrar_fallo(clave)
        log.info("Login fallido: %s", nombre)
        raise HTTPException(401, "Usuario o contraseña incorrectos")
    _fallos.pop(clave, None)
    u.ultimo_acceso = datetime.now(timezone.utc)
    db.commit()
    _poner_cookie(resp, _crear_token(u))
    return u


@router.post("/auth/logout", status_code=204)
def logout(resp: Response):
    resp.delete_cookie(COOKIE, path="/")


@router.get("/auth/me", response_model=UsuarioOut)
def me(u: Usuario = Depends(usuario_actual)):
    return u


@router.post("/auth/cambiar-password", response_model=UsuarioOut)
def cambiar_password(datos: CambioPasswordIn, resp: Response, u: Usuario = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    if not verificar_password(datos.actual, u.password_hash):
        raise HTTPException(400, "La contraseña actual no es correcta")
    if datos.actual == datos.nueva:
        raise HTTPException(400, "La nueva contraseña debe ser distinta")
    u.password_hash = hash_password(datos.nueva)
    u.debe_cambiar_password = False
    u.version_sesion += 1          # cierra las demás sesiones
    db.commit()
    _poner_cookie(resp, _crear_token(u))
    return u


# ---------------- Administración de usuarios ----------------
def _validar_usuario(datos, db: Session):
    if datos.rol == "USUARIO" and not datos.sede_id:
        raise HTTPException(400, "Un usuario de sede debe tener una sede asignada")
    if datos.sede_id and not db.get(Sede, datos.sede_id):
        raise HTTPException(400, "La sede no existe")


def _guardar(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un registro con ese usuario, DNI o nombre")


@router.get("/usuarios", response_model=list[UsuarioOut])
def listar_usuarios(_: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    return db.scalars(select(Usuario).order_by(Usuario.apellido, Usuario.nombre)).all()


@router.post("/usuarios", response_model=UsuarioOut, status_code=201)
def crear_usuario(datos: UsuarioCreate, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    _validar_usuario(datos, db)
    u = Usuario(**datos.model_dump(exclude={"password"}), password_hash=hash_password(datos.password),
                debe_cambiar_password=True)
    if u.rol == "ADMIN" and not datos.sede_id:
        u.sede_id = None
    db.add(u)
    _guardar(db)
    db.refresh(u)
    return u


@router.put("/usuarios/{uid}", response_model=UsuarioOut)
def editar_usuario(uid: int, datos: UsuarioUpdate, yo: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "No existe")
    _validar_usuario(datos, db)
    if u.id == yo.id and (not datos.activo or datos.rol != "ADMIN"):
        raise HTTPException(400, "No puedes quitarte el rol de administrador ni desactivarte")
    for k, v in datos.model_dump(exclude={"password"}).items():
        setattr(u, k, v)
    if datos.password:
        u.password_hash = hash_password(datos.password)
        u.debe_cambiar_password = u.id != yo.id
        u.version_sesion += 1
    if not datos.activo:
        u.version_sesion += 1
    _guardar(db)
    db.refresh(u)
    return u


@router.delete("/usuarios/{uid}", status_code=204)
def borrar_usuario(uid: int, yo: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "No existe")
    if u.id == yo.id:
        raise HTTPException(400, "No puedes eliminar tu propio usuario")
    db.delete(u)
    db.commit()


# ---------------- Sedes ----------------
@router.get("/sedes", response_model=list[SedeOut])
def listar_sedes(u: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    if u.rol != "ADMIN":
        return [u.sede] if u.sede else []
    return db.scalars(select(Sede).order_by(Sede.nombre)).all()


@router.post("/sedes", response_model=SedeOut, status_code=201)
def crear_sede(datos: SedeIn, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    s = Sede(**datos.model_dump())
    db.add(s)
    _guardar(db)
    db.refresh(s)
    return s


@router.put("/sedes/{sid}", response_model=SedeOut)
def editar_sede(sid: int, datos: SedeIn, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    s = db.get(Sede, sid)
    if not s:
        raise HTTPException(404, "No existe")
    for k, v in datos.model_dump().items():
        setattr(s, k, v)
    _guardar(db)
    db.refresh(s)
    return s


@router.delete("/sedes/{sid}", status_code=204)
def borrar_sede(sid: int, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    s = db.get(Sede, sid)
    if not s:
        raise HTTPException(404, "No existe")
    if db.scalar(select(func.count()).select_from(Usuario).where(Usuario.sede_id == sid)):
        raise HTTPException(400, "La sede tiene usuarios asignados; reasígnalos o desactiva la sede")
    db.delete(s)
    db.commit()


# ---------------- Datos iniciales ----------------
def datos_iniciales(db: Session):
    """Crea las sedes iniciales y el primer administrador si la base está vacía."""
    if not db.scalar(select(func.count()).select_from(Sede)):
        for par in config.SEDES_INICIALES.split(","):
            if "=" in par:
                nombre, area = (x.strip().upper() for x in par.split("=", 1))
                db.add(Sede(nombre=nombre, area_erp=area))
        db.commit()
    if not db.scalar(select(func.count()).select_from(Usuario)):
        password = config.ADMIN_PASSWORD_INICIAL or secrets.token_urlsafe(9)
        db.add(Usuario(usuario=config.ADMIN_USUARIO.lower(), password_hash=hash_password(password),
                       nombre="Administrador", apellido="Sistema", rol="ADMIN", debe_cambiar_password=True))
        db.commit()
        if config.ADMIN_PASSWORD_INICIAL:
            log.warning("Usuario administrador '%s' creado con ADMIN_PASSWORD_INICIAL.", config.ADMIN_USUARIO)
        else:
            log.warning("Usuario administrador creado -> usuario: %s  contraseña temporal: %s  "
                        "(se pedirá cambiarla al ingresar)", config.ADMIN_USUARIO, password)
