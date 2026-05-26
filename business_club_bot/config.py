"""
Конфигурация бота. Читает токен и список администраторов из файла .env.

Пример .env:
    BOT_TOKEN=1234567890:ABC...
    ADMIN_IDS=123456789,987654321
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Загружаем переменные из .env, если файл существует
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

# Список Telegram user_id администраторов через запятую
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

# Пути к файлам данных
DB_PATH: str = str(BASE_DIR / "club.db")
MESSAGES_PATH: str = str(BASE_DIR / "messages.json")
