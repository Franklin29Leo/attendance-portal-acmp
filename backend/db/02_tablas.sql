-- Tablas de la app (el backend también las crea solo al iniciar).
-- Ejecutar conectado a la base asistencia, como el usuario asistencia.

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
	es_licencia INTEGER NOT NULL, 
	licencia_tipo VARCHAR(100), 
	tienda_id INTEGER, 
	tienda_nombre VARCHAR(200), 
	cliente_nombre VARCHAR(200), 
	area VARCHAR(200), 
	origen VARCHAR(20) NOT NULL, 
	raw JSON, 
	creado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	actualizado TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS ix_asistencias_trabajador_dni ON asistencias (trabajador_dni);
CREATE UNIQUE INDEX IF NOT EXISTS ix_asistencias_external_id ON asistencias (external_id);
CREATE INDEX IF NOT EXISTS ix_asistencias_fecha ON asistencias (fecha);
CREATE INDEX IF NOT EXISTS ix_asistencias_tienda_nombre ON asistencias (tienda_nombre);

CREATE TABLE IF NOT EXISTS importaciones (
	id SERIAL NOT NULL, 
	momento TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	origen VARCHAR(20) NOT NULL, 
	fecha_consultada DATE, 
	total INTEGER NOT NULL, 
	nuevos INTEGER NOT NULL, 
	actualizados INTEGER NOT NULL, 
	ok BOOLEAN NOT NULL, 
	mensaje TEXT, 
	PRIMARY KEY (id)
);
