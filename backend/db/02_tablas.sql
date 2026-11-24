-- Generado desde backend/app/models.py (idéntico al esquema que crea la app).
-- Ejecutar conectado a la base "asistencia" con el usuario "asistencia":
--   psql -h HOST -U asistencia -d asistencia -f 02_tablas.sql
-- Es idempotente: se puede correr varias veces sin romper nada.

BEGIN;

-- 1. Sedes: cada sede se une a los registros por su área en el ERP (campo "area" de IGEA)
CREATE TABLE IF NOT EXISTS sedes (
	id SERIAL NOT NULL,
	nombre VARCHAR(100) NOT NULL,
	area_erp VARCHAR(200) NOT NULL,
	activo BOOLEAN DEFAULT true NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (nombre),
	UNIQUE (area_erp)
);

-- 2. Usuarios: contraseña guardada como hash bcrypt; USUARIO ve solo su sede, ADMIN todas
CREATE TABLE IF NOT EXISTS usuarios (
	id SERIAL NOT NULL,
	usuario VARCHAR(50) NOT NULL,
	password_hash VARCHAR(100) NOT NULL,
	nombre VARCHAR(100) NOT NULL,
	apellido VARCHAR(100) NOT NULL,
	dni VARCHAR(20),
	rol VARCHAR(20) DEFAULT 'USUARIO' NOT NULL,
	sede_id INTEGER,
	activo BOOLEAN DEFAULT true NOT NULL,
	debe_cambiar_password BOOLEAN DEFAULT true NOT NULL,
	version_sesion INTEGER DEFAULT 1 NOT NULL,
	ultimo_acceso TIMESTAMP WITH TIME ZONE,
	creado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (dni),
	FOREIGN KEY(sede_id) REFERENCES sedes (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_usuarios_usuario ON usuarios (usuario);

-- 3. Asistencias: una fila por trabajador y día. external_id = "id" del ERP (evita duplicados)
CREATE TABLE IF NOT EXISTS asistencias (
	id SERIAL NOT NULL,
	external_id INTEGER,
	fecha DATE NOT NULL,
	trabajador_id INTEGER,
	trabajador_nombre VARCHAR(200) NOT NULL,
	trabajador_dni VARCHAR(20),
	estado VARCHAR(40),
	hora_entrada TIME WITHOUT TIME ZONE,
	hora_salida TIME WITHOUT TIME ZONE,
	motivo_ausencia TEXT,
	motivo_salida TEXT,
	autorizado_por VARCHAR(200),
	observaciones TEXT,
	foto_entrada VARCHAR(500),
	foto_salida VARCHAR(500),
	lat_entrada FLOAT,
	lng_entrada FLOAT,
	lat_salida FLOAT,
	lng_salida FLOAT,
	es_licencia INTEGER DEFAULT 0 NOT NULL,
	licencia_tipo VARCHAR(100),
	tienda_id INTEGER,
	tienda_nombre VARCHAR(200),
	cliente_nombre VARCHAR(200),
	area VARCHAR(200),
	origen VARCHAR(20) DEFAULT 'MANUAL' NOT NULL,
	raw JSON,
	creado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	actualizado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ix_asistencias_external_id ON asistencias (external_id);
CREATE INDEX IF NOT EXISTS ix_asistencias_fecha ON asistencias (fecha);
CREATE INDEX IF NOT EXISTS ix_asistencias_tienda_nombre ON asistencias (tienda_nombre);
CREATE INDEX IF NOT EXISTS ix_asistencias_trabajador_dni ON asistencias (trabajador_dni);

-- 4. Historial de cargas (ERP, JSON, automática)
CREATE TABLE IF NOT EXISTS importaciones (
	id SERIAL NOT NULL,
	momento TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	origen VARCHAR(20) NOT NULL,
	fecha_consultada DATE,
	total INTEGER DEFAULT 0 NOT NULL,
	nuevos INTEGER DEFAULT 0 NOT NULL,
	actualizados INTEGER DEFAULT 0 NOT NULL,
	ok BOOLEAN DEFAULT true NOT NULL,
	mensaje TEXT,
	PRIMARY KEY (id)
);

-- Sedes iniciales
INSERT INTO sedes (nombre, area_erp, activo) VALUES
    ('CHORRILLOS', 'SEDE CHORRILLOS', true),
    ('TIZA',       'SEDE TIZA',       true)   -- verificar el área exacta en IGEA
ON CONFLICT DO NOTHING;

COMMIT;

-- El primer usuario administrador NO se crea aquí: lo crea la app al iniciar si la tabla
-- usuarios está vacía (usuario ADMIN_USUARIO, contraseña ADMIN_PASSWORD_INICIAL o temporal en el log).
