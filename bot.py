import os
import logging
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler

# ===============================
# CONFIG
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = "/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
tg_app: Application | None = None

# ===============================
# TELEGRAM HANDLERS
# ===============================

async def start(update: Update, context):
    await update.message.reply_text("✅ Bot online e funcionando!")

# ===============================
# FASTAPI LIFESPAN
# ===============================

@app.on_event("startup")
async def on_startup():
    global tg_app

    logger.info("🔧 Inicializando bot Telegram...")

    tg_app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    tg_app.add_handler(CommandHandler("start", start))

    await tg_app.initialize()
    await tg_app.bot.set_webhook(
        url=os.getenv("WEBHOOK_URL") + WEBHOOK_PATH
    )

    logger.info("✅ Webhook configurado com sucesso")

@app.on_event("shutdown")
async def on_shutdown():
    if tg_app:
        await tg_app.shutdown()

# ===============================
# WEBHOOK ENDPOINT
# ===============================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    try:
        data = await req.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.exception("Erro no webhook")
        return {"ok": False}
