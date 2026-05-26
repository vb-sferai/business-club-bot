"""Хендлеры админ-панели: просмотр заявок, редактирование текстов, рассылка, ЛС, статистика."""

import asyncio
import html

from aiogram import Bot, F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_IDS
from database import (
    all_user_ids,
    count_new_questions,
    find_user_by_username,
    get_question,
    get_user,
    list_applications,
    list_questions,
    mark_question_answered,
    mark_question_closed,
    set_status,
    stats,
)
from keyboards import (
    admin_main_kb,
    app_actions_kb,
    apps_pagination_kb,
    back_to_admin_kb,
    confirm_broadcast_kb,
    messages_edit_kb,
    question_actions_kb,
    questions_pagination_kb,
)
from messages import get_message, load_messages, update_message
from states import AdminActions

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def _show_admin_menu(message: Message, *, edit: bool = False) -> None:
    """Показывает главное меню админа с актуальным счётчиком новых вопросов."""
    new_q = count_new_questions()
    text = "🛠 <b>Админ-панель Бизнес-Клуба</b>\n\n"
    if new_q > 0:
        text += f"❓ Новых вопросов: <b>{new_q}</b>\n\n"
    text += "Выберите действие:"
    kb = admin_main_kb(new_q)
    if edit:
        try:
            await message.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=kb)


# ============== Главное меню ==============

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await _show_admin_menu(message)


