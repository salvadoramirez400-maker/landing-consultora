-- Datos del titular para presentar una marca en INAPI (formulario /marcas/datos).
-- Aplicar una vez: psql "$POSTGRES_URL" -f migrations/002_marcas_titulares.sql

CREATE TABLE IF NOT EXISTS marcas_titulares (
  id SERIAL PRIMARY KEY,
  fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  marca TEXT NOT NULL,
  titular_tipo TEXT NOT NULL CHECK (titular_tipo IN ('persona', 'empresa')),
  nombre TEXT NOT NULL,
  rut TEXT NOT NULL,
  razon_social TEXT NOT NULL DEFAULT '',
  rut_empresa TEXT NOT NULL DEFAULT '',
  cargo TEXT NOT NULL DEFAULT '',
  domicilio TEXT NOT NULL,
  comuna TEXT NOT NULL,
  correo TEXT NOT NULL,
  telefono TEXT NOT NULL,
  productos TEXT NOT NULL DEFAULT '',
  autoriza BOOLEAN NOT NULL,
  procesado BOOLEAN NOT NULL DEFAULT FALSE
);
