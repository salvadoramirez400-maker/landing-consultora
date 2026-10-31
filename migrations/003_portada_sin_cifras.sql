-- Portada sin cifras ni escasez sin respaldo (plan de abonos de CCC, 31-oct-2026).
-- Quita «Valorado 4.9/5 por más de 100 clientes», las cifras «10+ clínicas / 90 días / 100% con pacientes»,
-- «Cupos limitados este mes», «Solo tomamos 5 proyectos nuevos al mes» y «Plazas limitadas».
-- Toca solo esas claves: el resto del contenido editado desde /admin queda igual.
-- Aplicar una vez, después del deploy:
--   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U app -d landing_consultora < migrations/003_portada_sin_cifras.sql

UPDATE site_content
SET data = jsonb_set(jsonb_set(jsonb_set(jsonb_set(jsonb_set(data,
  '{hero,badge}', '"Arquitectura sanitaria y habilitación clínica"'),
  '{hero,note}', '"Partimos con un diagnóstico express de $49.990, que se descuenta si sigues con la resolución."'),
  '{stats,items}', '[]'),
  '{cta,badge}', '"Asesoría inicial"'),
  '{cta,text}', '"Revisamos tu caso y te decimos qué necesitas para abrir u operar con resolución sanitaria."')
WHERE id = 1;
