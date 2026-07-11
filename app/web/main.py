"""FastAPI dashboard. Run with: uvicorn app.web.main:app --reload"""
from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import config, db

BASE = Path(__file__).parent
app = FastAPI(title="Diabetes Tracker")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

_security = HTTPBasic()


def require_auth(creds: HTTPBasicCredentials = Depends(_security)) -> str:
    """Basic-auth gate for the dashboard. Refuses to serve if no password is set."""
    if not config.DASHBOARD_PASSWORD:
        raise HTTPException(status_code=500, detail="DASHBOARD_PASSWORD not configured")
    user_ok = secrets.compare_digest(creds.username, config.DASHBOARD_USER)
    pass_ok = secrets.compare_digest(creds.password, config.DASHBOARD_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autorizado",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username


@app.get("/health")
def health() -> dict:
    return {"ok": True}


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
def dashboard(request: Request, _: str = Depends(require_auth)):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "patient": config.PATIENT_NAME},
    )
