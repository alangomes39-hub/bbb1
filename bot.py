import os
import logging
import asyncio
import traceback
import aiosqlite
from datetime import datetime, date

from fastapi import FastAPI, Request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "COLOQUE_SEU_TOKEN")
ADMIN_ID = 5067341383
WEBHOOK_URL = "https://bbb1-production.up.railway.app/webhook"
DB_FILE = "database.db"

LAUNCH_DATE_2026 = date(2026, 1, 2)

PIX_CODE = "https://livepix.gg/proletariado"

WISE_EMAIL = "lanzinhoster@gmail.com"
SKRILL_EMAIL = "alan_t.t.i@hotmail.com"
BINANCE_TRX = "TKsUrqmP2sgfHUXL4jPL8CFJCvs9taGwxY"
BTC_ADDRESS = "13ct8pSdWBcGwGLgM4SdB38rEkixMM69H7"

# ==========================================================
# LOGS
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# ==========================================================
# FASTAPI (WEBHOOK)
# ==========================================================

app = FastAPI()
tg_app = ApplicationBuilder().token(BOT_TOKEN).build()

# ==========================================================
# BANCO DE DADOS
# ==========================================================

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            language TEXT,
            product TEXT,
            price TEXT,
            payment_method TEXT,
            status TEXT,
            is_2026 INTEGER,
            created_at TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS presale_2026 (
            user_id INTEGER,
            product TEXT,
            language TEXT
        )
        """)
        await db.commit()

# ==========================================================
# TEXTOS — PORTUGUÊS
# ==========================================================

TEXT_PT_LISTA = """🎉 *Promoção Imperdível!* 🎉

💎 Grupo Premium — R$120  
🌟 Grupo 2024/2025 — R$60  
🌍 Russas — R$45  
🌏 Filipinas — R$40  
🌍 Eastern Europe — R$50  
📦 Pacote de Canais — R$150  
"""

TEXT_PT_VIP = """🔥 *CANAL VIP SÓ BRASILEIRAS* — R$80
"""

TEXT_PT_2026 = """🆕 *NOVIDADE 2026 — PRÉ-VENDA*

🇧🇷 *Brasil 2026*
Preço normal: R$85  
🔥 *Pré-venda*: R$40  

📆 *Canal 2026*
Preço normal: R$75  
🔥 *Pré-venda*: R$30  

⚠️ *Acesso liberado somente em 02/01/2026*
Ao comprar agora, sua vaga fica garantida.
"""

# ==========================================================
# TEXTOS — ENGLISH
# ==========================================================

TEXT_EN_LISTA = """🎉 *Unmissable Promotion!* 🎉

💎 Premium — $50  
🌟 2024/2025 — $45  
🌍 Russian — $35  
🌏 Philippines — $30  
🌍 Eastern Europe — $40  
📦 Channel Package — $60  
"""

TEXT_EN_2026 = """🆕 *2026 PRE-SALE*

🇧🇷 *Brazil 2026*
Regular price: $55  
🔥 *Pre-sale*: $30  

📆 *Channel 2026*
Regular price: $55  
🔥 *Pre-sale*: $30  

