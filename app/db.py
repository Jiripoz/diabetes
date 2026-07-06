"""Postgres data access (Railway). Direct connection via psycopg."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None
_patient_cache: dict | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL not set")
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


@contextmanager
def cursor() -> Iterator:
    with pool().connection() as conn:  # commits on clean exit, rolls back on error
        with conn.cursor() as cur:
            yield cur


def get_or_create_patient() -> dict:
    global _patient_cache
    if _patient_cache is not None:
        return _patient_cache
    with cursor() as cur:
        cur.execute("select * from patients limit 1")
        row = cur.fetchone()
        if row is None:
            cur.execute(
                "insert into patients (name, telegram_id, timezone) "
                "values (%s, %s, %s) returning *",
                (config.PATIENT_NAME, config.ALLOWED_TELEGRAM_ID, config.TIMEZONE),
            )
            row = cur.fetchone()
    _patient_cache = row
    return row


def _patient_id() -> int:
    return get_or_create_patient()["id"]


def log_humalog(units: float, meal_tag: str | None = None, carbs_g: int | None = None) -> dict:
    with cursor() as cur:
        cur.execute(
            "insert into humalog_doses (patient_id, units, meal_tag, carbs_g) "
            "values (%s, %s, %s, %s) returning *",
            (_patient_id(), units, meal_tag, carbs_g),
        )
        return cur.fetchone()


def log_basal(status: str = "taken", units: float | None = None) -> dict:
    with cursor() as cur:
        cur.execute(
            "insert into basal_doses (patient_id, status, units) "
            "values (%s, %s, %s) returning *",
            (_patient_id(), status, units),
        )
        return cur.fetchone()


def log_glucose(mg_dl: int, context: str | None = None) -> dict:
    with cursor() as cur:
        cur.execute(
            "insert into glucose_readings (patient_id, mg_dl, context) "
            "values (%s, %s, %s) returning *",
            (_patient_id(), mg_dl, context),
        )
        return cur.fetchone()


def log_colirio(eye: str | None = None, product: str | None = None) -> dict:
    with cursor() as cur:
        cur.execute(
            "insert into colirio_uses (patient_id, eye, product) "
            "values (%s, %s, %s) returning *",
            (_patient_id(), eye, product or config.COLIRIO_PRODUCT),
        )
        return cur.fetchone()


# table/ts_col are fixed internal constants (never user input) — safe to interpolate.
def recent(table: str, ts_col: str, limit: int = 50) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            f"select * from {table} where patient_id = %s order by {ts_col} desc limit %s",
            (_patient_id(), limit),
        )
        return cur.fetchall()
