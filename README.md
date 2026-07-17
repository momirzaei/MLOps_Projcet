# Retail BI Assistant MLOps Project

Foundation for a retail BI assistant pipeline. Step 1 sets up repository structure,
configuration, local secrets, Dockerized PostgreSQL, and the initial warehouse roles
and schema.

## Step 1: Foundation

- `docs/` stores the DPRD document.
- `src/config/` provides a single settings module loaded from `.env`.
- `docker/postgres/init/01_users.sh` creates the `mlflow` database, owner role,
  and read-only role using container environment variables loaded by Docker
  Compose from `.env`.
- `docker/postgres/init/02_schema.sql` creates the `gold` schema and grants.
  It contains structure only, with no secrets.
- `data/bronze`, `data/silver`, and `data/quarantine` are tracked with `.gitkeep`
  files, while generated data remains ignored.

## Local Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
docker compose up -d
```

Copy `.env.example` to `.env` and replace placeholder passwords and the Groq API key
before running the full process.
