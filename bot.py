import os
import logging
import aiosqlite
from datetime import datetime, date
from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://bbb1-production.up.railway.app
WEBHOOK_PATH = "/webhook"
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "5067341383"))

DB_FILE = "database.db"

# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# =========================================================
# FASTAPI
# =========================================================

app = FastAPI()
tg_app: Application | None = None

# =========================================================
# DATABASE
# =========================================================

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            language TEXT,
            product TEXT,
            payment_method TEXT,
            status TEXT,
            created_at TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS buyers_2026 (
            user_id INTEGER,
            username TEXT,
            product TEXT,
            language TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

# =========================================================
# TEXTS
# =========================================================

TEXT_PT = """🎉 Promoção Imperdível! 🎉

💎 Grupo Premium — R$120
🌟 Grupo 2024/2025 — R$60
🌍 Russas — R$45
🌏 Filipinas — R$40
⏳ Acervo 2019–2021 — R$50
🤖 Pacote 2022–2025 — R$150

🆕 *NOVOS CANAIS 2026*  
🇧🇷 Brasil 2026 — R$85  
📆 Canal 2026 — R$75  

⚠️ *Aviso:*  
Acesso liberado apenas em **02/01/2026**  
🎁 Comprando agora:
• Brasil 2026 → **R$40**
• Canal 2026 → **R$30**
"""

TEXT_EN = """🎉 Unmissable Promotion! 🎉

💎 Premium — $50
🌟 2024/2025 — $45
🌍 Russian — $35
🌏 Philippines — $30
⏳ Old Content — $25
🤖 Package — $60

🆕 *NEW 2026 CHANNELS*
🇧🇷 Brazil 2026 — $55
📆 Channel 2026 — $55

⚠️ *Notice:*  
Access only on **January 2, 2026**  
🎁 Pre-sale price:
• Brazil 2026 → **$30**
• Channel 2026 → **$30**
"""

PIX_CODE = "https://livepix.gg/proletariado"

# =========================================================
# HANDLERS
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "Escolha seu idioma / Choose your language:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.replace("lang_", "")
    context.user_data["lang"] = lang

    if lang == "pt":
        await q.message.reply_text(TEXT_PT, parse_mode="Markdown")
        await q.message.reply_text(
            "💳 Pagar com PIX",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Pagar via PIX", callback_data="pay_pix")]
            ])
        )
    else:
        await q.message.reply_text(TEXT_EN, parse_mode="Markdown")
        await q.message.reply_text(
            "💳 Payment options",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay", callback_data="pay_crypto")]
            ])
        )

async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    context.user_data["awaiting_proof"] = True

    if context.user_data.get("lang") == "pt":
        await q.message.reply_text(
            f"💳 PIX:\n{PIX_CODE}\n\nEnvie o comprovante."
        )
    else:
        await q.message.reply_text(
            "Send your payment proof."
        )

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO orders (user_id, username, language, product, payment_method, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                user.id,
                user.username,
                context.user_data.get("lang"),
                "purchase",
                "pix",
                "proof_received",
                datetime.utcnow().isoformat()
            )
        )
        await db.commit()

    await update.message.reply_text(
        "✅ Comprovante recebido! Aguarde confirmação."
        if context.user_data.get("lang") == "pt"
        else "✅ Proof received! Please wait."
    )

    await tg_app.bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 Novo comprovante de @{user.username or user.id}"
    )

# =========================================================
# ADMIN REMINDER 02/01/2026
# =========================================================

async def check_2026_reminder():
    if date.today() == date(2026, 1, 2):
        await tg_app.bot.send_message(
            ADMIN_CHAT_ID,
            "📅 Hoje é 02/01/2026 — liberar acesso dos canais 2026!"
        )

# =========================================================
# FASTAPI LIFESPAN
# =========================================================

@app.on_event("startup")
async def startup():
    global tg_app
    await init_db()

    tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    tg_app.add_handler(CallbackQueryHandler(payment, pattern="^pay_"))
    tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof))

    await tg_app.initialize()
    await tg_app.bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)

    logger.info("✅ Bot iniciado com webhook")

@app.on_event("shutdown")
async def shutdown():
    if tg_app:
        await tg_app.shutdown()

@app.post(WEBHOOK_PATH)
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}
