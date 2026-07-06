"""Minimal Gemini agent: free-text Telegram message -> structured events -> DB.

Glauber writes naturally ("almocei arroz, feijão e frango e apliquei 10 de
humalog"). Gemini classifies each event, estimates meal macros (carbs/protein)
from the food description, and we route each to the right table.
"""
from __future__ import annotations

import json
import logging

from google import genai
from google.genai import types

from . import config, db

log = logging.getLogger("agent")

SYSTEM = """Você é o assistente de registro do Glauber, diabético tipo 1 (pt-BR).
A partir da mensagem dele, extraia UM OU MAIS eventos. Tipos:

- "humalog": dose de insulina rápida (Humalog), em unidades. reason: "refeicao" (dose de refeição) ou "correcao" (corrigir glicemia alta) ou "outro".
- "meal": comida ingerida. ESTIME carbs_g e protein_g (gramas) a partir da descrição usando conhecimento nutricional para porções brasileiras típicas. meal_tag: cafe|almoco|janta|lanche. description: resumo curto do prato.
- "glucose": glicemia em mg/dL (mg_dl). context: jejum|pre_refeicao|pos_refeicao|dormir|outro.
- "basal": Basaglar (insulina basal). units se mencionado.
- "colirio": colírio nos olhos. eye: od|oe|ambos (padrão ambos).

Regras:
- Uma refeição e a dose de insulina são eventos SEPARADOS — gere os dois quando ambos aparecerem.
- Estime macros com bom senso (ex.: 1 concha de arroz ~28g carbs; 1 filé de frango ~30g proteína).
- confirm_pt: frase curta de confirmação em português para o usuário (ex.: "Almoço: 68g carbs, 35g proteína").
- Se não houver nada registrável, retorne events vazio."""

SCHEMA = {
    "type": "object",
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["humalog", "meal", "glucose", "basal", "colirio", "unknown"]},
                    "units": {"type": "number"},
                    "reason": {"type": "string", "enum": ["refeicao", "correcao", "outro"]},
                    "carbs_g": {"type": "integer"},
                    "protein_g": {"type": "integer"},
                    "meal_tag": {"type": "string", "enum": ["cafe", "almoco", "janta", "lanche"]},
                    "description": {"type": "string"},
                    "mg_dl": {"type": "integer"},
                    "context": {"type": "string", "enum": ["jejum", "pre_refeicao", "pos_refeicao", "dormir", "outro"]},
                    "eye": {"type": "string", "enum": ["od", "oe", "ambos"]},
                    "confirm_pt": {"type": "string"},
                },
                "required": ["type", "confirm_pt"],
            },
        }
    },
    "required": ["events"],
}

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def interpret(text: str) -> list[dict]:
    resp = client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=text,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0.2,
        ),
    )
    data = json.loads(resp.text or "{}")
    return data.get("events", [])


def _save(e: dict) -> str | None:
    """Route one event to the right table. Returns a confirmation or None."""
    t = e.get("type")
    if t == "humalog" and e.get("units") is not None:
        db.log_humalog(units=float(e["units"]), reason=e.get("reason"))
    elif t == "meal":
        db.log_meal(carbs_g=e.get("carbs_g"), protein_g=e.get("protein_g"),
                    meal_tag=e.get("meal_tag"), description=e.get("description"))
    elif t == "glucose" and e.get("mg_dl") is not None:
        db.log_glucose(int(e["mg_dl"]), context=e.get("context"))
    elif t == "basal":
        db.log_basal(status="taken", units=e.get("units"))
    elif t == "colirio":
        db.log_colirio(eye=e.get("eye") or "ambos")
    else:
        return None
    return e.get("confirm_pt") or f"{t} registrado"


def handle(text: str) -> str:
    """Interpret a message and persist its events. Returns a pt-BR reply."""
    try:
        events = interpret(text)
    except Exception:
        log.exception("gemini interpret failed")
        return "Tive um problema ao entender 😕 tente de novo em instantes."

    confirms = []
    for e in events:
        try:
            c = _save(e)
            if c:
                confirms.append(c)
        except Exception:
            log.exception("failed to save event %s", e)

    if not confirms:
        return ("Não identifiquei um registro 🤔\n"
                "Ex.: \"almocei arroz, feijão e frango e apliquei 10 de humalog\", "
                "\"glicemia 140\", \"tomei a basaglar\".")
    return "✅ " + "\n✅ ".join(confirms)
