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

async def get_order(order_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        return await cur.fetchone()

async def get_last_order_for_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cur = await db.execute("""
            SELECT * FROM orders
            WHERE user_id=?
            ORDER BY id DESC LIMIT 1
        """, (user_id,))
        return await cur.fetchone()

# =====================================================
# TEXTOS
# =====================================================

TEXT_PT = """🎉 PROMOÇÃO IMPERDÍVEL 🎉

💎 Premium — R$135 (acesso imediato)  
🌟 2024/2025 — R$160 (acesso imediato)  
🌍 Russas — R$55 (acesso imediato)  
🌏 Filipinas — R$50 (acesso imediato)  
⏳ Acervo — R$65 (acesso imediato)  
🤖 Pacote — R$180 (acesso imediato)  
🇧🇷 Brasil 2025 — R$190 (acesso imediato) 
🆕 CANAIS 2026

🇧🇷 Brasil 2026 — R$85  
📆 Canal 2026 — R$75  

📌 INFORMAÇÕES IMPORTANTES:
• Os canais 2026 estão oficialmente liberados  
• Acesso conforme aprovação do pagamento  
• Grupos (exceto pacote e os canais 2026) possuem acesso vitalício
"""


TEXT_EN = """🎉 UNMISSABLE PROMOTION 🎉

💎 Premium — $50 (instant access)  
🌟 2024/2025 — $90 (instant access)  
🌍 Eastern Europe — $40 (instant access)  
🌏 Philippines — $35 (instant access)  
⏳ Archive — $30 (instant access)  
🤖 Package — $70 (instant access)  

🆕 2026 CHANNEL

📆 Channel 2026 — $55  

📌 IMPORTANT INFORMATION:
• 2026 channel is officially released  
• Access is granted after payment approval  
• All groups (except package and the 2026 channel) include lifetime access
"""


# =====================================================
# START
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

# =====================================================
# LANGUAGE
# =====================================================

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    lang = q.data.replace("lang_", "")
    context.user_data["lang"] = lang

    text = TEXT_PT if lang == "pt" else TEXT_EN

    buttons = [
        [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
        [InlineKeyboardButton("🌍 Russas" if lang == "pt" else "🌍 Eastern Europe", callback_data="buy_russia")],
        [InlineKeyboardButton("🌏 Filipinas" if lang == "pt" else "🌍 Philippines", callback_data="buy_ph")],
        [InlineKeyboardButton("🇧🇷 Brasil 2025", callback_data="buy_brasil2025")],
        [InlineKeyboardButton("⏳ Acervo" if lang == "pt" else "⏳ Archive", callback_data="buy_archive")],
        [InlineKeyboardButton("🤖 Pacote" if lang == "pt" else "🤖 Package", callback_data="buy_package")],
        [InlineKeyboardButton("📆 Channel 2026", callback_data="buy_2026")],
    ]

    if lang == "pt":
        buttons.insert(6, [InlineKeyboardButton("🇧🇷 Brasil 2026", callback_data="buy_brasil2026")])

    await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# =====================================================
# BUY
# =====================================================

PRODUCTS = {
    "buy_premium": ("Premium", False),
    "buy_2025": ("2024/2025", False),
    "buy_russia": ("Russas", False),
    "buy_ph": ("Filipinas", False),
    "buy_archive": ("Acervo", False),
    "buy_package": ("Pacote", False),
    "buy_brasil2026": ("Brasil 2026", True),
    "buy_2026": ("Canal 2026", True),
    "buy_brasil2025": ("Brasil 2025", False),
}

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user = q.from_user
    lang = context.user_data.get("lang", "pt")

    product, is_2026 = PRODUCTS[q.data]
    await create_order(user, lang, product, is_2026)
    context.user_data["awaiting_proof"] = True

    if lang == "pt":
        await q.message.reply_text(
            f"💳 PIX\n{PIX_CODE}\n\n"
            "📌 Envie o comprovante.\n\n"
            "⏳ A revisão pode levar até 2 horas.\n"
            "Caso ultrapasse esse prazo, entre em contato com @proletariado.\n\n"
            "Obrigado pela preferência."
        )
    else:
        kb = [
            [InlineKeyboardButton("💸 Wise", callback_data="pay_wise")],
            [InlineKeyboardButton("💳 Skrill", callback_data="pay_skrill")],
            [InlineKeyboardButton("🪙 Binance USDT TRX", callback_data="pay_binance")],
            [InlineKeyboardButton("₿ Bitcoin", callback_data="pay_btc")],
        ]
        await q.message.reply_text(
            "Choose a payment method:",
            reply_markup=InlineKeyboardMarkup(kb)
        )

# =====================================================
# PAYMENT METHODS EN
# =====================================================

async def payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    methods = {
        "pay_wise": "lanzinhoster@gmail.com",
        "pay_skrill": "alan_t.t.i@hotmail.com",
        "pay_binance": "USDT TRX\nTKsUrqmP2sgfHUXL4jPL8CFJCvs9taGwxY",
        "pay_btc": "Bitcoin\n13ct8pSdWBcGwGLgM4SdB38rEkixMM69H7",
    }

    await q.message.reply_text(
        f"{methods[q.data]}\n\n"
        "📌 Send payment proof.\n\n"
        "⏳ Review may take up to 2 hours.\n"
        "If it exceeds this time, contact @proletariado.\n\n"
        "Thank you."
    )

    context.user_data["awaiting_proof"] = True

# =====================================================
# RECEIVE PROOF + ADMIN PANEL
# =====================================================

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_proof"):
        return

    context.user_data["awaiting_proof"] = False
    user = update.effective_user
    order = await get_last_order_for_user(user.id)

    # ✅ envia confirmação ao cliente
    if order:
        if order[3] == "pt":
            await update.message.reply_text(
                "✅ Comprovante recebido com sucesso.\n\n"
                "⏳ Seu pedido está em análise.\n"
                "Por favor, aguarde."
            )
        else:
            await update.message.reply_text(
                "✅ Payment proof received successfully.\n\n"
                "⏳ Your order is under review.\n"
                "Please wait."
            )

    # ✅ ENVIA O COMPROVANTE PARA O ADMIN (como antes)
    if update.message.photo:
        await application.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=update.message.photo[-1].file_id,
            caption="📎 Comprovante enviado pelo cliente"
        )
    elif update.message.document:
        await application.bot.send_document(
            chat_id=ADMIN_CHAT_ID,
            document=update.message.document.file_id,
            caption="📎 Comprovante enviado pelo cliente"
        )

    panel = (
        f"User ID: {order[1]}\n"
        f"Username: @{order[2]}\n"
        f"Idioma: {order[3]}\n"
        f"Produto: {order[4]}\n"
        f"Status: {order[5]}\n"
        f"2026: {'SIM' if order[6] else 'NÃO'}\n"
        f"Data: {order[7]}"
    )

    kb = [
        [
            InlineKeyboardButton("✅ Aprovar", callback_data=f"admin_approve_{order[0]}"),
            InlineKeyboardButton("❌ Rejeitar", callback_data=f"admin_reject_{order[0]}"),
        ],
        [InlineKeyboardButton("📤 Enviar link", callback_data=f"admin_send_{order[0]}")],
    ]

    if order[6]:
        kb.append([InlineKeyboardButton("🟣 Pedido 2026", callback_data=f"admin_2026_{order[0]}")])

    await application.bot.send_message(
        ADMIN_CHAT_ID,
        panel,
        reply_markup=InlineKeyboardMarkup(kb)
    )

# =====================================================
# ADMIN CALLBACK
# =====================================================

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.from_user.id != ADMIN_CHAT_ID:
        return

    _, action, oid = q.data.split("_")
    oid = int(oid)

    order = await get_order(oid)
    uid = order[1]
    lang = order[3]

    if action == "approve":
        await approve_order(oid)
        context.user_data["awaiting_link"] = uid
        await q.message.reply_text("✅ Pedido aprovado.")

    elif action == "reject":
        msg = (
            "❌ Seu pagamento não foi aprovado. Contate @proletariado."
            if lang == "pt"
            else "❌ Your payment was not approved. Contact @proletariado."
        )
        await application.bot.send_message(uid, msg)
        await q.message.reply_text("❌ Pedido rejeitado.")

    elif action == "send":
        context.user_data["awaiting_link"] = uid
        await q.message.reply_text("📤 Envie o link para o cliente.")

    elif action == "2026":
        await q.message.reply_text("🟣 Pedido identificado como PRÉ-VENDA 2026.")

# =====================================================
# RECEIVE ADMIN LINK
# =====================================================

async def receive_admin_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    uid = context.user_data.get("awaiting_link")
    if not uid:
        return

    link = update.message.text

    await application.bot.send_message(
        chat_id=uid,
        text=f"✅ Pedido aprovado!\n\n🔗 Acesso:\n{link}"
    )

    context.user_data.pop("awaiting_link", None)
    await update.message.reply_text("✅ Link enviado com sucesso.")

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
    application.add_handler(CallbackQueryHandler(payment_methods, pattern="^pay_"))
    application.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^admin_"))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, receive_proof))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_admin_link))

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
