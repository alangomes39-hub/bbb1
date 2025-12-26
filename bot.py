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

# ================= CONFIG =================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "5067341383"))

DB_FILE = "database.db"
WEBHOOK_PATH = "/webhook"

PIX_CODE = "https://livepix.gg/proletariado"

WISE_EMAIL = "lanzinhoster@gmail.com"
SKRILL_EMAIL = "alan_t.t.i@hotmail.com"
BINANCE_TRX = "TKsUrqmP2sgfHUXL4jPL8CFJCvs9taGwxY"
BTC_ADDRESS = "13ct8pSdWBcGwGLgM4SdB38rEkixMM69H7"

LAUNCH_DATE_2026 = date(2026, 1, 2)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")

# ================= DATABASE =================

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
            is_2026 INTEGER,
            created_at TEXT
        )
        """)
        await db.commit()

async def create_order(user, lang, product, payment, is_2026):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        INSERT INTO orders
        (user_id, username, language, product, payment_method, status, is_2026, created_at)
        VALUES (?,?,?,?,?,?,?,?)
        """, (
            user.id,
            user.username,
            lang,
            product,
            payment,
            "pending",
            1 if is_2026 else 0,
            datetime.utcnow().isoformat()
        ))
        await db.commit()

async def get_last_order(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        return await cur.fetchone()

async def get_order(order_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cur.fetchone()

async def update_order_status(order_id, status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id)
        )
        await db.commit()

async def get_2026_orders():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("""
        SELECT user_id, language, product
        FROM orders
        WHERE is_2026=1 AND status='approved'
        """)
        return await cur.fetchall()

# ================= TEXTOS =================

TEXT_PT = """🎉 PROMOÇÃO IMPERDÍVEL 🎉

💎 Premium — R$120 (Acesso imediato)
🌟 2024/2025 — R$60 (Acesso imediato)
🌍 Russas — R$45 (Acesso imediato)
🌏 Filipinas — R$40 (Acesso imediato)
⏳ Acervo — R$50 (Acesso imediato)
🤖 Pacote Completo — R$150 (Acesso imediato)

🔥 NOVOS CANAIS 2026 🔥
🇧🇷 Brasil 2026 — Pré-venda R$40
📆 Canal 2026 — Pré-venda R$30

⚠️ Acesso somente em 02/01/2026
"""

TEXT_EN = """🎉 UNMISSABLE PROMOTION 🎉

💎 Premium — $50 (Instant access)
🌟 2024/2025 — $45 (Instant access)
🌍 Eastern Europe — $35 (Instant access)
🌏 Philippines — $30 (Instant access)
⏳ Archive — $25 (Instant access)
🤖 Full Package — $60 (Instant access)

🔥 NEW 2026 CHANNEL 🔥
📆 Channel 2026 — Pre-sale $30

⚠️ Access only on 01/02/2026
"""

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
    ]
    await update.message.reply_text(
        "Escolha seu idioma / Choose your language:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= LANGUAGE =================

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    lang = q.data.replace("lang_", "")
    context.user_data["lang"] = lang

    if lang == "pt":
        kb = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Russas", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Filipinas", callback_data="buy_philippines")],
            [InlineKeyboardButton("⏳ Acervo", callback_data="buy_archive")],
            [InlineKeyboardButton("🤖 Pacote Completo", callback_data="buy_package")],
            [InlineKeyboardButton("🇧🇷 Brasil 2026", callback_data="buy_brasil2026")],
            [InlineKeyboardButton("📆 Canal 2026", callback_data="buy_2026")],
        ]
        await q.message.reply_text(TEXT_PT, reply_markup=InlineKeyboardMarkup(kb))
    else:
        kb = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Eastern Europe", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Philippines", callback_data="buy_philippines")],
            [InlineKeyboardButton("⏳ Archive", callback_data="buy_archive")],
            [InlineKeyboardButton("🤖 Full Package", callback_data="buy_package")],
            [InlineKeyboardButton("📆 Channel 2026", callback_data="buy_2026")],
        ]
        await q.message.reply_text(TEXT_EN, reply_markup=InlineKeyboardMarkup(kb))

# ================= BUY =================

