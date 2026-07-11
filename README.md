# Diabetes Tracker — Glauber Machado (POC)

Telegram bot for logging insulin/glicemia/colírio + a web dashboard.
Stack: **Python** (python-telegram-bot + FastAPI), **Supabase** (Postgres), **Railway**.

```
Glauber → Telegram bot (buttons) → Supabase ← FastAPI dashboard (website)
                 ↑ reminders (Basaglar 21h, colírio)
```

## What it does (POC)
- **Humalog:** button stepper (units) → meal tag → saved.
- **Glicemia:** preset buttons or just type a number.
- **Basaglar:** one-tap confirm; reminder at 21:00.
- **Colírio:** one-tap log; reminders at configured times.
- **Dashboard:** glicemia chart, KPIs, recent doses/events (pt-BR).

## Local setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in tokens/keys
# create schema in Supabase SQL editor:
#   paste db/schema.sql and run
```

Run the two processes (separate terminals):
```bash
python -m app.bot.main                         # Telegram bot
uvicorn app.web.main:app --reload              # dashboard at http://localhost:8000
```

## Deploy to Railway
1. Push this repo to GitHub.
2. In Railway, create a project from the repo. Add **two services** from the same repo:
   - **web** — start command: `uvicorn app.web.main:app --host 0.0.0.0 --port $PORT`
   - **bot** — start command: `python -m app.bot.main`
3. Set the env vars from `.env.example` on **both** services.
4. The `web` service gets a public URL (the dashboard). The `bot` runs as a worker.

## Environment variables
See `.env.example`. `TELEGRAM_BOT_TOKEN` and `SESSION_SECRET` are server-side only — never exposed to the browser.
`SUPABASE_ANON_KEY` is the public anon key and is safe to expose client-side.

## Dashboard login (Google SSO via Supabase)
The dashboard requires Google sign-in through Supabase Auth, restricted to the emails in
`ALLOWED_EMAILS`. One-time setup in the Supabase dashboard:
1. Authentication → Providers → enable **Google**, with a Client ID/Secret from a Google Cloud
   OAuth consent screen (Web application type).
2. Authentication → URL Configuration → add the dashboard's `/auth/callback` URL (both the
   Railway URL and `http://localhost:8000` for local dev) to **Redirect URLs**.
