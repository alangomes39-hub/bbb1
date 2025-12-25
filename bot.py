import os
import logging
import aiosqlite
from datetime import datetime, time, date

from fastapi import FastAPI, Request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)

# =====================================================
# CONFIG
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

DB_FILE = "bot_database.db"

PIX_LINK = "https://livepix.gg/proletariado"

# =====================================================
# LOG
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# =====================================================
# FASTAPI + TELEGRAM
# =====================================================

app = FastAPI()
tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

# =====================================================
# TEXTOS
# =====================================================

TEXT_PT_LISTA = """🎉 Promoção Imperdível! 🎉

💎 Grupo Premium — R$120  
🌟 Grupo 2024/2025 — R$60  
🌍 Russas — R$45  
🌏 Filipinas — R$40  
⏳ Acervo 2019–2021 — R$50  
🤖 Pacote 2022–2025 — R$150  

🆕 *NOVOS CANAIS (ACESSO A PARTIR DE 02/01/2026)*  
🇧🇷 Brasil 2026 — R$85 *(promo: R$40)*  
📆 Canal 2026 — R$75 *(promo: R$30)*  
"""

TEXT_PT_VIP = """🔥 CANAL VIP SÓ BRASILEIRAS — R$80  

⚠️ *Canais 2026 serão liberados em 02/01/2026*  
"""

TEXT_EN = """🎉 Unmissable Promotion! 🎉

💎 Premium — $50  
🌟 2024/2025 — $45  
🌍 Russian — $35  
🌏 Philippines — $30  
⏳ Old Content — $25  
🤖 Package — $60  

🆕 *NEW CHANNELS (ACCESS FROM 01/02/2026)*  
🇧🇷 Brazil 2026 — $30  
📆 Channel 2026 — $55  
"""

# =====================================================
# DATABASE
# =====================================================

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
        await db.commit()

async def save_order(user, lang, product, method):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        INSERT INTO orders
        (user_id, username, language, product, payment_method, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            lang,
            product,
            method,
            "pending",
            datetime.utcnow().isoformat()
        ))
        await db.commit()

# =====================================================
# START / LANGUAGE
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "Escolha sua língua / Choose your language:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    lang = q.data.replace("lang_", "")
    context.user_data["lang"] = lang
    await q.answer()

    if lang == "pt":
        await q.message.reply_text(TEXT_PT_LISTA, parse_mode="Markdown")
        await q.message.reply_text(TEXT_PT_VIP, parse_mode="Markdown")
        kb = [
            [InlineKeyboardButton("💳 Pagar com Pix", callback_data="pay_pix")],
            [InlineKeyboardButton("📞 Suporte", callback_data="support")]
        ]
    else:
        await q.message.reply_text(TEXT_EN, parse_mode="Markdown")
        kb = [
            [InlineKeyboardButton("💸 Wise", callback_data="pay_wise")],
            [InlineKeyboardButton("💳 Skrill", callback_data="pay_skrill")],
            [InlineKeyboardButton("🪙 Binance", callback_data="pay_binance")],
            [InlineKeyboardButton("₿ Bitcoin", callback_data="pay_btc")],
            [InlineKeyboardButton("📞 Support", callback_data="support")]
        ]

    await q.message.reply_text(
        "Escolha uma opção:" if lang == "pt" else "Choose an option:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =====================================================
# PAYMENT
# =====================================================

async def payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user = q.from_user
    lang = context.user_data.get("lang", "pt")
    method = q.data.replace("pay_", "")

    await q.answer()

    if q.data == "support":
        await q.message.reply_text("@proletariado")
        return

    await save_order(user, lang, "manual", method)
    context.user_data["awaiting_proof"] = True

    if method == "pix":
        await q.message.reply_text(
            f"💳 PIX:\n{PIX_LINK}\n\nEnvie o comprovante.",
            disable_web_page_preview=True
        )
    else:
        await q.message.reply_text("Send payment proof.")

# =====================================================
# PROOF
# =====================================================

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    lang = context.user_data.get("lang", "pt")

    msg = (
        "✅ Comprovante recebido. Aguarde aprovação."
        if lang == "pt"
        else
        "✅ Proof received. Please wait."
    )

    await update.message.reply_text(msg)

    await context.bot.copy_message(
        chat_id=ADMIN_CHAT_ID,
        from_chat_id=update.message.chat_id,
        message_id=update.message.message_id
    )

# =====================================================
# JOB — AVISO 02/01/2026
# =====================================================

async def aviso_2026(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        ADMIN_CHAT_ID,
        "🚨 HOJE (02/01/2026): liberar acesso aos canais 2026"
    )

tg_app.job_queue.run_daily(
    aviso_2026,
    time=time(9, 0),
    days=(0,1,2,3,4,5,6),
    name="aviso_2026"
)

# =====================================================
# HANDLERS
# =====================================================

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
tg_app.add_handler(CallbackQueryHandler(payment_handler, pattern="^(pay_|support)"))
tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof))

# =====================================================
# WEBHOOK
# =====================================================

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.on_event("startup")
async def startup():
    await init_db()
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    logger.info("Webhook configurado")

@app.on_event("shutdown")
async def shutdown():
    await tg_app.shutdown()
