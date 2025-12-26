import os
import logging
import aiosqlite
from datetime import datetime
from contextlib import asynccontextmanager

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

# =====================================================
# CONFIG
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://bbb1-production.up.railway.app
WEBHOOK_PATH = "/webhook"
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "5067341383"))
DB_FILE = "database.db"

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
            payment_method TEXT,
            status TEXT,
            created_at TEXT
        )
        """)
        await db.commit()

async def create_order(user, lang, method):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO orders (user_id, username, language, payment_method, status, created_at) VALUES (?,?,?,?,?,?)",
            (
                user.id,
                user.username,
                lang,
                method,
                "pending",
                datetime.utcnow().isoformat()
            )
        )
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
        cur = await db.execute(
            "SELECT * FROM orders WHERE id=?",
            (order_id,)
        )
        return await cur.fetchone()

async def update_status(order_id, status):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE id=?",
            (status, order_id)
        )
        await db.commit()

async def list_orders():
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute(
            "SELECT id, user_id, username, payment_method, status, created_at FROM orders ORDER BY id DESC LIMIT 20"
        )
        return await cur.fetchall()

# =====================================================
# TEXTOS
# =====================================================

TEXT_PT = "💳 PIX:\nhttps://livepix.gg/proletariado\n\nEnvie o comprovante."
TEXT_EN = "Send your payment proof."

# =====================================================
# BOT HANDLERS
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

    kb = [[InlineKeyboardButton("💳 Pagar", callback_data="pay")]]

    await q.message.reply_text(
        TEXT_PT if lang == "pt" else TEXT_EN,
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    await create_order(user, lang, "pix")
    context.user_data["awaiting_proof"] = True

    await q.message.reply_text(TEXT_PT if lang == "pt" else TEXT_EN)

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user
    order = await get_last_order(user.id)

    await update.message.reply_text(
        "✅ Comprovante recebido! Aguarde."
        if context.user_data.get("lang") == "pt"
        else "✅ Proof received! Please wait."
    )

    kb = [[InlineKeyboardButton(
        "🔍 Abrir painel do pedido",
        callback_data=f"admin_panel_{order[0]}"
    )]]

    await application.bot.send_message(
        ADMIN_CHAT_ID,
        f"📩 Novo comprovante\nPedido #{order[0]}\nUsuário: @{user.username}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await application.bot.copy_message(
        ADMIN_CHAT_ID,
        update.message.chat_id,
        update.message.message_id
    )

# =====================================================
# ADMIN PANEL
# =====================================================

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_CHAT_ID:
        return

    _, action, oid = q.data.split("_")
    oid = int(oid)
    order = await get_order(oid)

    if not order:
        await q.message.reply_text("Pedido não encontrado.")
        return

    if action == "panel":
        kb = [
            [InlineKeyboardButton("✅ Aprovar", callback_data=f"admin_approve_{oid}")],
            [InlineKeyboardButton("❌ Rejeitar", callback_data=f"admin_reject_{oid}")],
            [InlineKeyboardButton("📤 Enviar link", callback_data=f"admin_send_{oid}")]
        ]
        await q.message.reply_text(
            f"📦 Pedido #{oid}\nStatus: {order[5]}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    elif action == "approve":
        await update_status(oid, "approved")
        await q.message.reply_text("Pagamento aprovado. Envie o link.")
        context.user_data["send_link"] = oid

    elif action == "reject":
        await update_status(oid, "rejected")
        await application.bot.send_message(
            order[1],
            "❌ Pagamento rejeitado."
        )

    elif action == "send":
        context.user_data["send_link"] = oid
        await q.message.reply_text("Envie o link agora.")

async def admin_send_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    oid = context.user_data.get("send_link")
    if not oid:
        return

    order = await get_order(oid)
    link = update.message.text

    await application.bot.send_message(
        order[1],
        f"🎉 Pagamento aprovado!\n\nAqui está seu link:\n{link}"
    )

    await update_status(oid, "delivered")
    await update.message.reply_text("✅ Link enviado.")
    context.user_data["send_link"] = None

async def admin_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    rows = await list_orders()
    text = "📊 Últimos pedidos:\n\n"

    for r in rows:
        text += f"#{r[0]} | @{r[2]} | {r[3]} | {r[4]}\n"

    await update.message.reply_text(text)

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
    application.add_handler(CommandHandler("admin_history", admin_history))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(pay, pattern="^pay$"))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    application.add_handler(
        MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_link)
    )

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL + WEBHOOK_PATH)

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
