"""Хендлеры пользовательского сценария: /start с проверкой резидента и заполнение анкеты."""

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from database import ensure_user, get_user, save_application
from keyboards import (
    phone_kb,
    resident_check_kb,
    skip_comment_kb,
    start_kb,
    use_tg_username_kb,
)
from messages import get_message
from states import Registration

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    ensure_user(message.from_user.id, message.from_user.username)
    user = get_user(message.from_user.id)

    # Уже подавал и заявка ещё не отклонена — не даём подать повторно
    if user and user["status"] in ("pending", "approved"):
        await message.answer(get_message("already_applied"))
        return

    # Сначала приветствие, затем — проверка резидентства
    await message.answer(get_message("welcome"))
    await message.answer(
        get_message("resident_check"),
        reply_markup=resident_check_kb(),
    )


@router.callback_query(F.data == "resident:yes")
async def cb_resident_yes(call: CallbackQuery, state: FSMContext) -> None:
    """Резидент — даём возможность подать заявку."""
    await call.message.answer(get_message("apply_invite"), reply_markup=start_kb())
    await call.answer()


@router.callback_query(F.data == "resident:no")
async def cb_resident_no(call: CallbackQuery, state: FSMContext) -> None:
    """Не резидент — вежливо завершаем разговор."""
    await call.message.answer(get_message("not_resident"))
    await call.answer()


@router.callback_query(F.data == "apply")
async def cb_apply(call: CallbackQuery, state: FSMContext) -> None:
    await call.message.answer(get_message("ask_name"))
    await state.set_state(Registration.waiting_name)
    await call.answer()


# Шаг 1 — имя
@router.message(Registration.waiting_name, F.text)
async def reg_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(
            "Имя слишком короткое. Пожалуйста, укажите ваше имя и фамилию."
        )
        return
    await state.update_data(full_name=name)
    await message.answer(get_message("ask_phone"), reply_markup=phone_kb())
    await state.set_state(Registration.waiting_phone)


# Шаг 2 — телефон (контактом или текстом)
@router.message(Registration.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.contact.phone_number)
    await _ask_username(message, state)


@router.message(Registration.waiting_phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext) -> None:
    phone = message.text.strip()
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 7:
        await message.answer(
            "Номер выглядит некорректно. Введите его в формате +7 999 123-45-67 "
            "или поделитесь контактом по кнопке."
        )
        return
    await state.update_data(phone=phone)
    await _ask_username(message, state)


async def _ask_username(message: Message, state: FSMContext) -> None:
    """Убирает reply-клавиатуру и просит указать ник в Telegram."""
    tg_username = message.from_user.username
    await message.answer("👇", reply_markup=ReplyKeyboardRemove())
    if tg_username:
        await message.answer(
            get_message("ask_username"),
            reply_markup=use_tg_username_kb(tg_username),
        )
    else:
        await message.answer(get_message("ask_username"))
    await state.set_state(Registration.waiting_username)


# Шаг 3 — ник в Telegram
@router.callback_query(Registration.waiting_username, F.data == "use_tg_username")
async def reg_use_tg_username(call: CallbackQuery, state: FSMContext) -> None:
    username = call.from_user.username or ""
    await state.update_data(club_username=f"@{username}")
    await call.message.answer(
        get_message("ask_comment"), reply_markup=skip_comment_kb()
    )
    await state.set_state(Registration.waiting_comment)
    await call.answer()


@router.message(Registration.waiting_username, F.text)
async def reg_username(message: Message, state: FSMContext) -> None:
    raw = message.text.strip().lstrip("@")
    if len(raw) < 3 or " " in raw:
        await message.answer(
            "Похоже на некорректный ник. Укажите его в формате @username."
        )
        return
    await state.update_data(club_username=f"@{raw}")
    await message.answer(
        get_message("ask_comment"), reply_markup=skip_comment_kb()
    )
    await state.set_state(Registration.waiting_comment)


# Шаг 4 — комментарий (или пропуск)
@router.callback_query(Registration.waiting_comment, F.data == "skip_comment")
async def reg_skip_comment(call: CallbackQuery, state: FSMContext) -> None:
    await _finalize(call.message, call.from_user.id, state, comment="")
    await call.answer()


@router.message(Registration.waiting_comment, F.text)
async def reg_comment(message: Message, state: FSMContext) -> None:
    await _finalize(message, message.from_user.id, state, comment=message.text.strip())


async def _finalize(
    message: Message, user_id: int, state: FSMContext, comment: str
) -> None:
    data = await state.get_data()
    save_application(
        user_id=user_id,
        full_name=data.get("full_name", ""),
        phone=data.get("phone", ""),
        club_username=data.get("club_username", ""),
        comment=comment,
    )
    await state.clear()
    await message.answer(get_message("application_received"))
