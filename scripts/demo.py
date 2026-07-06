"""Demo data seeder/wiper (temporary — not part of the app).

  python -m scripts.demo seed   # insert ~4 days of realistic data
  python -m scripts.demo wipe   # remove ALL logged data (keeps patient row)
"""
from __future__ import annotations

import datetime as dt
import sys
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row

from app import config

TZ = ZoneInfo("America/Sao_Paulo")

# Meals are separate events with macros: (hour, min, tag, carbs_g, protein_g, desc)
MEALS = [
    (7, 40, "cafe", 32, 14, "Pão integral, ovos e café"),
    (12, 30, "almoco", 68, 38, "Arroz, feijão, frango grelhado e salada"),
    (16, 10, "lanche", 24, 9, "Iogurte com granola"),
    (19, 40, "janta", 52, 30, "Macarrão com carne moída"),
]

# Humalog is ERRATIC — irregular times/units through the day (meals + corrections).
# (hour, min, units, reason)
HUMALOG = [
    (7, 55, 6, "refeicao"),
    (10, 20, 2, "correcao"),
    (12, 40, 11, "refeicao"),
    (15, 5, 3, "correcao"),
    (16, 20, 2, "refeicao"),
    (19, 50, 9, "refeicao"),
    (22, 35, 4, "correcao"),
]

# Glicemia readings: (hour, min, mg_dl, context)
GLUCOSE = [
    (7, 30, 118, "jejum"),
    (10, 15, 158, "pos_refeicao"),
    (13, 0, 172, "pos_refeicao"),
    (15, 0, 149, "outro"),
    (18, 15, 104, "pre_refeicao"),
    (21, 10, 137, "pos_refeicao"),
    (23, 30, 126, "dormir"),
]

COLIRIO = [(8, 0), (14, 0), (20, 0)]
DRIFT = {3: -9, 2: +7, 1: -3, 0: +4}  # per-day glucose drift so the chart varies


def _pid(cur) -> int:
    cur.execute("select id from patients order by id limit 1")
    return cur.fetchone()["id"]


def seed() -> None:
    now = dt.datetime.now(TZ)
    with psycopg.connect(config.DATABASE_URL, row_factory=dict_row, autocommit=True) as conn:
        cur = conn.cursor()
        pid = _pid(cur)
        n = 0

        def at(day, h, m):
            return dt.datetime.combine(day, dt.time(h, m), tzinfo=TZ)

        for offset in (3, 2, 1, 0):
            day = (now - dt.timedelta(days=offset)).date()
            drift = DRIFT[offset]
            for h, m, tag, c, p, desc in MEALS:
                ts = at(day, h, m)
                if True:  # demo: seed full days incl. today so "Dia" view is complete
                    cur.execute("insert into meals (patient_id, eaten_at, carbs_g, protein_g, meal_tag, description) values (%s,%s,%s,%s,%s,%s)",
                                (pid, ts, c, p, tag, desc)); n += 1
            for h, m, u, r in HUMALOG:
                ts = at(day, h, m)
                if True:  # demo: seed full days incl. today so "Dia" view is complete
                    cur.execute("insert into humalog_doses (patient_id, taken_at, units, reason) values (%s,%s,%s,%s)",
                                (pid, ts, u, r)); n += 1
            for h, m, mg, ctx in GLUCOSE:
                ts = at(day, h, m)
                if True:  # demo: seed full days incl. today so "Dia" view is complete
                    cur.execute("insert into glucose_readings (patient_id, measured_at, mg_dl, context) values (%s,%s,%s,%s)",
                                (pid, ts, mg + drift, ctx)); n += 1
            for h, m in COLIRIO:
                ts = at(day, h, m)
                if True:  # demo: seed full days incl. today so "Dia" view is complete
                    cur.execute("insert into colirio_uses (patient_id, used_at, eye, product) values (%s,%s,'ambos',%s)",
                                (pid, ts, config.COLIRIO_PRODUCT)); n += 1
            cur.execute("insert into basal_doses (patient_id, taken_at, units, status) values (%s,%s,20,'taken')",
                        (pid, at(day, 21, 0))); n += 1

        # a couple of very recent entries so cards look live right now
        cur.execute("insert into glucose_readings (patient_id, measured_at, mg_dl, context) values (%s,%s,143,'pre_refeicao')",
                    (pid, now - dt.timedelta(minutes=25)))
        cur.execute("insert into humalog_doses (patient_id, taken_at, units, reason) values (%s,%s,4,'correcao')",
                    (pid, now - dt.timedelta(minutes=90)))
        print(f"Seeded {n + 2} demo records for patient {pid}.")


def wipe() -> None:
    with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
        for t in ("humalog_doses", "meals", "basal_doses", "glucose_readings", "colirio_uses"):
            conn.execute(f"delete from {t}")
        print("Wiped all logged data (patient row kept).")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "seed"
    {"seed": seed, "wipe": wipe}[cmd]()
