"""FastAPI dashboard. Run with: uvicorn app.web.main:app --reload"""
from __future__ import annotations

from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .. import config, db

BASE = Path(__file__).parent
app = FastAPI(title="Diabetes Tracker")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

if not config.SESSION_SECRET:
    raise RuntimeError("SESSION_SECRET not configured")
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET,
    same_site="lax",
    https_only=config.IS_PRODUCTION,
    max_age=60 * 60 * 24 * 30,  # 30 days
)


def _session_email(request: Request) -> str | None:
    email = request.session.get("email")
    return email if email in config.ALLOWED_EMAILS else None


def require_auth(request: Request) -> str:
    """Session gate for API routes: signed in via Google SSO with an allowed email."""
    email = _session_email(request)
    if email is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autorizado")
    return email


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "supabase_url": config.SUPABASE_URL,
            "supabase_anon_key": config.SUPABASE_ANON_KEY,
        },
    )


@app.get("/auth/callback")
def auth_callback_page(request: Request):
    return templates.TemplateResponse(
        "auth_callback.html",
        {
            "request": request,
            "supabase_url": config.SUPABASE_URL,
            "supabase_anon_key": config.SUPABASE_ANON_KEY,
        },
    )


@app.post("/auth/callback")
async def auth_callback(request: Request) -> dict:
    body = await request.json()
    access_token = body.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token ausente")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={"Authorization": f"Bearer {access_token}", "apikey": config.SUPABASE_ANON_KEY},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token inválido")

    email = (resp.json().get("email") or "").strip().lower()
    if email not in config.ALLOWED_EMAILS:
        raise HTTPException(status_code=403, detail="Este e-mail não tem acesso ao painel")

    request.session["email"] = email
    return {"ok": True}


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


@app.get("/api/data")
def data(_: str = Depends(require_auth)) -> dict:
    # FastAPI encodes datetime -> ISO string and Decimal -> number automatically.
    return {
        "humalog": db.recent("humalog_doses", "taken_at", limit=500),
        "meals": db.recent("meals", "eaten_at", limit=500),
        "basal": db.recent("basal_doses", "taken_at", limit=500),
        "glucose": db.recent("glucose_readings", "measured_at", limit=500),
        "colirio": db.recent("colirio_uses", "used_at", limit=500),
    }


@app.get("/")
def dashboard(request: Request):
    email = _session_email(request)
    if email is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "patient": config.PATIENT_NAME},
    )
