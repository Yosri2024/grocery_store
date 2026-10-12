-- ============================================================
-- Grocery Store — PostgreSQL 16 OBLIGATOIRE
-- Exécuter en superuser postgres : psql -U postgres -f sql/01_init.sql
-- ============================================================

-- 1) Rôle applicatif (change le mot de passe en prod !)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grocery_user') THEN
    CREATE ROLE grocery_user WITH LOGIN PASSWORD 'grocery_pass_123';
  END IF;
END
$$;

-- 2) Base de données propriétaire grocery_user
SELECT 'CREATE DATABASE grocery_db OWNER grocery_user ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'grocery_db')\gexec

-- 3) Extensions requises pour full-text + trigramme + unaccent
\c grocery_db

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- 4) Droits
GRANT ALL PRIVILEGES ON DATABASE grocery_db TO grocery_user;
ALTER SCHEMA public OWNER TO grocery_user;
GRANT ALL ON SCHEMA public TO grocery_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO grocery_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO grocery_user;

-- 5) Vérification
-- Correspond à .env : DATABASE_URL=postgres://grocery_user:grocery_pass_123@127.0.0.1:5432/grocery_db
SELECT version();
SELECT extname FROM pg_extension WHERE extname IN ('pg_trgm', 'unaccent', 'btree_gin');

-- ============================================================
-- Commandes utiles (psql) :
--   psql "postgres://grocery_user:grocery_pass_123@127.0.0.1:5432/grocery_db" -c "\dx"
--   python manage.py migrate
--   python manage.py createsuperuser
-- Reset total (DEV uniquement) :
--   DROP DATABASE IF EXISTS grocery_db;
--   DROP ROLE IF EXISTS grocery_user;
-- ============================================================