PRODUCTS = {
    "buy_premium": ("Premium", False),
    "buy_2025": ("2024/2025", False),
    "buy_russian": ("Eastern Europe", False),
    "buy_philippines": ("Philippines", False),
    "buy_archive": ("Archive", False),
    "buy_package": ("Full Package", False),
    "buy_brasil2026": ("Brasil 2026", True),
    "buy_2026": ("Channel 2026", True),
}

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    product, is_2026 = PRODUCTS[q.data]
    context.user_data["pending_product"] = (product, is_2026)

    if lang == "pt":
        await q.message.reply_text(
            f"💳 PIX\n{PIX_CODE}\n\nEnvie o comprovante."
        )
        context.user_data["payment"] = "PIX"
    else:
        kb = [
            [InlineKeyboardButton("Wise", callback_data="pay_wise")],
            [InlineKeyboardButton("Skrill", callback_data="pay_skrill")],
            [InlineKeyboardButton("Binance USDT (TRX)", callback_data="pay_binance")],
            [InlineKeyboardButton("Bitcoin", callback_data="pay_btc")],
        ]
        await q.message.reply_text(
            "Choose a payment method:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# ================= PAY METHODS =================

async def pay_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    methods = {
        "pay_wise": f"Wise: {WISE_EMAIL}",
        "pay_skrill": f"Skrill: {SKRILL_EMAIL}",
        "pay_binance": f"Binance USDT (TRX): {BINANCE_TRX}",
        "pay_btc": f"Bitcoin: {BTC_ADDRESS}",
    }

    context.user_data["payment"] = q.data.replace("pay_", "").upper()

    await q.message.reply_text(
        f"{methods[q.data]}\n\nSend your payment proof."
    )

# ================= RECEIVE PROOF =================

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = context.user_data.get("lang", "pt")

    product, is_2026 = context.user_data["pending_product"]
    payment = context.user_data.get("payment")

    await create_order(user, lang, product, payment, is_2026)

    if lang == "pt":
        msg = (
            "✅ Comprovante recebido.\n\n"
            "A revisão pode levar até 2 horas.\n"
            "Caso ultrapasse esse prazo, entre em contato com @proletariado.\n\n"
            "Obrigado pela sua compra."
        )
    else:
        msg = (
            "✅ Proof received.\n\n"
            "The review may take up to 2 hours.\n"
            "If it takes longer, contact @proletariado.\n\n"
            "Thank you for your purchase."
        )

    await update.message.reply_text(msg)

    order = await get_last_order(user.id)
    oid = order[0]

    kb = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_{oid}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{oid}")],
        [InlineKeyboardButton("📤 Send link", callback_data=f"admin_send_{oid}")]
    ]

    await application.bot.send_message(
        ADMIN_CHAT_ID,
        f"📦 New order #{oid}\nUser: @{user.username}\nProduct: {product}\nPayment: {payment}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await application.bot.copy_message(
        ADMIN_CHAT_ID,
        update.message.chat_id,
        update.message.message_id
    )

# ================= ADMIN PANEL =================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    _, action, oid = q.data.split("_")
    oid = int(oid)

    order = await get_order(oid)
    uid = order[1]
    lang = order[3]

    if action == "approve":
        await update_order_status(oid, "approved")
        await q.message.reply_text("✅ Order approved.")
    elif action == "reject":
        await update_order_status(oid, "rejected")
        await application.bot.send_message(
            uid,
            "❌ Payment rejected. Contact support."
        )
        await q.message.reply_text("❌ Order rejected.")
    elif action == "send":
        context.user_data["send_link"] = oid
        await q.message.reply_text("Send the access link:")

async def admin_send_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "send_link" not in context.user_data:
        return

    oid = context.user_data.pop("send_link")
    order = await get_order(oid)
    uid = order[1]

    await application.bot.send_message(
        uid,
        f"🔗 Access link:\n{update.message.text}"
    )

    await update_order_status(oid, "delivered")
    await update.message.reply_text("✅ Link sent.")

# ================= NOTIFY 2026 =================

async def notify_2026(context: ContextTypes.DEFAULT_TYPE):
    orders = await get_2026_orders()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        "🚀 Today is 02/01/2026. Release the 2026 channels."
    )

    for uid, lang, product in orders:
        msg = (
            f"The channel {product} is now available."
            if lang == "en"
            else f"O canal {product} já está disponível."
        )
        await context.bot.send_message(uid, msg)

# ================= FASTAPI =================

application: Application | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global application

    await init_db()

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    application.add_handler(CallbackQueryHandler(pay_method, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_link))

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
