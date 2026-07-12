"""Telegram bot: button-driven logging for Glauber, in Portuguese (BR).

Humalog (insulin) and meals (carbs+protein) are separate events.
Run with: python -m app.bot.main
"""
from __future__ import annotations

import asyncio
import logging
from datetime import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .. import agent, config, db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("bot")

# Per-chat scratch state for multi-step flows.
_STATE: dict[int, dict] = {}

MEAL_TAGS = [("Café", "cafe"), ("Almoço", "almoco"), ("Janta", "janta"), ("Lanche", "lanche")]
REASONS = [("🍽 Refeição", "refeicao"), ("🩹 Correção", "correcao")]


def _authorized(update: Update) -> bool:
    if not config.ALLOWED_TELEGRAM_IDS:
        return True
    user = update.effective_user
    if user is not None and user.id in config.ALLOWED_TELEGRAM_IDS:
        return True
    if user is not None:
        log.warning("rejected caller: id=%s username=%s name=%s", user.id, user.username, user.full_name)
    return False


def _st(chat_id: int) -> dict:
    return _STATE.setdefault(chat_id, {})


# ---------- keyboards ----------

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💉 Humalog", callback_data="menu:humalog"),
             InlineKeyboardButton("🍽 Refeição", callback_data="menu:refeicao")],
            [InlineKeyboardButton("🩸 Glicemia", callback_data="menu:glicemia")],
            [InlineKeyboardButton("🌙 Basaglar (21h)", callback_data="basal:taken"),
             InlineKeyboardButton("👁 Colírio", callback_data="colirio:ambos")],
        ]
    )


def stepper_kb(value, prefix: str, step, unit: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"➖{step:g}", callback_data=f"{prefix}:dec"),
                InlineKeyboardButton(f"{value:g}{unit}", callback_data="noop"),
                InlineKeyboardButton(f"➕{step:g}", callback_data=f"{prefix}:inc"),
            ],
            [InlineKeyboardButton("Continuar ➡️", callback_data=f"{prefix}:next")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")],
        ]
    )


