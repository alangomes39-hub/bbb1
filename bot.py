import os
import logging
import aiosqlite
from datetime import datetime, date
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIG
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "5067341383"))

DB_FILE = "database.db"
WEBHOOK_PATH = "/webhook"

PIX_CODE = "https://livepix.gg/proletariado"
LAUNCH_DATE_2026 = date(2026, 1, 2)

# =====================================================
# LOG
# =====================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

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
            status TEXT,
            is_2026 INTEGER,
            created_at TEXT
        )
        """)
        await db.commit()

async def create_order(user, lang, product, is_2026):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO orders
            (user_id, username, language, product, status, is_2026, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            user.id,
            user.username,
            lang,
            product,
            "pending",
            1 if is_2026 else 0,
            datetime.utcnow().isoformat()
        ))
        await db.commit()

async def approve_order(order_id):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status='approved' WHERE id=?",
            (order_id,)
        )
        await db.commit()

async def get_last_order():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 1")
        return await cur.fetchone()

async def get_2026_buyers():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("""
            SELECT user_id, language, product
            FROM orders
            WHERE is_2026=1 AND status='approved'
        """)
        return await cur.fetchall()

# =====================================================
# TEXTOS
# =====================================================

TEXT_PT = """🎉 PROMOÇÃO IMPERDÍVEL 🎉

💎 Premium — R$120 (✅ Acesso imediato)
🌟 2024/2025 — R$60 (✅ Acesso imediato)
🌍 Russas (Eastern Europe) — R$45 (✅ Acesso imediato)
🌏 Filipinas — R$40 (✅ Acesso imediato)
⏳ Acervo 2019–2021 — R$50 (✅ Acesso imediato)
🤖 Pacote Completo — R$150 (✅ Acesso imediato)

🔥🔥 NOVOS CANAIS 2026 🔥🔥

🇧🇷 Brasil 2026  
Valor normal: R$85  
🎁 Pré-venda: R$40  

📆 Canal 2026  
Valor normal: R$75  
🎁 Pré-venda: R$30  

⚠️ ATENÇÃO:
Acesso liberado SOMENTE em 02/01/2026.
"""

TEXT_EN = """🎉 UNMISSABLE PROMOTION 🎉

💎 Premium — $50 (✅ Instant access)
🌟 2024/2025 — $45 (✅ Instant access)
🌍 Eastern Europe — $35 (✅ Instant access)
🌏 Philippines — $30 (✅ Instant access)
⏳ Archive — $25 (✅ Instant access)
🤖 Full Package — $60 (✅ Instant access)

🔥🔥 NEW 2026 CHANNELS 🔥🔥

🇧🇷 Brazil 2026  
Regular price: $55  
🎁 Pre-sale: $30  

📆 Channel 2026  
Regular price: $55  
🎁 Pre-sale: $30  

⚠️ IMPORTANT:
Access will be released ONLY on 01/02/2026.
"""

# =====================================================
# BOT HANDLERS
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
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

    text = TEXT_PT if lang == "pt" else TEXT_EN

    if lang == "pt":
        kb = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Russas", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Filipinas", callback_data="buy_philippines")],
            [InlineKeyboardButton("⏳ Acervo", callback_data="buy_archive")],
            [InlineKeyboardButton("🤖 Pacote Completo", callback_data="buy_package")],
            [InlineKeyboardButton("🇧🇷 Brasil 2026 (Pré)", callback_data="buy_brasil2026")],
            [InlineKeyboardButton("📆 Canal 2026 (Pré)", callback_data="buy_2026")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Eastern Europe", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Philippines", callback_data="buy_philippines")],
            [InlineKeyboardButton("⏳ Archive", callback_data="buy_archive")],
            [InlineKeyboardButton("🤖 Full Package", callback_data="buy_package")],
            [InlineKeyboardButton("🇧🇷 Brazil 2026 (Pre)", callback_data="buy_brasil2026")],
            [InlineKeyboardButton("📆 Channel 2026 (Pre)", callback_data="buy_2026")],
        ]

    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    products = {
        "buy_premium": ("Premium", False),
        "buy_2025": ("2024/2025", False),
        "buy_russian": ("Eastern Europe", False),
        "buy_philippines": ("Philippines", False),
        "buy_archive": ("Archive", False),
        "buy_package": ("Full Package", False),
        "buy_brasil2026": ("Brazil 2026", True),
        "buy_2026": ("Channel 2026", True),
    }

    product, is_2026 = products[q.data]
    await create_order(user, lang, product, is_2026)

    context.user_data["awaiting_proof"] = True

    if lang == "pt":
        msg = f"""💳 PAGAMENTO VIA PIX
{PIX_CODE}

📎 Envie o comprovante.

🔍 A revisão pode levar até 2 horas.
Caso ultrapasse esse prazo, fale com o suporte:
👉 @proletariado

🙏 Obrigado pela confiança! Você é muito importante para nós 💙
"""
    else:
        msg = f"""💳 PAYMENT VIA PIX
{PIX_CODE}

📎 Please send your payment proof.

🔍 Review may take up to 2 hours.
If it takes longer, contact support:
👉 @proletariado

🙏 Thank you for your trust! You are very important to us 💙
"""

    await q.message.reply_text(msg)

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user
    lang = context.user_data.get("lang", "pt")

    if lang == "pt":
        await update.message.reply_text(
            "✅ Comprovante recebido!\n\n🔍 Seu pedido está em revisão.\n⏳ Pode levar até 2 horas."
        )
    else:
        await update.message.reply_text(
            "✅ Proof received!\n\n🔍 Your order is under review.\n⏳ It may take up to 2 hours."
        )

    await application.bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 Novo comprovante recebido de @{user.username or user.id}"
    )

# =====================================================
# NOTIFICAÇÃO 2026
# =====================================================

async def notify_2026(context: ContextTypes.DEFAULT_TYPE):
    buyers = await get_2026_buyers()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        "🚀 Hoje é 02/01/2026! Liberar links dos canais 2026."
    )

    for uid, lang, product in buyers:
        if lang == "pt":
            msg = f"🎉 O canal {product} foi liberado! Entre em contato para receber o link."
        else:
            msg = f"🎉 The {product} channel is now live! Contact support to receive your link."

        await context.bot.send_message(uid, msg)

# =====================================================
# FASTAPI + LIFESPAN
# =====================================================

application: Application | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global application

    await init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof))

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)

    if application.job_queue:
        application.job_queue.run_once(
            notify_2026,
            when=datetime(2026, 1, 2, 0, 5)
        )

    yield

    await application.stop()
    await application.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}
