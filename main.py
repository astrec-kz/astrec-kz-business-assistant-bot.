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

# --- Направления и услуги ---------------------------------------------------
# track: "own" — услуги, которые оказывает сама Карина (подбор, HR-консалтинг)
#        "market" — маркетплейс: заявка передаётся специалисту вручную
GROUPS = [
    ("hr", "HR и персонал"),
    ("finlegal", "Финансы и право"),
    ("strategy", "Стратегия и развитие"),
    ("marketing", "Маркетинг и коммуникации"),
    ("events", "Мероприятия и сервис"),
]

CATEGORIES = [
    ("hr_recruit", "Подбор персонала", "own", "hr"),
    ("hr_consult", "HR-консалтинг", "own", "hr"),
    ("hr_admin", "Кадровый учёт и расчёт заработной платы", "market", "hr"),
    ("training", "Обучение персонала", "market", "hr"),
    ("finance_acc", "Финансы и бухгалтерия", "market", "finlegal"),
    ("taxes", "Налоги", "market", "finlegal"),
    ("legal", "Юристы и адвокаты — сделки, МФЦА", "market", "finlegal"),
    ("biz_analytics", "Бизнес-аналитика и оценка", "market", "finlegal"),
    ("biz_plan", "Бизнес-планирование", "market", "strategy"),
    ("product", "Product-менеджмент", "market", "strategy"),
    ("project_mgmt", "Project-менеджмент", "market", "strategy"),
    ("it", "IT-направление", "market", "strategy"),
    ("pr", "PR и коммуникации", "market", "marketing"),
    ("marketing", "Маркетинговый анализ и план", "market", "marketing"),
    ("events", "Форумы, ивенты и стратегические сессии", "market", "events"),
    ("interpretation", "Синхронный перевод", "market", "events"),
]
CATEGORY_LABELS = {key: label for key, label, _, _ in CATEGORIES}
GROUP_LABELS = {key: label for key, label in GROUPS}

URGENCY_OPTIONS = [
    ("urgent", "Срочно"),
    ("week", "В течение недели"),
    ("flex", "Не срочно"),
]

# --- Состояния диалога -------------------------------------------------------
(
    CHOOSING_GROUP,
    CHOOSING_CATEGORY,
    ENTERING_ESSENCE,
    CHOOSING_URGENCY,
    ENTERING_BUDGET,
    ENTERING_CONTACT,
    CONFIRMING,
) = range(7)


def groups_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"grp:{key}")]
        for key, label in GROUPS
    ]
    return InlineKeyboardMarkup(buttons)


def categories_keyboard(group_key: str) -> InlineKeyboardMarkup:
    items = [(key, label) for key, label, _, grp in CATEGORIES if grp == group_key]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"cat:{key}")]
        for key, label in items
    ]
    buttons.append([InlineKeyboardButton("‹ Назад к направлениям", callback_data="back_to_groups")])
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
            InlineKeyboardButton("Подтвердить", callback_data="confirm:yes"),
            InlineKeyboardButton("Отменить", callback_data="confirm:no"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


# --- Хендлеры ----------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "<b>ASTREC — Business Assistant</b>\n\n"
        "Консультационная и HR-поддержка для вашего бизнеса.\n\n"
        "Выберите направление:",
        reply_markup=groups_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return CHOOSING_GROUP


async def group_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    context.user_data["group_key"] = key
    context.user_data["group_label"] = GROUP_LABELS[key]

    await query.edit_message_text(
        f"<b>{GROUP_LABELS[key]}</b>\n\nВыберите услугу:",
        reply_markup=categories_keyboard(key),
        parse_mode=ParseMode.HTML,
    )
    return CHOOSING_CATEGORY


async def back_to_groups(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "<b>ASTREC — Business Assistant</b>\n\n"
        "Консультационная и HR-поддержка для вашего бизнеса.\n\n"
        "Выберите направление:",
        reply_markup=groups_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return CHOOSING_GROUP


async def category_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split(":", 1)[1]
    context.user_data["category_key"] = key
    context.user_data["category_label"] = CATEGORY_LABELS[key]

    await query.edit_message_text(
        f"<b>{CATEGORY_LABELS[key]}</b>\n\n"
        "Кратко опишите суть вашего запроса (2–3 предложения):",
        parse_mode=ParseMode.HTML,
    )
    return ENTERING_ESSENCE


async def essence_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["essence"] = update.message.text
    await update.message.reply_text(
        "Насколько срочен запрос?",
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
        "Ориентировочный бюджет на задачу?\n"
        "Укажите сумму или напишите «не определён»:"
    )
    return ENTERING_BUDGET


async def budget_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["budget"] = update.message.text
    await update.message.reply_text(
        "Контакт для связи — телефон или @username в Telegram:"
    )
    return ENTERING_CONTACT


async def contact_entered(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["contact"] = update.message.text
    d = context.user_data

    summary = (
        "<b>Проверьте заявку</b>\n\n"
        f"Направление: {d['group_label']}\n"
        f"Услуга: {d['category_label']}\n"
        f"Суть: {d['essence']}\n"
        f"Срочность: {d['urgency']}\n"
        f"Бюджет: {d['budget']}\n"
        f"Контакт: {d['contact']}"
    )
    await update.message.reply_text(
        summary, reply_markup=confirm_keyboard(), parse_mode=ParseMode.HTML
    )
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
        "<b>Новая заявка</b>\n\n"
        f"Направление: {d['group_label']}\n"
        f"Услуга: {d['category_label']}\n"
        f"Суть: {d['essence']}\n"
        f"Срочность: {d['urgency']}\n"
        f"Бюджет: {d['budget']}\n"
        f"Контакт: {d['contact']}\n\n"
        f"От: {user.full_name} ({username}, id {user.id})\n"
        f"{datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    if ADMIN_CHAT_ID:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID, text=admin_text, parse_mode=ParseMode.HTML
        )
    else:
        logger.warning("ADMIN_CHAT_ID не задан — заявка не доставлена администратору")

    await query.edit_message_text(
        "Заявка принята. Мы свяжемся с вами в ближайшее время.\n\n"
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
            CHOOSING_GROUP: [CallbackQueryHandler(group_chosen, pattern="^grp:")],
            CHOOSING_CATEGORY: [
                CallbackQueryHandler(back_to_groups, pattern="^back_to_groups$"),
                CallbackQueryHandler(category_chosen, pattern="^cat:"),
            ],
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
