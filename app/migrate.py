"""Apply db/schema.sql to the configured Postgres. Idempotent.

Run with: python -m app.migrate
Also runs automatically on web startup (see Procfile).
"""
from __future__ import annotations

from pathlib import Path

import psycopg

from . import config

SCHEMA = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> None:
    if not config.DATABASE_URL:
        raise SystemExit("DATABASE_URL not set")
    sql = SCHEMA.read_text()
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        conn.execute(sql)
    print(f"Applied schema from {SCHEMA}")


if __name__ == "__main__":
    main()
