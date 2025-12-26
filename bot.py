import os
import asyncio
import aiosqlite
from datetime import datetime, date

from fastapi import FastAPI, Request
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes,
    CommandHandler, CallbackQueryHandler, MessageHandler, filters
)

# ======================================================
# CONFIGURAÇÕES
# ======================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # https://xxxxx.up.railway.app
DB_FILE = "database.db"

RELEASE_DATE_2026 = date(2026, 1, 2)

app = FastAPI()
tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ======================================================
# BANCO DE DADOS
# ======================================================

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

# ======================================================
# TEXTOS
# ======================================================

TEXT_PT = (
    "🎉 *Promoção Imperdível!* 🎉\n\n"
    "💎 Premium — R$120\n"
    "🌟 2024/2025 — R$60\n"
    "🌍 Russas — R$45\n"
    "🌏 Filipinas — R$40\n"
    "🌍 Eastern Europe — R$45\n"
    "⏳ Acervo 2019–2021 — R$50\n"
    "🤖 Pacote 2022–2025 — R$150\n\n"
    "🆕 *PRÉ-VENDA 2026*\n"
    "🇧🇷 Brasil 2026 — R$85 (🔥 agora R$40)\n"
    "🌎 Canal 2026 — R$75 (🔥 agora R$30)\n\n"
    "⚠️ *Acesso liberado somente em 02/01/2026*\n"
    "Garantindo agora você paga mais barato."
)

TEXT_EN = (
    "🎉 *Unmissable Promotion!* 🎉\n\n"
    "💎 Premium — $50\n"
    "🌟 2024/2025 — $45\n"
    "🌍 Russian — $35\n"
    "🌏 Philippines — $30\n"
    "🌍 Eastern Europe — $35\n"
    "⏳ Old Content — $25\n"
    "🤖 Package — $60\n\n"
    "🆕 *2026 PRE-SALE*\n"
    "🇧🇷 Brazil 2026 — $55 (🔥 now $30)\n"
    "🌎 Channel 2026 — $55 (🔥 now $30)\n\n"
    "⚠️ *Access available only on Jan 2, 2026*"
)

# ======================================================
# START
# ======================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ])
    await update.message.reply_text(
        "Escolha seu idioma / Choose your language:",
        reply_markup=kb
    )

# ======================================================
# IDIOMA
# ======================================================

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.split("_")[1]
    context.user_data["lang"] = lang

    text = TEXT_PT if lang == "pt" else TEXT_EN

    buttons = [
        ["Premium", "2024/2025"],
        ["Russas", "Filipinas"],
        ["Eastern Europe", "Acervo"],
        ["Pacote"],
        ["Brasil 2026", "Canal 2026"]
    ]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(b, callback_data=f"product_{b}")]
        if len(row) == 1 else
        [InlineKeyboardButton(row[0], callback_data=f"product_{row[0]}"),
         InlineKeyboardButton(row[1], callback_data=f"product_{row[1]}")]
        for row in buttons
    ])

    await q.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

# ======================================================
# PRODUTO
# ======================================================

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    product = q.data.replace("product_", "")
    context.user_data["product"] = product
    lang = context.user_data.get("lang", "pt")

    is_2026 = product in ["Brasil 2026", "Canal 2026"]
    context.user_data["is_2026"] = is_2026

    pay_buttons = (
        [
            [InlineKeyboardButton("💳 Pix", callback_data="pay_pix")],
            [InlineKeyboardButton("📞 Suporte", url="https://t.me/proletariado")]
        ] if lang == "pt" else
        [
            [InlineKeyboardButton("Wise", callback_data="pay_wise")],
            [InlineKeyboardButton("Skrill", callback_data="pay_skrill")],
            [InlineKeyboardButton("Binance", callback_data="pay_binance")],
            [InlineKeyboardButton("Bitcoin", callback_data="pay_btc")]
        ]
    )

    await q.message.reply_text(
        f"📦 *Produto selecionado:* {product}\n\nEscolha o pagamento:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(pay_buttons)
    )

# ======================================================
# PAGAMENTO
# ======================================================

async def payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    method = q.data.replace("pay_", "")
    user = q.from_user

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            INSERT INTO orders
            (user_id, username, language, product, payment_method, status, is_2026, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username,
                context.user_data["lang"],
                context.user_data["product"],
                method,
                "pending",
                1 if context.user_data.get("is_2026") else 0,
                datetime.utcnow().isoformat()
            )
        )
        await db.commit()

    codes = {
        "pix": "https://livepix.gg/proletariado",
        "wise": "lanzinhoster@gmail.com",
        "skrill": "alan_t.t.i@hotmail.com",
        "binance": "TKsUrqmP2sgfHUXL4jPL8CFJCvs9taGwxY (TRX)",
        "btc": "13ct8pSdWBcGwGLgM4SdB38rEkixMM69H7"
    }

    await q.message.reply_text(
        f"💳 *Pagamento ({method.upper()})*\n\n"
        f"`{codes.get(method)}`\n\n"
        "📸 Envie o comprovante aqui.",
        parse_mode="Markdown"
    )

# ======================================================
# COMPROVANTE
# ======================================================

async def proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status=? WHERE user_id=? ORDER BY id DESC LIMIT 1",
            ("proof_received", user.id)
        )
        await db.commit()

    await update.message.reply_text("✅ Comprovante recebido. Aguarde a verificação.")

    await tg_app.bot.copy_message(
        ADMIN_CHAT_ID,
        update.message.chat_id,
        update.message.message_id
    )

# ======================================================
# WEBHOOK
# ======================================================

@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

# ======================================================
# STARTUP
# ======================================================

@app.on_event("startup")
async def startup():
    await init_db()
    await tg_app.initialize()
    await tg_app.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

# ======================================================
# HANDLERS
# ======================================================

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
tg_app.add_handler(CallbackQueryHandler(choose_product, pattern="^product_"))
tg_app.add_handler(CallbackQueryHandler(payment, pattern="^pay_"))
tg_app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, proof))
