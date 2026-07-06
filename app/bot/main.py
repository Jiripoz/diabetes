"""Telegram bot: button-driven logging for Glauber, in Portuguese (BR).

Run with: python -m app.bot.main
"""
from __future__ import annotations

import logging
from datetime import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .. import config, db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
log = logging.getLogger("bot")

# Per-chat scratch state for the multi-step Humalog flow: {chat_id: pending_units}
_PENDING: dict[int, float] = {}

MEAL_TAGS = [
    ("Café", "cafe"),
    ("Almoço", "almoco"),
    ("Janta", "janta"),
    ("Lanche", "lanche"),
    ("Correção", "correcao"),
]


def _authorized(update: Update) -> bool:
    if config.ALLOWED_TELEGRAM_ID is None:
        return True  # open during early POC if no id configured yet
    user = update.effective_user
    return user is not None and user.id == config.ALLOWED_TELEGRAM_ID


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💉 Humalog", callback_data="menu:humalog")],
            [InlineKeyboardButton("🩸 Glicemia", callback_data="menu:glicemia")],
            [InlineKeyboardButton("🌙 Basaglar (21h)", callback_data="basal:taken")],
            [InlineKeyboardButton("👁 Colírio", callback_data="colirio:ambos")],
        ]
    )


def humalog_units_kb(units: float) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➖2", callback_data="hu:dec"),
                InlineKeyboardButton(f"{units:g}u", callback_data="noop"),
                InlineKeyboardButton("➕2", callback_data="hu:inc"),
            ],
            [InlineKeyboardButton("Confirmar ➡️ escolher refeição", callback_data="hu:next")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")],
        ]
    )


def meal_kb() -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(lbl, callback_data=f"hu:meal:{tag}")] for lbl, tag in MEAL_TAGS]
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


def glicemia_kb() -> InlineKeyboardMarkup:
    # quick presets; free-typed number also accepted via message handler
    presets = [70, 90, 110, 130, 160, 200, 250, 300]
    rows, row = [], []
    for v in presets:
        row.append(InlineKeyboardButton(str(v), callback_data=f"gl:{v}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu:home")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        await update.message.reply_text("Desculpe, este bot é privado.")
        return
    await update.message.reply_text(
        f"Olá {config.PATIENT_NAME.split()[0]}! O que vamos registrar?",
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
    if data in ("menu:home",):
        await q.edit_message_text("O que vamos registrar?", reply_markup=main_menu())
        return

    if data == "menu:humalog":
        _PENDING[chat_id] = 8.0
        await q.edit_message_text("Humalog — ajuste as unidades:", reply_markup=humalog_units_kb(8.0))
        return
    if data.startswith("hu:"):
        await _handle_humalog(q, chat_id, data)
        return

    if data == "menu:glicemia":
        await q.edit_message_text(
            "Glicemia (mg/dL) — toque num valor ou digite o número:",
            reply_markup=glicemia_kb(),
        )
        return
    if data.startswith("gl:"):
        mg = int(data.split(":")[1])
        db.log_glucose(mg)
        await q.edit_message_text(f"✅ Glicemia {mg} mg/dL registrada.", reply_markup=main_menu())
        return

    if data == "basal:taken":
        db.log_basal(status="taken")
        await q.edit_message_text("✅ Basaglar registrada. Boa noite! 🌙", reply_markup=main_menu())
        return

    if data.startswith("colirio:"):
        eye = data.split(":")[1]
        db.log_colirio(eye=eye)
        await q.edit_message_text(
            f"✅ Colírio ({config.COLIRIO_PRODUCT}) registrado.", reply_markup=main_menu()
        )
        return


async def _handle_humalog(q, chat_id: int, data: str) -> None:
    units = _PENDING.get(chat_id, 8.0)
    if data == "hu:dec":
        units = max(0.0, units - 2)
        _PENDING[chat_id] = units
        await q.edit_message_reply_markup(reply_markup=humalog_units_kb(units))
    elif data == "hu:inc":
        units += 2
        _PENDING[chat_id] = units
        await q.edit_message_reply_markup(reply_markup=humalog_units_kb(units))
    elif data == "hu:next":
        await q.edit_message_text(f"Humalog {units:g}u — qual refeição?", reply_markup=meal_kb())
    elif data.startswith("hu:meal:"):
        tag = data.split(":")[2]
        db.log_humalog(units=units, meal_tag=tag)
        _PENDING.pop(chat_id, None)
        label = next((l for l, t in MEAL_TAGS if t == tag), tag)
        await q.edit_message_text(
            f"✅ Humalog {units:g}u ({label}) registrado.", reply_markup=main_menu()
        )


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """A bare number is treated as a glicemia reading — quick capture."""
    if not _authorized(update):
        return
    txt = (update.message.text or "").strip()
    if txt.isdigit() and 10 <= int(txt) <= 900:
        db.log_glucose(int(txt))
        await update.message.reply_text(
            f"✅ Glicemia {txt} mg/dL registrada.", reply_markup=main_menu()
        )
    else:
        await update.message.reply_text("Use os botões para registrar:", reply_markup=main_menu())


# ---- Reminders (JobQueue) ----

async def remind_basaglar(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if config.ALLOWED_TELEGRAM_ID:
        await ctx.bot.send_message(
            config.ALLOWED_TELEGRAM_ID,
            "🌙 Hora da Basaglar (21h). Já tomou?",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ Tomei", callback_data="basal:taken")]]
            ),
        )


async def remind_colirio(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if config.ALLOWED_TELEGRAM_ID:
        await ctx.bot.send_message(
            config.ALLOWED_TELEGRAM_ID,
            f"👁 Hora do colírio ({config.COLIRIO_PRODUCT}).",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ Apliquei", callback_data="colirio:ambos")]]
            ),
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
    from telegram.ext import MessageHandler, filters

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
