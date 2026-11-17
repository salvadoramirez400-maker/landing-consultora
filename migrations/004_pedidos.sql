-- Pedidos de pago con tarjeta desde la web (/pagar/<producto>): quién iba a pagar y si Mercado Pago confirmó el pago.
-- Aplicar una vez: psql "$POSTGRES_URL" -f migrations/004_pedidos.sql (db.ensure_schema() también la corre).

CREATE TABLE IF NOT EXISTS pedidos (
  id SERIAL PRIMARY KEY,
  ficha TEXT NOT NULL UNIQUE,                 -- identificador público, imposible de adivinar
  fecha TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  producto TEXT NOT NULL,
  monto INTEGER NOT NULL,
  nombre TEXT NOT NULL,
  telefono TEXT NOT NULL,
  tipo TEXT NOT NULL DEFAULT '',
  comuna TEXT NOT NULL DEFAULT '',
  estado TEXT NOT NULL DEFAULT 'iniciado' CHECK (estado IN ('iniciado', 'pendiente', 'pagado', 'rechazado')),
  mp_preferencia TEXT NOT NULL DEFAULT '',
  mp_pago TEXT NOT NULL DEFAULT '',
  pagado_en TIMESTAMPTZ,
  avisado BOOLEAN NOT NULL DEFAULT FALSE
);
