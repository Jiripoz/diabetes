"""Central config loaded from environment (.env in dev, Railway vars in prod)."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _times(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_TELEGRAM_ID = int(os.environ["ALLOWED_TELEGRAM_ID"]) if os.environ.get("ALLOWED_TELEGRAM_ID") else None

# App data lives in Railway Postgres. Locally use the public connection string;
# on Railway the internal DATABASE_URL is injected automatically.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Supabase is reserved for SSO/login only (added later); no app data here.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")

# Dashboard basic-auth (placeholder until Supabase SSO). If password is empty,
# the dashboard refuses to serve rather than exposing data openly.
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "glauber")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")

PATIENT_NAME = os.environ.get("PATIENT_NAME", "Glauber Machado")
TIMEZONE = os.environ.get("TIMEZONE", "America/Sao_Paulo")
TZ = ZoneInfo(TIMEZONE)

BASAGLAR_TIME = os.environ.get("BASAGLAR_TIME", "21:00")
COLIRIO_TIMES = _times(os.environ.get("COLIRIO_TIMES", "08:00,14:00,20:00"))
COLIRIO_PRODUCT = os.environ.get("COLIRIO_PRODUCT", "binadeprosto")

PORT = int(os.environ.get("PORT", "8000"))