@router.callback_query(F.data == "admin:back")
async def cb_admin_back(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await _show_admin_menu(call.message, edit=True)
    await call.answer()


@router.message(Command("cancel"), StateFilter("*"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await _show_admin_menu(message)


# ============== Просмотр заявок ==============

@router.callback_query(F.data.startswith("admin:apps:"))
async def cb_apps_list(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    _, _, status, page_str = call.data.split(":")
    page = int(page_str)
    items = list_applications(status=status)
    title_map = {
        "pending": "⏳ На рассмотрении",
        "approved": "✅ Одобренные",
        "rejected": "❌ Отклонённые",
    }
    title = title_map.get(status, status)
    if not items:
        await call.message.edit_text(
            f"<b>{title}</b>\n\nПока пусто.",
            reply_markup=back_to_admin_kb(),
        )
        await call.answer()
        return
    await call.message.edit_text(
        f"<b>{title}</b> ({len(items)})\n\nВыберите заявку для просмотра:",
        reply_markup=apps_pagination_kb(items, status, page),
    )
    await call.answer()


async def _render_app_view(message: Message, user_id: int) -> None:
    """Рендерит карточку заявки. Используется и при просмотре, и после действий."""
    u = get_user(user_id)
    if not u:
        await message.edit_text("Заявка не найдена.", reply_markup=back_to_admin_kb())
        return

    def esc(value: object) -> str:
        if not value:
            return "—"
        return html.escape(str(value))

    status_emoji = {
        "pending": "⏳ на рассмотрении",
        "approved": "✅ одобрена",
        "rejected": "❌ отклонена",
        "started": "— (анкета не заполнена)",
    }.get(u["status"], u["status"])

    text = (
        f"<b>Заявка №{u['user_id']}</b>\n\n"
        f"👤 <b>Имя:</b> {esc(u['full_name'])}\n"
        f"📱 <b>Телефон:</b> <code>{esc(u['phone'])}</code>\n"
        f"💬 <b>Telegram:</b> {esc(u['club_username'])} "
        f"(аккаунт: @{esc(u['tg_username'])})\n"
        f"📝 <b>Комментарий:</b> {esc(u['comment'])}\n"
        f"📌 <b>Статус:</b> {status_emoji}\n"
        f"🗓 <b>Подана:</b> {esc(u['applied_at'])}\n"
    )
    try:
        await message.edit_text(
            text, reply_markup=app_actions_kb(u["user_id"], u["status"])
        )
    except Exception:
        # Если редактировать нельзя (например, исходное сообщение было медиа) — отправим новое
        await message.answer(
            text, reply_markup=app_actions_kb(u["user_id"], u["status"])
        )


@router.callback_query(F.data.startswith("app:view:"))
async def cb_view_app(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    user_id = int(call.data.split(":")[2])
    await _render_app_view(call.message, user_id)
    await call.answer()


@router.callback_query(F.data.startswith("app:approve:"))
async def cb_approve(call: CallbackQuery, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    user_id = int(call.data.split(":")[2])
    set_status(user_id, "approved")
    try:
        await bot.send_message(user_id, get_message("approved_notification"))
    except Exception:
        pass
    await call.answer("Заявка одобрена ✅")
    await _render_app_view(call.message, user_id)


@router.callback_query(F.data.startswith("app:reject:"))
async def cb_reject(call: CallbackQuery, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    user_id = int(call.data.split(":")[2])
    set_status(user_id, "rejected")
    try:
        await bot.send_message(user_id, get_message("rejected_notification"))
    except Exception:
        pass
    await call.answer("Заявка отклонена ❌")
    await _render_app_view(call.message, user_id)


@router.callback_query(F.data.startswith("app:dm:"))
async def cb_app_dm(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    user_id = int(call.data.split(":")[2])
    await state.update_data(dm_target=user_id)
    await state.set_state(AdminActions.dm_writing)
    await call.message.answer(
        f"✍️ Напишите сообщение для пользователя <code>{user_id}</code>.\n"
        f"Поддерживаются текст, фото, видео, документы — что отправите, то и улетит.\n\n"
        f"Отправьте /cancel для отмены."
    )
    await call.answer()


# ============== Редактирование текстов ==============

@router.callback_query(F.data == "admin:edit_msg")
async def cb_edit_msg(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    keys = list(load_messages().keys())
    await call.message.edit_text(
        "📝 <b>Редактирование текстов</b>\n\n"
        "Выберите сообщение, которое хотите изменить:",
        reply_markup=messages_edit_kb(keys),
    )
    await call.answer()


@router.callback_query(F.data.startswith("msg:edit:"))
async def cb_edit_specific(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    key = call.data.split(":", 2)[2]
    current = get_message(key)
    await state.update_data(edit_key=key)
    await state.set_state(AdminActions.editing_message)

    # Отдельным сообщением — текущий текст в безопасном виде (через <pre>), чтобы было удобно скопировать
    await call.message.answer(
        f"Текущий текст «<b>{html.escape(key)}</b>»:"
    )
    await call.message.answer(
        f"<pre>{html.escape(current)}</pre>"
    )
    await call.message.answer(
        "✏️ Отправьте новый текст одним сообщением.\n\n"
        "Поддерживается HTML-разметка: "
        "<code>&lt;b&gt;жирный&lt;/b&gt;</code>, "
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>, "
        "<code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code>, "
        "<code>&lt;a href=\"...\"&gt;ссылка&lt;/a&gt;</code>.\n\n"
        "Отправьте /cancel для отмены."
    )
    await call.answer()


@router.message(AdminActions.editing_message, F.text)
async def admin_set_message_text(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    if message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main_kb(count_new_questions()))
        return

    data = await state.get_data()
    key = data.get("edit_key")
    if not key:
        await state.clear()
        return

    # Проверим, что Telegram сможет распарсить разметку — иначе тексту нельзя доверять
    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=message.text,
            parse_mode="HTML",
            disable_notification=True,
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось сохранить: ошибка HTML-разметки.\n<code>{html.escape(str(e))}</code>\n\n"
            f"Проверьте теги и отправьте текст ещё раз, либо /cancel для отмены."
        )
        return

    update_message(key, message.text)
    await state.clear()
    await message.answer(
        f"✅ Сообщение «{html.escape(key)}» обновлено.",
        reply_markup=back_to_admin_kb(),
    )


# ============== Рассылка всем ==============

@router.callback_query(F.data == "admin:broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(AdminActions.broadcasting)
    await call.message.answer(
        "📢 <b>Рассылка всем</b>\n\n"
        "Отправьте сообщение (текст, фото, видео или что угодно ещё) — оно "
        "будет показано как предпросмотр. После подтверждения уйдёт всем "
        "пользователям бота.\n\n"
        "Отправьте /cancel для отмены."
    )
    await call.answer()


@router.message(AdminActions.broadcasting)
async def broadcast_preview(message: Message, state: FSMContext) -> None:
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main_kb(count_new_questions()))
        return

    # Сохраним ссылку на это сообщение — потом будем его копировать
    await state.update_data(
        bc_chat_id=message.chat.id,
        bc_message_id=message.message_id,
    )
    await message.answer(
        "👆 Это сообщение будет отправлено всем пользователям. Подтвердить?",
        reply_markup=confirm_broadcast_kb(),
    )


@router.callback_query(F.data == "bc:cancel")
async def bc_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.answer("Рассылка отменена.", reply_markup=admin_main_kb(count_new_questions()))
    await call.answer()


@router.callback_query(F.data == "bc:confirm")
async def bc_confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    data = await state.get_data()
    chat_id = data.get("bc_chat_id")
    message_id = data.get("bc_message_id")
    await state.clear()
    if not chat_id or not message_id:
        await call.message.answer(
            "Нет сообщения для рассылки.", reply_markup=admin_main_kb(count_new_questions())
        )
        await call.answer()
        return

    user_ids = all_user_ids()
    sent, failed = 0, 0
    progress = await call.message.answer(
        f"Начинаю рассылку для {len(user_ids)} получателей…"
    )
    for uid in user_ids:
        try:
            await bot.copy_message(
                chat_id=uid, from_chat_id=chat_id, message_id=message_id
            )
            sent += 1
        except Exception:
            failed += 1
        # Telegram ограничивает ~30 сообщений в секунду — берём с запасом
        await asyncio.sleep(0.05)

    await progress.edit_text(
        f"📢 <b>Рассылка завершена.</b>\n"
        f"Отправлено: <b>{sent}</b>\n"
        f"Не доставлено: <b>{failed}</b>",
        reply_markup=back_to_admin_kb(),
    )
    await call.answer()


# ============== Личное сообщение пользователю ==============

@router.callback_query(F.data == "admin:dm")
async def cb_dm(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.set_state(AdminActions.dm_picking_user)
    await call.message.answer(
        "💌 <b>Личное сообщение</b>\n\n"
        "Введите <b>user_id</b> (число) или <b>@username</b> получателя.\n\n"
        "Отправьте /cancel для отмены."
    )
    await call.answer()


@router.message(AdminActions.dm_picking_user, F.text)
async def dm_pick(message: Message, state: FSMContext) -> None:
    raw = message.text.strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main_kb(count_new_questions()))
        return

    target_id: int | None = None
    if raw.isdigit():
        target_id = int(raw)
    else:
        user = find_user_by_username(raw)
        if user:
            target_id = user["user_id"]

    if not target_id:
        await message.answer(
            "Пользователь не найден. Попробуйте ещё раз или /cancel.\n"
            "Подсказка: пользователь должен был хотя бы раз нажать /start."
        )
        return

    await state.update_data(dm_target=target_id)
    await state.set_state(AdminActions.dm_writing)
    await message.answer(
        f"Готово. Теперь отправьте сообщение для <code>{target_id}</code> "
        f"(текст, фото, видео и т.д.).\n\nОтправьте /cancel для отмены."
    )


@router.message(AdminActions.dm_writing)
async def dm_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_main_kb(count_new_questions()))
        return

    data = await state.get_data()
    target = data.get("dm_target")
    await state.clear()
    if not target:
        await message.answer(
            "Получатель не задан.", reply_markup=admin_main_kb(count_new_questions())
        )
        return

    try:
        await bot.copy_message(
            chat_id=target,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer(
            f"✅ Сообщение отправлено пользователю <code>{target}</code>.",
            reply_markup=back_to_admin_kb(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить: <code>{html.escape(str(e))}</code>\n\n"
            f"Скорее всего, пользователь заблокировал бота.",
            reply_markup=back_to_admin_kb(),
        )


# ============== Вопросы пользователей ==============

@router.callback_query(F.data.startswith("admin:questions:"))
async def cb_questions_list(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    _, _, status, page_str = call.data.split(":")
    page = int(page_str)
    items = list_questions(status=status)
    title_map = {
        "new": "❓ Новые вопросы",
        "answered": "💬 Отвеченные вопросы",
        "closed": "✅ Закрытые вопросы",
    }
    title = title_map.get(status, status)

    if not items:
        # Пустой список — всё равно показываем переключатель вкладок
        from keyboards import questions_tabs_kb
        await call.message.edit_text(
            f"<b>{title}</b>\n\nПока пусто.",
            reply_markup=questions_tabs_kb(status),
        )
        await call.answer()
        return

    await call.message.edit_text(
        f"<b>{title}</b> ({len(items)})\n\nВыберите вопрос для просмотра:",
        reply_markup=questions_pagination_kb(items, status, page),
    )
    await call.answer()


async def _render_question_view(
    message: Message, question_id: int, from_status: str = "new"
) -> None:
    q = get_question(question_id)
    if not q:
        try:
            await message.edit_text(
                "Вопрос не найден.", reply_markup=back_to_admin_kb()
            )
        except Exception:
            await message.answer(
                "Вопрос не найден.", reply_markup=back_to_admin_kb()
            )
        return

    user = get_user(q["user_id"])
    if user:
        user_label = (
            f"{user.get('full_name') or '—'} "
            f"(@{user.get('tg_username') or '—'}, id <code>{q['user_id']}</code>)"
        )
    else:
        user_label = f"id <code>{q['user_id']}</code>"

    status_text = {
        "new": "🆕 ждёт ответа",
        "answered": "💬 отвечен",
        "closed": "✅ закрыт без ответа",
    }.get(q["status"], q["status"])

    text = (
        f"<b>Вопрос #{q['id']}</b>\n\n"
        f"👤 <b>От:</b> {user_label}\n"
        f"📌 <b>Статус:</b> {status_text}\n"
        f"🗓 <b>Задан:</b> {q['created_at']}\n\n"
        f"<b>Текст вопроса:</b>\n{html.escape(q['text'])}\n"
    )
    if q["answer_text"]:
        text += (
            f"\n<b>Ответ ({q['answered_at']}):</b>\n"
            f"<i>{html.escape(q['answer_text'][:1000])}</i>"
        )

    kb = question_actions_kb(q["id"], q["status"], from_status=from_status)
    try:
        await message.edit_text(text, reply_markup=kb)
    except Exception:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("q:view:"))
async def cb_view_question(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    parts = call.data.split(":")
    q_id = int(parts[2])
    from_status = parts[3] if len(parts) >= 4 else "new"
    await _render_question_view(call.message, q_id, from_status=from_status)
    await call.answer()


@router.callback_query(F.data.startswith("q:answer:"))
async def cb_answer_question(call: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    q_id = int(call.data.split(":")[2])
    q = get_question(q_id)
    if not q:
        await call.answer("Вопрос не найден")
        return
    await state.update_data(answering_question_id=q_id)
    await state.set_state(AdminActions.answering_question)
    await call.message.answer(
        f"✍️ Напишите ответ на <b>вопрос #{q_id}</b>.\n\n"
        f"Можно отправить текст, фото, видео или документ — мы перешлём как есть.\n\n"
        f"<b>Контекст вопроса:</b>\n"
        f"<i>{html.escape(q['text'][:600])}</i>\n\n"
        f"Отправьте /cancel для отмены."
    )
    await call.answer()


@router.message(AdminActions.answering_question)
async def send_answer(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    if message.text and message.text.strip() == "/cancel":
        await state.clear()
        await message.answer(
            "Отменено.", reply_markup=admin_main_kb(count_new_questions())
        )
        return

    data = await state.get_data()
    q_id = data.get("answering_question_id")
    await state.clear()
    if not q_id:
        await message.answer(
            "Контекст ответа потерян.",
            reply_markup=admin_main_kb(count_new_questions()),
        )
        return
    q = get_question(q_id)
    if not q:
        await message.answer(
            "Вопрос не найден.",
            reply_markup=admin_main_kb(count_new_questions()),
        )
        return

    try:
        # Сначала вводное сообщение с цитатой вопроса
        await bot.send_message(
            q["user_id"],
            f"{get_message('answer_intro')}\n\n"
            f"<i>«{html.escape(q['text'][:300])}»</i>",
        )
        # Затем — сам ответ (copy_message умеет любой тип)
        await bot.copy_message(
            chat_id=q["user_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        answer_text = message.text or message.caption or "(медиа-сообщение)"
        mark_question_answered(q_id, message.from_user.id, answer_text)
        await message.answer(
            f"✅ Ответ отправлен пользователю по вопросу #{q_id}.",
            reply_markup=back_to_admin_kb(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить ответ: <code>{html.escape(str(e))}</code>\n"
            f"Возможно, пользователь заблокировал бота.",
            reply_markup=back_to_admin_kb(),
        )


@router.callback_query(F.data.startswith("q:close:"))
async def cb_close_question(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    q_id = int(call.data.split(":")[2])
    mark_question_closed(q_id)
    await call.answer("Вопрос закрыт ✅")
    await _render_question_view(call.message, q_id, from_status="closed")


@router.callback_query(F.data.startswith("q:applicant:"))
async def cb_question_applicant(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    q_id = int(call.data.split(":")[2])
    q = get_question(q_id)
    if not q:
        await call.answer("Не найдено")
        return
    await _render_app_view(call.message, q["user_id"])
    await call.answer()


# ============== Статистика ==============

@router.callback_query(F.data == "admin:stats")
async def cb_stats(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    s = stats()
    text = (
        "<b>📊 Статистика</b>\n\n"
        "<b>Пользователи</b>\n"
        f"• Всего в базе: <b>{s['total']}</b>\n"
        f"• Только запустили /start: <b>{s['started']}</b>\n"
        f"• ⏳ Ожидают рассмотрения: <b>{s['pending']}</b>\n"
        f"• ✅ Одобрены: <b>{s['approved']}</b>\n"
        f"• ❌ Отклонены: <b>{s['rejected']}</b>\n\n"
        "<b>Вопросы</b>\n"
        f"• Всего задано: <b>{s['questions_total']}</b>\n"
        f"• 🆕 Новых: <b>{s['questions_new']}</b>\n"
        f"• 💬 Отвечено: <b>{s['questions_answered']}</b>\n"
        f"• ✅ Закрыто без ответа: <b>{s['questions_closed']}</b>\n"
    )
    await call.message.edit_text(text, reply_markup=back_to_admin_kb())
    await call.answer()


# ============== Утилита: показать свой user_id ==============

@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    """Для всех — чтобы человек мог узнать свой user_id и прислать админу."""
    await message.answer(
        f"Ваш Telegram user_id: <code>{message.from_user.id}</code>"
    )
