-- Ejecutar como superusuario (postgres), conectado a la base "postgres".
CREATE USER asistencia WITH PASSWORD 'asistencia';
CREATE DATABASE asistencia OWNER asistencia ENCODING 'UTF8';