⚠️ *Access will be released on January 2, 2026*
"""

# ==========================================================
# PRODUTOS (FONTE ÚNICA)
# ==========================================================

PRODUCTS = {
    "premium": {"pt": "Grupo Premium", "en": "Premium"},
    "2025": {"pt": "Grupo 2024/2025", "en": "2024/2025"},
    "russian": {"pt": "Russas", "en": "Russian"},
    "philippines": {"pt": "Filipinas", "en": "Philippines"},
    "europe": {"pt": "Eastern Europe", "en": "Eastern Europe"},
    "package": {"pt": "Pacote de Canais", "en": "Channel Package"},
    "vip": {"pt": "VIP Brasileiras", "en": "Brazilian VIP"},
    "br2026": {"pt": "Brasil 2026", "en": "Brazil 2026"},
    "ch2026": {"pt": "Canal 2026", "en": "Channel 2026"},
}
# ==========================================================
# /START — ESCOLHA DE IDIOMA
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🇧🇷 Português", callback_data="lang_pt")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")]
    ]
    await update.message.reply_text(
        "🌐 Escolha seu idioma / Choose your language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ==========================================================
# DEFINIR IDIOMA
# ==========================================================

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang

    if lang == "pt":
        await query.message.reply_text(TEXT_PT_LISTA, parse_mode="Markdown")
        await query.message.reply_text(TEXT_PT_VIP, parse_mode="Markdown")
        await query.message.reply_text(TEXT_PT_2026, parse_mode="Markdown")

        keyboard = [
            [InlineKeyboardButton("💎 Grupo Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 Grupo 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Russas", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Filipinas", callback_data="buy_philippines")],
            [InlineKeyboardButton("🌍 Eastern Europe", callback_data="buy_europe")],
            [InlineKeyboardButton("📦 Pacote de Canais", callback_data="buy_package")],
            [InlineKeyboardButton("🔥 VIP Brasileiras", callback_data="buy_vip")],
            [InlineKeyboardButton("🆕 Brasil 2026 (Pré-venda)", callback_data="buy_br2026")],
            [InlineKeyboardButton("🆕 Canal 2026 (Pré-venda)", callback_data="buy_ch2026")],
            [InlineKeyboardButton("📞 Suporte", callback_data="support")]
        ]
        await query.message.reply_text(
            "👇 Escolha o canal desejado:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    else:
        await query.message.reply_text(TEXT_EN_LISTA, parse_mode="Markdown")
        await query.message.reply_text(TEXT_EN_2026, parse_mode="Markdown")

        keyboard = [
            [InlineKeyboardButton("💎 Premium", callback_data="buy_premium")],
            [InlineKeyboardButton("🌟 2024/2025", callback_data="buy_2025")],
            [InlineKeyboardButton("🌍 Russian", callback_data="buy_russian")],
            [InlineKeyboardButton("🌏 Philippines", callback_data="buy_philippines")],
            [InlineKeyboardButton("🌍 Eastern Europe", callback_data="buy_europe")],
            [InlineKeyboardButton("📦 Channel Package", callback_data="buy_package")],
            [InlineKeyboardButton("🆕 Brazil 2026 (Pre-sale)", callback_data="buy_br2026")],
            [InlineKeyboardButton("🆕 Channel 2026 (Pre-sale)", callback_data="buy_ch2026")],
            [InlineKeyboardButton("📞 Support", callback_data="support")]
        ]
        await query.message.reply_text(
            "👇 Choose your channel:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


# ==========================================================
# SUPORTE
# ==========================================================

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📞 @proletariado")


# ==========================================================
# ESCOLHA DO PRODUTO
# ==========================================================

async def choose_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_key = query.data.replace("buy_", "")
    lang = context.user_data.get("lang", "pt")

    context.user_data["product"] = product_key

    # Identificar se é 2026
    is_2026 = product_key in ["br2026", "ch2026"]
    context.user_data["is_2026"] = is_2026

    if lang == "pt":
        text = f"💳 *Pagamento via PIX*\n\nCódigo:\n{PIX_CODE}\n\n📸 Envie o comprovante."
    else:
        text = (
            "💳 *Payment options*\n\n"
            f"WISE: `{WISE_EMAIL}`\n"
            f"SKRILL: `{SKRILL_EMAIL}`\n"
            f"BINANCE (TRX): `{BINANCE_TRX}`\n"
            f"BTC: `{BTC_ADDRESS}`\n\n"
            "📸 Send payment proof."
        )

    await query.message.reply_text(text, parse_mode="Markdown")


# ==========================================================
# REGISTRO DO PEDIDO
# ==========================================================

async def register_order(user, context, payment_method):
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
                context.user_data.get("lang"),
                context.user_data.get("product"),
                payment_method,
                "awaiting_proof",
                int(context.user_data.get("is_2026", False)),
                datetime.utcnow().isoformat()
            )
        )
        await db.commit()


# ==========================================================
# HANDLERS (PARTE 2)
# ==========================================================

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CallbackQueryHandler(set_language, pattern="^lang_"))
tg_app.add_handler(CallbackQueryHandler(support, pattern="^support$"))
tg_app.add_handler(CallbackQueryHandler(choose_product, pattern="^buy_"))
# ==========================================================
# RECEBER COMPROVANTE DE PAGAMENTO
# ==========================================================

async def receive_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.message.from_user
    lang = context.user_data.get("lang", "pt")
    product = context.user_data.get("product")

    if not product:
        if lang == "pt":
            await update.message.reply_text("❗ Você ainda não escolheu um canal.")
        else:
            await update.message.reply_text("❗ You have not selected a channel yet.")
        return

    # Atualiza pedido no banco
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """
            UPDATE orders
            SET status = ?, proof_received_at = ?
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            ("proof_received", datetime.utcnow().isoformat(), user.id)
        )
        await db.commit()

    # Mensagem ao cliente
    if lang == "pt":
        await update.message.reply_text(
            "✅ *Comprovante recebido!*\n\n"
            "⏳ Aguarde a verificação.\n"
            "Você será avisado assim que for aprovado.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "✅ *Payment proof received!*\n\n"
            "⏳ Please wait for verification.\n"
            "You will be notified once approved.",
            parse_mode="Markdown"
        )

    # Buscar dados do pedido
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """
            SELECT id, product, language, payment_method, is_2026, created_at
            FROM orders
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (user.id,)
        )
        order = await cursor.fetchone()

    if not order:
        return

    order_id, product, language, payment_method, is_2026, created_at = order

    # Texto para o admin
    admin_text = (
        "📩 *NOVO COMPROVANTE RECEBIDO*\n\n"
        f"🆔 Pedido: `{order_id}`\n"
        f"👤 Usuário: @{user.username or 'sem_username'}\n"
        f"🌐 Idioma: {language}\n"
        f"📦 Produto: {product}\n"
        f"💳 Pagamento: {payment_method}\n"
        f"🆕 Pré-venda 2026: {'SIM' if is_2026 else 'NÃO'}\n"
        f"📅 Data: {created_at}\n"
    )

    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📊 Abrir painel do pedido",
                callback_data=f"admin_open_{order_id}"
            )
        ]
    ])

    # Envia mensagem para o admin
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=admin_text,
        parse_mode="Markdown",
        reply_markup=admin_keyboard
    )

    # Repassa o comprovante (foto ou documento) para o admin
    try:
        await context.bot.copy_message(
            chat_id=ADMIN_CHAT_ID,
            from_chat_id=update.message.chat_id,
            message_id=update.message.message_id
        )
    except Exception:
        pass


# ==========================================================
# HANDLER DE COMPROVANTE (PARTE 3)
# ==========================================================

tg_app.add_handler(
    MessageHandler(
        filters.PHOTO | filters.Document.ALL,
        receive_payment_proof
    )
)
def format_admin_panel(order):
    (
        order_id,
        user_id,
        username,
        language,
        product,
        payment_method,
        status,
        is_2026,
        created_at
    ) = order

    user_tag = f"@{username}" if username else "(sem username)"
    idioma = "Português" if language == "pt" else "English"

    txt = (
        f"📦 *PEDIDO #{order_id}*\n\n"
        f"👤 Usuário: {user_tag}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"🌐 Idioma: {idioma}\n"
        f"📦 Produto: {product}\n"
        f"💳 Pagamento: {payment_method}\n"
        f"📌 Status: {status}\n"
        f"🆕 Pré-venda 2026: {'SIM' if is_2026 else 'NÃO'}\n"
        f"📅 Criado em: {created_at}\n"
    )
    return txt
async def get_order_by_id(order_id):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """
            SELECT id, user_id, username, language, product,
                   payment_method, status, is_2026, created_at
            FROM orders
            WHERE id = ?
            """,
            (order_id,)
        )
        return await cursor.fetchone()
async def admin_open_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_CHAT_ID:
        await query.answer("Acesso negado", show_alert=True)
        return

    order_id = int(query.data.split("_")[-1])
    order = await get_order_by_id(order_id)

    if not order:
        await query.message.reply_text("❌ Pedido não encontrado.")
        return

    text = format_admin_panel(order)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprovar", callback_data=f"admin_approve_{order_id}"),
            InlineKeyboardButton("❌ Rejeitar", callback_data=f"admin_reject_{order_id}")
        ],
        [
            InlineKeyboardButton("📤 Enviar link", callback_data=f"admin_send_{order_id}")
        ]
    ])

    await query.message.reply_text(
        text=text,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_CHAT_ID:
        return

    action, order_id = query.data.split("_")[1], int(query.data.split("_")[2])
    order = await get_order_by_id(order_id)

    if not order:
        await query.message.reply_text("❌ Pedido não encontrado.")
        return

    user_id = order[1]
    lang = order[3]

    if action == "approve":
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                ("approved", order_id)
            )
            await db.commit()

        msg = (
            "✅ *Pagamento aprovado!*\n\n"
            "Em breve você receberá seu acesso."
            if lang == "pt"
            else
            "✅ *Payment approved!*\n\n"
            "You will receive your access soon."
        )

        await context.bot.send_message(user_id, msg, parse_mode="Markdown")
        await query.message.reply_text("✅ Pedido aprovado.")

    if action == "reject":
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "UPDATE orders SET status = ? WHERE id = ?",
                ("rejected", order_id)
            )
            await db.commit()

        msg = (
            "❌ *Pagamento recusado.*\n\nEnvie um comprovante válido."
            if lang == "pt"
            else
            "❌ *Payment rejected.*\n\nPlease send a valid proof."
        )

        await context.bot.send_message(user_id, msg, parse_mode="Markdown")
        await query.message.reply_text("❌ Pedido rejeitado.")
async def admin_send_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    order_id = context.user_data.get("awaiting_link")
    if not order_id:
        return

    link = update.message.text.strip()
    order = await get_order_by_id(order_id)

    if not order:
        await update.message.reply_text("❌ Pedido não encontrado.")
        return

    user_id = order[1]
    lang = order[3]

    msg = (
        f"🎉 *Acesso liberado!*\n\n👉 {link}"
        if lang == "pt"
        else
        f"🎉 *Access granted!*\n\n👉 {link}"
    )

    await context.bot.send_message(user_id, msg, parse_mode="Markdown")

    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "UPDATE orders SET status = ? WHERE id = ?",
            ("delivered", order_id)
        )
        await db.commit()

    await update.message.reply_text("✅ Link enviado com sucesso.")
    context.user_data["awaiting_link"] = None
tg_app.add_handler(CallbackQueryHandler(admin_open_panel, pattern="^admin_open_"))
tg_app.add_handler(CallbackQueryHandler(admin_action, pattern="^admin_(approve|reject)_"))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_send_link))
from datetime import date

RELEASE_DATE_2026 = date(2026, 1, 2)
async def get_all_2026_buyers():
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT user_id, language, product
            FROM orders
            WHERE is_2026 = 1
              AND status IN ('approved', 'delivered')
            """
        )
        return await cursor.fetchall()
