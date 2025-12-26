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
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://bbb1-production.up.railway.app
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
            payment_method TEXT,
            status TEXT,
            is_2026 INTEGER,
            created_at TEXT
        )
        """)
        await db.commit()

async def create_order(user, lang, product, payment_method, is_2026):
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
            payment_method,
            "pending",
            1 if is_2026 else 0,
            datetime.utcnow().isoformat()
        ))
        await db.commit()

async def update_status(order_id, status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id)
        )
        await db.commit()

async def get_last_order_by_user(user_id):
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

💎 Premium — R$120 (acesso imediato)
🌟 2024/2025 — R$60 (acesso imediato)
🌍 Russas — R$45 (acesso imediato)
🌏 Filipinas — R$40 (acesso imediato)
⏳ Acervo — R$50 (acesso imediato)
🤖 Pacote — R$150 (acesso imediato)

🔥🔥 NOVOS CANAIS 2026 🔥🔥

🇧🇷 Brasil 2026
Pré-venda: R$40
Após lançamento: R$85

📆 Canal 2026
Pré-venda: R$30
Após lançamento: R$75

⚠️ Acesso aos canais 2026 somente em 02/01/2026.
"""

TEXT_EN = """🎉 UNMISSABLE PROMOTION 🎉

💎 Premium — $50 (instant access)
🌟 2024/2025 — $45 (instant access)
🌍 Eastern Europe — $35 (instant access)
🌏 Philippines — $30 (instant access)
⏳ Old Content — $25 (instant access)
🤖 Package — $60 (instant access)

🔥🔥 NEW 2026 CHANNEL 🔥🔥

📆 Channel 2026
Pre-sale: $30
After launch: $55

⚠️ Access will be released only on 01/02/2026.
"""

# =====================================================
# ADMIN PANEL
# =====================================================

def format_admin_panel(order):
    (
        oid, user_id, username, lang, product,
        payment_method, status, is_2026, created_at
    ) = order

    return (
        f"User ID: {user_id}\n"
        f"Username: @{username if username else 'sem_username'}\n"
        f"Idioma: {lang}\n"
        f"Produto: {product}\n"
        f"Método: {payment_method}\n"
        f"Status: {status}\n"
        f"2026: {'SIM' if is_2026 else 'NÃO'}\n"
        f"Data: {created_at}"
    )