def reason_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(lbl, callback_data=f"hu:save:{r}")] for lbl, r in REASONS]
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def meal_tag_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(lbl, callback_data=f"me:tag:{t}")] for lbl, t in MEAL_TAGS]
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def glicemia_kb() -> InlineKeyboardMarkup:
    presets = [70, 90, 110, 130, 160, 200, 250, 300]
    rows, row = [], []
    for v in presets:
        row.append(InlineKeyboardButton(str(v), callback_data=f"gl:{v}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


# ---------- handlers ----------

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await update.message.reply_text("Desculpe, este bot é privado.")
        return
    await update.message.reply_text(
        f"Olá {config.PATIENT_NAME.split()[0]}! Pode escrever naturalmente "
        "(ex.: \"almocei arroz, feijão e frango e apliquei 10 de humalog\") "
        "ou usar os botões abaixo.",
        reply_markup=main_menu(),
    )


async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    q = update.callback_query
    await q.answer()
    data = q.data
    chat_id = q.message.chat_id

    if data == "noop":
        return
    if data == "menu:home":
        _STATE.pop(chat_id, None)
        await q.edit_message_text("O que vamos registrar?", reply_markup=main_menu())
        return

    # Humalog: units -> reason -> save
    if data == "menu:humalog":
        _st(chat_id)["hu"] = 8.0
        await q.edit_message_text("💉 Humalog — ajuste as unidades:",
                                  reply_markup=stepper_kb(8.0, "hu", 2, "u"))
        return
    if data == "hu:dec" or data == "hu:inc":
        s = _st(chat_id); s["hu"] = max(0.0, s.get("hu", 8.0) + (2 if data == "hu:inc" else -2))
        await q.edit_message_reply_markup(reply_markup=stepper_kb(s["hu"], "hu", 2, "u"))
        return
    if data == "hu:next":
        u = _st(chat_id).get("hu", 8.0)
        await q.edit_message_text(f"💉 Humalog {u:g}u — motivo?", reply_markup=reason_kb())
        return
    if data.startswith("hu:save:"):
        reason = data.split(":")[2]
        u = _st(chat_id).get("hu", 8.0)
        db.log_humalog(units=u, reason=reason)
        _STATE.pop(chat_id, None)
        lbl = next((l for l, r in REASONS if r == reason), reason)
        await q.edit_message_text(f"✅ Humalog {u:g}u registrado ({lbl}).", reply_markup=main_menu())
        return

    # Refeição: carbs -> protein -> tag -> save
    if data == "menu:refeicao":
        _st(chat_id).update({"carbs": 30, "prot": 15})
        await q.edit_message_text("🍽 Refeição — carboidratos (g):",
                                  reply_markup=stepper_kb(30, "car", 10, "g"))
        return
    if data == "car:dec" or data == "car:inc":
        s = _st(chat_id); s["carbs"] = max(0, s.get("carbs", 30) + (10 if data == "car:inc" else -10))
        await q.edit_message_reply_markup(reply_markup=stepper_kb(s["carbs"], "car", 10, "g"))
        return
    if data == "car:next":
        p = _st(chat_id).get("prot", 15)
        await q.edit_message_text("🍽 Agora as proteínas (g):",
                                  reply_markup=stepper_kb(p, "pro", 5, "g"))
        return
    if data == "pro:dec" or data == "pro:inc":
        s = _st(chat_id); s["prot"] = max(0, s.get("prot", 15) + (5 if data == "pro:inc" else -5))
        await q.edit_message_reply_markup(reply_markup=stepper_kb(s["prot"], "pro", 5, "g"))
        return
    if data == "pro:next":
        await q.edit_message_text("🍽 Qual refeição?", reply_markup=meal_tag_kb())
        return
    if data.startswith("me:tag:"):
        tag = data.split(":")[2]
        s = _st(chat_id)
        db.log_meal(carbs_g=s.get("carbs"), protein_g=s.get("prot"), meal_tag=tag)
        _STATE.pop(chat_id, None)
        lbl = next((l for l, t in MEAL_TAGS if t == tag), tag)
        await q.edit_message_text(
            f"✅ {lbl}: {s.get('carbs')}g carbs · {s.get('prot')}g proteína.",
            reply_markup=main_menu(),
        )
        return

    # Glicemia
    if data == "menu:glicemia":
        await q.edit_message_text("🩸 Glicemia (mg/dL) — toque ou digite o número:",
                                  reply_markup=glicemia_kb())
        return
    if data.startswith("gl:"):
        mg = int(data.split(":")[1])
        db.log_glucose(mg)
        await q.edit_message_text(f"✅ Glicemia {mg} mg/dL registrada.", reply_markup=main_menu())
        return

    # Basaglar / Colírio
    if data == "basal:taken":
        db.log_basal(status="taken")
        await q.edit_message_text("✅ Basaglar registrada. Boa noite! 🌙", reply_markup=main_menu())
        return
    if data.startswith("colirio:"):
        db.log_colirio(eye=data.split(":")[1])
        await q.edit_message_text(f"✅ Colírio ({config.COLIRIO_PRODUCT}) registrado.",
                                  reply_markup=main_menu())
        return


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Free text is interpreted by the Gemini agent and saved to the right table."""
    if not _authorized(update):
        return
    txt = (update.message.text or "").strip()
    # Fast path: a bare glucose number, no LLM call needed.
    if txt.isdigit() and 10 <= int(txt) <= 900:
        db.log_glucose(int(txt))
        await update.message.reply_text(f"✅ Glicemia {txt} mg/dL registrada.", reply_markup=main_menu())
        return
    await ctx.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await asyncio.to_thread(agent.handle, txt)
    await update.message.reply_text(reply, reply_markup=main_menu())


# ---------- reminders ----------

async def remind_basaglar(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if config.PATIENT_TELEGRAM_ID:
        await ctx.bot.send_message(
            config.PATIENT_TELEGRAM_ID, "🌙 Hora da Basaglar (21h). Já tomou?",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Tomei", callback_data="basal:taken")]]),
        )


async def remind_colirio(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if config.PATIENT_TELEGRAM_ID:
        await ctx.bot.send_message(
            config.PATIENT_TELEGRAM_ID, f"👁 Hora do colírio ({config.COLIRIO_PRODUCT}).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Apliquei", callback_data="colirio:ambos")]]),
        )


def _parse_hhmm(raw: str) -> time:
    h, m = raw.split(":")
    return time(hour=int(h), minute=int(m), tzinfo=config.TZ)


def schedule_reminders(app: Application) -> None:
    jq = app.job_queue
    jq.run_daily(remind_basaglar, time=_parse_hhmm(config.BASAGLAR_TIME), name="basaglar")
    for i, t in enumerate(config.COLIRIO_TIMES):
        jq.run_daily(remind_colirio, time=_parse_hhmm(t), name=f"colirio-{i}")
    log.info("Reminders scheduled: basaglar=%s colirio=%s", config.BASAGLAR_TIME, config.COLIRIO_TIMES)


def build_app() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", start))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    schedule_reminders(app)
    return app


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN not set")
    app = build_app()
    log.info("Bot starting (polling)…")
    app.run_polling()


if __name__ == "__main__":
    main()
