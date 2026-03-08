#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for Postgres..."
python - <<'PY'
import os
import time
from sqlalchemy import create_engine, text

db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)
for _ in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Postgres is ready")
        break
    except Exception:
        time.sleep(1)
else:
    raise SystemExit("Postgres is unavailable")
PY

echo "Applying migrations..."
alembic upgrade head

python -m app.init_db

exec uvicorn app.main:app --host 0.0.0.0 --port 3100
