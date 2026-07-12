"""Central config loaded from environment (.env in dev, Railway vars in prod)."""
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _times(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Only these Telegram numeric user ids may use the bot. Empty = open (POC default).
ALLOWED_TELEGRAM_IDS = {
    int(i) for i in os.environ.get("ALLOWED_TELEGRAM_IDS", "").split(",") if i.strip()
}

# Who proactive reminders (Basaglar, colírio) are sent to — the patient, not every
# allowed user. Falls back to the sole allowed id if only one is configured.
_patient_id_raw = os.environ.get("PATIENT_TELEGRAM_ID", "")
PATIENT_TELEGRAM_ID = (
    int(_patient_id_raw)
    if _patient_id_raw
    else (next(iter(ALLOWED_TELEGRAM_IDS)) if len(ALLOWED_TELEGRAM_IDS) == 1 else None)
)

# App data lives in Railway Postgres. Locally use the public connection string;
# on Railway the internal DATABASE_URL is injected automatically.
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Gemini — parses free-text Telegram messages into structured events.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# Supabase Auth — Google SSO for the dashboard. No app data lives here.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Only these emails may sign in to the dashboard. Set via env only — never hardcode
# real emails here, this file is committed to the repo.
ALLOWED_EMAILS = {
    e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()
}

# Signs the login session cookie. Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SESSION_SECRET = os.environ.get("SESSION_SECRET", "")

IS_PRODUCTION = bool(os.environ.get("RAILWAY_ENVIRONMENT"))

PATIENT_NAME = os.environ.get("PATIENT_NAME", "Glauber Machado")
TIMEZONE = os.environ.get("TIMEZONE", "America/Sao_Paulo")
TZ = ZoneInfo(TIMEZONE)

BASAGLAR_TIME = os.environ.get("BASAGLAR_TIME", "21:00")
COLIRIO_TIMES = _times(os.environ.get("COLIRIO_TIMES", "08:00,14:00,20:00"))
COLIRIO_PRODUCT = os.environ.get("COLIRIO_PRODUCT", "binadeprosto")

PORT = int(os.environ.get("PORT", "8000"))
