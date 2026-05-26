"""Состояния FSM (конечного автомата) для шагов регистрации и админских действий."""

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    """Этапы заполнения анкеты пользователем."""

    waiting_name = State()
    waiting_phone = State()
    waiting_username = State()
    waiting_comment = State()


class Question(StatesGroup):
    """Состояние, когда пользователь пишет вопрос."""

    asking = State()


class AdminActions(StatesGroup):
    """Состояния для интерактивных действий админа."""

    editing_message = State()        # Жду новый текст для конкретного ключа
    broadcasting = State()           # Жду сообщение для рассылки всем
    dm_picking_user = State()        # Жду user_id или @username
    dm_writing = State()             # Жду сообщение для конкретного пользователя
    answering_question = State()     # Жду ответ на вопрос (question_id в data)
