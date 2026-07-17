-- =========================================================
-- 02_schema.sql - gold schema + grants for Text-to-SQL safety
-- Passwords/users are provisioned by 01_users.sh from env vars.
-- This file contains structure only and is safe to commit.
-- =========================================================

\getenv postgres_db POSTGRES_DB
\getenv dwh_owner_user DWH_OWNER_USER
\getenv dwh_readonly_user DWH_READONLY_USER

\connect :postgres_db

-- ---------- schema ----------
CREATE SCHEMA IF NOT EXISTS gold AUTHORIZATION :"dwh_owner_user";

-- owner: full control of gold
GRANT ALL ON SCHEMA gold TO :"dwh_owner_user";

-- readonly: connect + read gold, nothing else
GRANT CONNECT ON DATABASE :"postgres_db" TO :"dwh_readonly_user";
GRANT USAGE ON SCHEMA gold TO :"dwh_readonly_user";
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO :"dwh_readonly_user";

-- future tables/views created by retail_owner in gold are auto-readable
ALTER DEFAULT PRIVILEGES FOR ROLE :"dwh_owner_user" IN SCHEMA gold
    GRANT SELECT ON TABLES TO :"dwh_readonly_user";

-- explicitly block readonly from public schema writes
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
