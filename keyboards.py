"""Все клавиатуры — собраны в одном месте, чтобы их было удобно править."""

from typing import Any

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ---------- Клавиатуры пользователя ----------

def resident_check_kb() -> InlineKeyboardMarkup:
    """Кнопки Да/Нет для проверки, является ли пользователь резидентом «Эволют»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="resident:yes"),
                InlineKeyboardButton(text="❌ Нет", callback_data="resident:no"),
            ]
        ]
    )


def start_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Подать заявку", callback_data="apply")]
        ]
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def use_tg_username_kb(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Использовать @{username}",
                    callback_data="use_tg_username",
                )
            ]
        ]
    )


def skip_comment_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_comment")]
        ]
    )


def ask_question_kb() -> InlineKeyboardMarkup:
    """Кнопка «Задать вопрос» — показывается пользователю после подачи заявки."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❓ Задать вопрос",
                                   callback_data="ask_question")]
        ]
    )


# ---------- Админские клавиатуры ----------

def admin_main_kb(new_questions_count: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Заявки на рассмотрении",
                                   callback_data="admin:apps:pending:0")],
            [InlineKeyboardButton(text="✅ Одобренные",
                                   callback_data="admin:apps:approved:0"),
             InlineKeyboardButton(text="❌ Отклонённые",
                                   callback_data="admin:apps:rejected:0")],
            [InlineKeyboardButton(text="📝 Редактировать сообщения",
                                   callback_data="admin:edit_msg")],
            [InlineKeyboardButton(text="📢 Рассылка всем",
                                   callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="💌 Написать пользователю",
                                   callback_data="admin:dm")],
            [InlineKeyboardButton(text="📊 Статистика",
                                   callback_data="admin:stats")],
        ]
    )


def back_to_admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ В меню админа",
                                   callback_data="admin:back")]
        ]
    )


def app_actions_kb(user_id: int, status: str) -> InlineKeyboardMarkup:
    """Кнопки на карточке заявки: одобрить/отклонить/написать/назад."""
    rows: list[list[InlineKeyboardButton]] = []
    action_row: list[InlineKeyboardButton] = []
    if status != "approved":
        action_row.append(
            InlineKeyboardButton(text="✅ Одобрить",
                                  callback_data=f"app:approve:{user_id}")
        )
    if status != "rejected":
        action_row.append(
            InlineKeyboardButton(text="❌ Отклонить",
                                  callback_data=f"app:reject:{user_id}")
        )
    if action_row:
        rows.append(action_row)
    rows.append([
        InlineKeyboardButton(text="💌 Написать", callback_data=f"app:dm:{user_id}")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def messages_edit_kb(keys: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=k, callback_data=f"msg:edit:{k}")] for k in keys]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_broadcast_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Отправить всем",
                                   callback_data="bc:confirm"),
             InlineKeyboardButton(text="❌ Отмена",
                                   callback_data="bc:cancel")]
        ]
    )


def apps_pagination_kb(
    items: list[dict[str, Any]],
    status: str,
    page: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    """Список заявок с пагинацией. Каждая кнопка ведёт в карточку заявки."""
    start = page * page_size
    chunk = items[start : start + page_size]
    rows: list[list[InlineKeyboardButton]] = []
    for app in chunk:
        name = app.get("full_name") or "—"
        tg = app.get("tg_username") or "—"
        rows.append([
            InlineKeyboardButton(
                text=f"{name} (@{tg})",
                callback_data=f"app:view:{app['user_id']}",
            )
        ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"admin:apps:{status}:{page - 1}"
        ))
    if start + page_size < len(items):
        nav.append(InlineKeyboardButton(
            text="➡️", callback_data=f"admin:apps:{status}:{page + 1}"
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------- Клавиатуры для раздела «Вопросы» ----------

def questions_tabs_kb(current: str) -> InlineKeyboardMarkup:
    """Переключение между вкладками: новые / отвеченные / закрытые."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("• 🆕 Новые •" if current == "new" else "🆕 Новые"),
                    callback_data="admin:questions:new:0",
                ),
                InlineKeyboardButton(
                    text=("• 💬 Отвеченные •" if current == "answered" else "💬 Отвеченные"),
                    callback_data="admin:questions:answered:0",
                ),
                InlineKeyboardButton(
                    text=("• ✅ Закрытые •" if current == "closed" else "✅ Закрытые"),
                    callback_data="admin:questions:closed:0",
                ),
            ],
            [InlineKeyboardButton(text="⬅️ В меню админа",
                                   callback_data="admin:back")],
        ]
    )


def questions_pagination_kb(
    items: list[dict[str, Any]],
    status: str,
    page: int,
    page_size: int = 5,
) -> InlineKeyboardMarkup:
    start = page * page_size
    chunk = items[start : start + page_size]
    rows: list[list[InlineKeyboardButton]] = []
    for q in chunk:
        preview = (q.get("text") or "").strip().replace("\n", " ")
        if len(preview) > 50:
            preview = preview[:47] + "…"
        rows.append([
            InlineKeyboardButton(
                text=f"#{q['id']} • {preview}",
                callback_data=f"q:view:{q['id']}:{status}",
            )
        ])
    # Переключатель вкладок
    rows.append([
        InlineKeyboardButton(
            text=("• 🆕 •" if status == "new" else "🆕"),
            callback_data="admin:questions:new:0",
        ),
        InlineKeyboardButton(
            text=("• 💬 •" if status == "answered" else "💬"),
            callback_data="admin:questions:answered:0",
        ),
        InlineKeyboardButton(
            text=("• ✅ •" if status == "closed" else "✅"),
            callback_data="admin:questions:closed:0",
        ),
    ])
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(
            text="⬅️", callback_data=f"admin:questions:{status}:{page - 1}"
        ))
    if start + page_size < len(items):
        nav.append(InlineKeyboardButton(
            text="➡️", callback_data=f"admin:questions:{status}:{page + 1}"
        ))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="⬅️ В меню админа",
                                       callback_data="admin:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_actions_kb(
    question_id: int, status: str, from_status: str = "new"
) -> InlineKeyboardMarkup:
    """Кнопки на карточке вопроса. from_status — куда возвращаться при «Назад»."""
    rows: list[list[InlineKeyboardButton]] = []
    if status == "new":
        rows.append([
            InlineKeyboardButton(text="💬 Ответить",
                                  callback_data=f"q:answer:{question_id}"),
            InlineKeyboardButton(text="✅ Закрыть",
                                  callback_data=f"q:close:{question_id}"),
        ])
    elif status == "closed":
        rows.append([
            InlineKeyboardButton(text="💬 Ответить",
                                  callback_data=f"q:answer:{question_id}"),
        ])
    else:  # answered
        rows.append([
            InlineKeyboardButton(text="💬 Ответить снова",
                                  callback_data=f"q:answer:{question_id}"),
        ])
    rows.append([
        InlineKeyboardButton(text="👤 Карточка заявителя",
                              callback_data=f"q:applicant:{question_id}")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ К списку вопросов",
                              callback_data=f"admin:questions:{from_status}:0")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def question_notification_kb(question_id: int) -> InlineKeyboardMarkup:
    """Кнопки в уведомлении админу о новом вопросе."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Ответить",
                                   callback_data=f"q:answer:{question_id}")],
            [InlineKeyboardButton(text="👁 Открыть карточку",
                                   callback_data=f"q:view:{question_id}:new")],
        ]
    )
