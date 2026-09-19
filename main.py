"""
ASTREC Business Assistant Bot
Единая точка входа для заявок предпринимателей: подбор персонала,
HR-консалтинг и маркетплейс специалистов (юристы, бухгалтеры и т.д.)

Все заявки уходят в личный чат администратора (ADMIN_CHAT_ID).
Роутинга к специалистам бот не делает — администратор распределяет вручную.
"""

import logging
import os
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")

# --- Категории услуг -------------------------------------------------------
# track: "own" — услуги, которые оказывает сама Карина (подбор, HR-консалтинг)
#        "market" — маркетплейс: заявка передаётся специалисту вручную
CATEGORIES = [
    ("hr_recruit", "🎯 Подбор персонала", "own"),
    ("hr_consult", "🧑‍💼 HR-консалтинг", "own"),
    ("finance_acc", "💰 Финансы и бухгалтерия", "market"),
    ("taxes", "📊 Налоги", "market"),
    ("legal", "⚖️ Юристы / Адвокаты (сделки, МФЦА)", "market"),
    ("pr", "📣 PR и коммуникации", "market"),
    ("hr_admin", "🗂 Кадровый учёт и расчёт ЗП", "market"),
    ("biz_analytics", "📈 Бизнес-аналитика и оценка", "market"),
    ("biz_plan", "📝 Бизнес-планирование", "market"),
    ("marketing", "📢 Маркетинговый анализ и план", "market"),
    ("training", "🎓 Обучение персонала", "market"),
    ("events", "🎪 Организация форумов, ивентов и стратегических сессий", "market"),
    ("it", "💻 IT-направление", "market"),
    ("product", "🚀 Product-менеджмент", "market"),
    ("project_mgmt", "📋 Project-менеджмент", "market"),
    ("interpretation", "🎧 Синхронный перевод", "market"),
]
CATEGORY_LABELS = {key: label for key, label, _ in CATEGORIES}

URGENCY_OPTIONS = [
    ("urgent", "🔴 Срочно"),
    ("week", "🟡 В течение недели"),
    ("flex", "🟢 Не срочно"),
]

# --- Состояния диалога -------------------------------------------------------
(
    CHOOSING_CATEGORY,
    ENTERING_ESSENCE,
    CHOOSING_URGENCY,
    ENTERING_BUDGET,
    ENTERING_CONTACT,
    CONFIRMING,
) = range(6)


def categories_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"cat:{key}")]
        for key, label, _ in CATEGORIES
    ]
    return InlineKeyboardMarkup(buttons)


def urgency_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"urg:{key}")]
        for key, label in URGENCY_OPTIONS
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("✅ Отправить", callback_data="confirm:yes"),
            InlineKeyboardButton("❌ Отменить", callback_data="confirm:no"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# --- Хендлеры ----------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Здравствуйте! Это бот-ассистент ASTREC для предпринимателей.\n\n"
        "Выберите, с чем вам нужна помощь:",
        reply_markup=categories_keyboard(),
    )
    return CHOOSING_CATEGORY


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    context.user_data["category_key"] = key
    context.user_data["category_label"] = CATEGORY_LABELS[key]

    await query.edit_message_text(
        f"Тема: {CATEGORY_LABELS[key]}\n\n"
        "Кратко опишите суть вашего запроса (2-3 предложения):"
    )
    return ENTERING_ESSENCE


async def essence_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["essence"] = update.message.text
    await update.message.reply_text(
        "Насколько это срочно?",
        reply_markup=urgency_keyboard(),
    )
    return CHOOSING_URGENCY


async def urgency_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    label = dict(URGENCY_OPTIONS)[key]
    context.user_data["urgency"] = label

    await query.edit_message_text(
        "Какой у вас ориентировочный бюджет на эту задачу? "
        "(укажите сумму или напишите «не определён»):"
    )
    return ENTERING_BUDGET


async def budget_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["budget"] = update.message.text
    await update.message.reply_text(
        "Оставьте контакт для связи (телефон или @username в Telegram):"
    )
    return ENTERING_CONTACT


async def contact_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["contact"] = update.message.text
    d = context.user_data

    summary = (
        "Проверьте вашу заявку:\n\n"
        f"📌 Тема: {d['category_label']}\n"
        f"📝 Суть: {d['essence']}\n"
        f"⏱ Срочность: {d['urgency']}\n"
        f"💵 Бюджет: {d['budget']}\n"
        f"📞 Контакт: {d['contact']}\n"
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard())
    return CONFIRMING


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    decision = query.data.split(":", 1)[1]

    if decision == "no":
        await query.edit_message_text("Заявка отменена. Чтобы начать заново — /start")
        context.user_data.clear()
        return ConversationHandler.END

    d = context.user_data
    user = query.from_user
    username = f"@{user.username}" if user.username else "(без username)"

    admin_text = (
        "🆕 <b>Новая заявка</b>\n\n"
        f"📌 <b>Тема:</b> {d['category_label']}\n"
        f"📝 <b>Суть:</b> {d['essence']}\n"
        f"⏱ <b>Срочность:</b> {d['urgency']}\n"
        f"💵 <b>Бюджет:</b> {d['budget']}\n"
        f"📞 <b>Контакт:</b> {d['contact']}\n\n"
        f"👤 От: {user.full_name} ({username}, id {user.id})\n"
        f"🕒 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    if ADMIN_CHAT_ID:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode=ParseMode.HTML
        )
    else:
        logger.warning("ADMIN_CHAT_ID не задан — заявка не доставлена администратору")

    await query.edit_message_text(
        "✅ Заявка принята! Мы свяжемся с вами в ближайшее время.\n\n"
        "Чтобы оставить ещё одну заявку — /start"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Заявка отменена. Чтобы начать заново — /start")
    return ConversationHandler.END


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Служебная команда: узнать chat_id — нужен для настройки ADMIN_CHAT_ID."""
    await update.message.reply_text(f"Ваш chat_id: {update.effective_chat.id}")


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не задан BOT_TOKEN в переменных окружения")

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_CATEGORY: [CallbackQueryHandler(category_chosen, pattern="^cat:")],
            ENTERING_ESSENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, essence_entered)],
            CHOOSING_URGENCY: [CallbackQueryHandler(urgency_chosen, pattern="^urg:")],
            ENTERING_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_entered)],
            ENTERING_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_entered)],
            CONFIRMING: [CallbackQueryHandler(confirm, pattern="^confirm:")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("myid", my_id))

    logger.info("Бот запущен, ожидаю сообщения...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
