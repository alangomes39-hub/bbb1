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

async def update_status(order_id, status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id)
        )
        await db.commit()

async def get_order(order_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cur.fetchone()

async def get_last_order_by_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
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

💎 Premium — R$120  
🌟 2024/2025 — R$60  
🌍 Russas — R$45  
🌏 Filipinas — R$40  
🤖 Pacote Completo — R$150  

🔥🔥 NOVOS CANAIS 2026 🔥🔥

🇧🇷 Brasil 2026  
Valor normal: R$85  
🎁 Pré-venda: R$40  

📆 Canal 2026  
Valor normal: R$75  
🎁 Pré-venda: R$30  

⚠️ ATENÇÃO:
Acesso liberado SOMENTE em 02/01/2026.
Comprando agora você garante a vaga
no valor promocional.
"""

TEXT_EN = """🎉 UNMISSABLE PROMOTION 🎉

💎 Premium — $50  
🌟 2024/2025 — $45  
🌍 Russian — $35  
🌏 Philippines — $30  
🤖 Full Package — $60  

🔥🔥 NEW 2026 CHANNELS 🔥🔥

🇧🇷 Brazil 2026  
Regular price: $55  
🎁 Pre-sale: $30  

📆 Channel 2026  
Regular price: $55  
🎁 Pre-sale: $30  

⚠️ IMPORTANT:
Access will be released ONLY on 01/02/2026.
Buying now guarantees your spot
at the promotional price.
"""

# =====================================================
# START / LANGUAGE
# =====================================================

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

    text = TEXT_PT if lang == "pt" else TEXT_EN

    kb = [
        [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
        [InlineKeyboardButton("🌍 Russas", callback_data="buy_russas")],
        [InlineKeyboardButton("🌏 Filipinas", callback_data="buy_filipinas")],
        [InlineKeyboardButton("🤖 Pacote Completo", callback_data="buy_pacote")],
        [InlineKeyboardButton("🇧🇷 Brasil 2026 (Pré)", callback_data="buy_brasil2026")],
        [InlineKeyboardButton("📆 Canal 2026 (Pré)", callback_data="buy_2026")]
    ]

    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

# =====================================================
# BUY FLOW
# =====================================================

PRODUCTS = {
    "buy_premium": ("Premium", False),
    "buy_2025": ("2024/2025", False),
    "buy_russas": ("Russas", False),
    "buy_filipinas": ("Filipinas", False),
    "buy_pacote": ("Pacote Completo", False),
    "buy_brasil2026": ("Brasil 2026", True),
    "buy_2026": ("Canal 2026", True),
}

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    product, is_2026 = PRODUCTS[q.data]
    await create_order(user, lang, product, is_2026)
    context.user_data["awaiting_proof"] = True

    msg = (
        f"💳 PIX:\n{PIX_CODE}\n\nEnvie o comprovante."
        if lang == "pt"
        else "💳 Payment method:\nSend your payment proof."
    )

    await q.message.reply_text(msg)

# =====================================================
# RECEIVE PROOF
# =====================================================

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user

    order = await get_last_order_by_user(user.id)

    await update.message.reply_text(
        "✅ Comprovante recebido! Aguarde a verificação."
        if context.user_data.get("lang") == "pt"
        else "✅ Proof received! Please wait."
    )

    if order:
        await send_admin_panel(context, order[0])

# =====================================================
# ADMIN PANEL
# =====================================================

def format_admin(order):
    (
        oid, uid, username, lang,
        product, status, is_2026, created
    ) = order

    return (
        f"<b>📦 PEDIDO #{oid}</b>\n\n"
        f"<b>User ID:</b> {uid}\n"
        f"<b>Username:</b> @{username or 'sem'}\n"
        f"<b>Idioma:</b> {lang}\n"
        f"<b>Produto:</b> {product}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>2026:</b> {'SIM' if is_2026 else 'NÃO'}\n"
        f"<b>Data:</b> {created}"
    )

async def send_admin_panel(context, order_id):
    order = await get_order(order_id)
    if not order:
        return

    kb = [
        [
            InlineKeyboardButton("✅ Aprovar", callback_data=f"admin_approve_{order_id}"),
            InlineKeyboardButton("❌ Rejeitar", callback_data=f"admin_reject_{order_id}")
        ],
        [InlineKeyboardButton("📤 Enviar link", callback_data=f"admin_send_{order_id}")]
    ]

    if order[6] == 1:
        kb.append(
            [InlineKeyboardButton("🟣 Pedido 2026", callback_data=f"admin_2026_{order_id}")]
        )

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        format_admin(order),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    q = update.callback_query
    await q.answer()

    action, oid = q.data.rsplit("_", 1)
    oid = int(oid)
    order = await get_order(oid)

    if not order:
        return

    uid = order[1]
    lang = order[3]

    if action == "admin_approve":
        await update_status(oid, "approved")
        await q.message.reply_text("✅ Pedido aprovado.")

    elif action == "admin_reject":
        await update_status(oid, "rejected")
        msg = (
            "❌ Pagamento rejeitado."
            if lang == "pt"
            else "❌ Payment rejected."
        )
        await context.bot.send_message(uid, msg)
        await q.message.reply_text("❌ Pedido rejeitado.")

    elif action == "admin_send":
        context.user_data["send_link_for"] = oid
        await q.message.reply_text("📤 Envie o link para o cliente:")

    elif action == "admin_2026":
        await q.message.reply_text(
            "🟣 Cliente com acesso antecipado 2026.\n"
            "Será notificado automaticamente em 02/01/2026."
        )

async def admin_send_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    oid = context.user_data.get("send_link_for")
    if not oid:
        return

    order = await get_order(oid)
    if not order:
        return

    uid = order[1]
    lang = order[3]
    link = update.message.text.strip()

    msg = (
        f"🎉 Pagamento aprovado!\n👉 {link}"
        if lang == "pt"
        else f"🎉 Payment approved!\n👉 {link}"
    )

    await context.bot.send_message(uid, msg)
    await update_status(oid, "delivered")
    await update.message.reply_text("✅ Link enviado.")
    context.user_data["send_link_for"] = None

# =====================================================
# 2026 NOTIFICATION
# =====================================================

async def notify_2026(context: ContextTypes.DEFAULT_TYPE):
    buyers = await get_2026_buyers()

    await context.bot.send_message(
        ADMIN_CHAT_ID,
        "🚀 Hoje é 02/01/2026! Libere os canais 2026."
    )

    for uid, lang, product in buyers:
        msg = (
            f"🎉 O canal {product} foi liberado!"
            if lang == "pt"
            else f"🎉 The {product} channel is now live!"
        )
        await context.bot.send_message(uid, msg)

# =====================================================
# FASTAPI / WEBHOOK
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
    application.add_handler(CallbackQueryHandler(admin_callbacks, pattern="^admin_"))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_link)
    )

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