async def send_admin_panel(application, order):
    oid = order[0]
    text = format_admin_panel(order)

    buttons = [
        [
            InlineKeyboardButton("✅ Aprovar", callback_data=f"admin_approve_{oid}"),
            InlineKeyboardButton("❌ Rejeitar", callback_data=f"admin_reject_{oid}")
        ],
        [InlineKeyboardButton("📤 Enviar link", callback_data=f"admin_send_{oid}")]
    ]

    if order[7] == 1:
        buttons.append([InlineKeyboardButton("🟣 Pedido 2026", callback_data="noop")])

    await application.bot.send_message(
        ADMIN_CHAT_ID,
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

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
            [InlineKeyboardButton("🌍 Russas", callback_data="buy_russas")],
            [InlineKeyboardButton("🌏 Filipinas", callback_data="buy_filipinas")],
            [InlineKeyboardButton("⏳ Acervo", callback_data="buy_acervo")],
            [InlineKeyboardButton("🤖 Pacote", callback_data="buy_pacote")],
            [InlineKeyboardButton("🇧🇷 Brasil 2026 (Pré)", callback_data="buy_brasil2026")],
            [InlineKeyboardButton("📆 Canal 2026 (Pré)", callback_data="buy_2026")],
        ]
    else:
        kb = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Eastern Europe", callback_data="buy_europe")],
            [InlineKeyboardButton("🌏 Philippines", callback_data="buy_filipinas")],
            [InlineKeyboardButton("⏳ Old Content", callback_data="buy_acervo")],
            [InlineKeyboardButton("🤖 Package", callback_data="buy_pacote")],
            [InlineKeyboardButton("📆 Channel 2026 (Pre)", callback_data="buy_2026")],
        ]

    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    product_map = {
        "buy_premium": ("Premium", False),
        "buy_2025": ("2024/2025", False),
        "buy_russas": ("Russas", False),
        "buy_filipinas": ("Filipinas", False),
        "buy_europe": ("Eastern Europe", False),
        "buy_acervo": ("Acervo", False),
        "buy_pacote": ("Pacote", False),
        "buy_brasil2026": ("Brasil 2026", True),
        "buy_2026": ("Canal 2026", True),
    }

    product, is_2026 = product_map[q.data]
    context.user_data["selected_product"] = product
    context.user_data["is_2026"] = is_2026

    if lang == "pt":
        kb = [[InlineKeyboardButton("💳 Pagar com PIX", callback_data="pay_pix")]]
    else:
        kb = [
            [InlineKeyboardButton("💸 Wise", callback_data="pay_wise")],
            [InlineKeyboardButton("💳 Skrill", callback_data="pay_skrill")],
            [InlineKeyboardButton("₿ Bitcoin", callback_data="pay_btc")],
            [InlineKeyboardButton("🪙 Binance USDT (TRX)", callback_data="pay_binance")],
        ]

    await q.message.reply_text(
        "Escolha o método de pagamento:" if lang == "pt" else "Choose payment method:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def choose_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    method = q.data.replace("pay_", "")
    product = context.user_data["selected_product"]
    is_2026 = context.user_data["is_2026"]

    await create_order(user, lang, product, method, is_2026)
    context.user_data["awaiting_proof"] = True

    if lang == "pt":
        msg = f"💳 PIX:\n{PIX_CODE}\n\nEnvie o comprovante."
    else:
        msg = "Send your payment proof."

    await q.message.reply_text(msg)

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user
    lang = context.user_data.get("lang", "pt")

    order = await get_last_order_by_user(user.id)
    await send_admin_panel(application, order)

    if lang == "pt":
        msg = (
            "✅ Comprovante recebido.\n\n"
            "A revisão pode levar até 2 horas.\n"
            "Caso ultrapasse esse prazo, entre em contato com @proletariado.\n\n"
            "Agradecemos pela sua compra."
        )
    else:
        msg = (
            "✅ Payment proof received.\n\n"
            "The review may take up to 2 hours.\n"
            "If it exceeds this time, please contact @proletariado.\n\n"
            "Thank you for your purchase."
        )

    await update.message.reply_text(msg)

# =====================================================
# ADMIN ACTIONS
# =====================================================

async def admin_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_CHAT_ID:
        return

    action, oid = q.data.split("_", 1)
    order = await get_order(int(oid))

    if action == "admin_approve":
        await update_status(int(oid), "approved")
        await q.message.reply_text("✅ Pedido aprovado.")
    elif action == "admin_reject":
        await update_status(int(oid), "rejected")
        await q.message.reply_text("❌ Pedido rejeitado.")
    elif action == "admin_send":
        context.user_data["send_link_to"] = order[1]
        await q.message.reply_text("📤 Envie o link para o cliente:")

async def admin_send_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    uid = context.user_data.get("send_link_to")
    if not uid:
        return

    await application.bot.send_message(uid, update.message.text)
    await update.message.reply_text("✅ Link enviado.")
    context.user_data["send_link_to"] = None

# =====================================================
# 2026 NOTIFICATION
# =====================================================

async def notify_2026(context: ContextTypes.DEFAULT_TYPE):
    buyers = await get_2026_buyers()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        "🚀 Hoje é 02/01/2026. Libere os links dos canais 2026."
    )

    for uid, lang, product in buyers:
        msg = (
            f"O canal {product} foi liberado. Entre em contato para receber o link."
            if lang == "pt"
            else f"The {product} channel is now available. Please contact support."
        )
        await context.bot.send_message(uid, msg)

# =====================================================
# FASTAPI + WEBHOOK
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
    application.add_handler(CallbackQueryHandler(choose_payment, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_actions, pattern="^admin_"))
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
