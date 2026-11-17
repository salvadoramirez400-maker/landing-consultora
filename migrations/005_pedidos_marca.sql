-- Nombre de la marca en los pedidos de reserva de marca (/pagar/reserva).
-- Aplicar una vez: psql "$POSTGRES_URL" -f migrations/005_pedidos_marca.sql (db.ensure_schema() también la corre).

ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS marca TEXT NOT NULL DEFAULT '';