async def notify_2026_clients(bot):
    buyers = await get_all_2026_buyers()

    for user_id, lang, product in buyers:
        if lang == "pt":
            msg = (
                "🎉 *ACESSO LIBERADO!*\n\n"
                f"O canal *{product}* já está disponível.\n"
                "Você comprou na pré-venda e agora pode receber o link.\n\n"
                "📩 Aguarde, o acesso será enviado em seguida."
            )
        else:
            msg = (
                "🎉 *ACCESS RELEASED!*\n\n"
                f"The channel *{product}* is now available.\n"
                "You purchased early access and can now receive the link.\n\n"
                "📩 Please wait, the access will be sent shortly."
            )

        try:
            await bot.send_message(user_id, msg, parse_mode="Markdown")
        except Exception:
            pass
async def notify_admin_release(bot):
    msg = (
        "🚨 *LANÇAMENTO 02/01/2026*\n\n"
        "Os canais *Brasil 2026* e *Canal 2026* estão liberados.\n\n"
        "📌 Clientes da pré-venda já foram notificados.\n"
        "👉 Agora você pode enviar os links manualmente pelo painel."
    )

    await bot.send_message(ADMIN_CHAT_ID, msg, parse_mode="Markdown")
async def schedule_2026_release(app):
    async def check_release():
        today = date.today()
        if today == RELEASE_DATE_2026:
            await notify_2026_clients(app.bot)
            await notify_admin_release(app.bot)

    app.job_queue.run_repeating(
        check_release,
        interval=86400,  # 1 vez por dia
        first=10
    )
await schedule_2026_release(tg_app)
