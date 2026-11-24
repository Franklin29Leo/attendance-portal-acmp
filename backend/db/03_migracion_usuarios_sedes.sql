-- Generado desde backend/app/models.py (idéntico al esquema que crea la app).
-- Ejecutar conectado a la base "asistencia" con el usuario "asistencia":
--   psql -h HOST -U asistencia -d asistencia -f 03_migracion_usuarios_sedes.sql
-- Es idempotente: se puede correr varias veces sin romper nada.

-- Para una base de producción que YA tiene asistencias e importaciones (versión sin login):
-- agrega solo las tablas de inicio de sesión y sedes. No toca los datos existentes.

BEGIN;

CREATE TABLE IF NOT EXISTS sedes (
	id SERIAL NOT NULL,
	nombre VARCHAR(100) NOT NULL,
	area_erp VARCHAR(200) NOT NULL,
	activo BOOLEAN DEFAULT true NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (nombre),
	UNIQUE (area_erp)
);

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

INSERT INTO sedes (nombre, area_erp, activo) VALUES
    ('CHORRILLOS', 'SEDE CHORRILLOS', true),
    ('TIZA',       'SEDE TIZA',       true)   -- verificar el área exacta en IGEA
ON CONFLICT DO NOTHING;

COMMIT;

-- Comprobación: registros que no pertenecen a ninguna sede (no los verá un usuario de sede)
SELECT area, count(*) AS registros
FROM asistencias
WHERE area IS NULL OR upper(area) NOT IN (SELECT area_erp FROM sedes)
GROUP BY area ORDER BY registros DESC;
