import logging
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import state
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, User
from app.services.jira import JiraService
from app.utils.helpers import format_issue_message, format_datetime, parse_jira_datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class UserStates(state.StatesGroup):
    waiting_for_token = state.State()
    waiting_for_issue_key = state.State()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

def format_worklog_message(worklog_entries: dict) -> str:
    """Форматирование сообщения с отчетом о раоте."""
    if not worklog_entries:
        return "За последние 3 дня нет записей о работе."
        
    message = "📊 *Отчет о затраченном времени за последние 3 дня*\n\n"
    
    for issue_key, entries in worklog_entries.items():
        message += f"🔹 *Задача:* [{issue_key}]({settings.JIRA_URL}/browse/{issue_key})\n"
        message += f"*Название:* {entries[0]['issue_summary']}\n\n"
        
        for entry in entries:
            date = parse_jira_datetime(entry['date']).strftime("%d-%m-%y %H:%M")
            message += f"⏰ {date}\n"
            message += f"⌛️ *Затрачено:* {entry['time_spent']}\n"
            if entry['comment']:
                message += f"💬 *Комментарий:*\n{entry['comment']}\n"
            message += "\n"
        
        message += "─────────────────\n"
    
    return message

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.reply(
        "Привет! Я бот для работы с Jira. "
        "Для начала работы установите ваш токен Jira с помощью команды /set_token\n\n"
        "Доступные команды:\n"
        "/set_token - Установить токен Jira\n"
        "/remove_token - Удалить токен\n"
        "/get_issue - Получить информацию о задаче\n"
        "/worklog - Получить отчет о работе за последние 2 дня\n"
        "/help - Показать справку"
    )

@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    await message.reply(
        "Доступные команды:\n"
        "/set_token - Установить токен Jira\n"
        "/remove_token - Удалить токен\n"
        "/get_issue - Получить информацию о задаче\n"
        "/worklog - Получить отчет о работе за последние 3 дня\n"
        "/help - Показать справку"
    )

@dp.message_handler(commands=['worklog'])
async def worklog_command(message: types.Message):
    """Получение отчета о работе за последние 3 дня."""
    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        await message.reply("❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
        return
    
    try:
        # Получаем данные из Jira
        jira = JiraService(token=user.jira_token)
        worklog_entries = jira.get_recent_worklog()
        
        # Форматируем и отправляем сообщение
        response = format_worklog_message(worklog_entries)
        await message.reply(response, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error getting worklog: {e}")
        await message.reply(f"❌ Ошибка при получении отчета: {str(e)}")

@dp.message_handler(commands=['set_token'])
async def set_token_command(message: types.Message):
    # Удаляем сообщение с командой для безопасности
    await message.delete()
    
    # Проверяем, есть ли уже токен у пользователя
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        await message.answer(
            "У вас уже установлен токен. Хотите установить новый?\n"
            "Используйте /remove_token для удаления текущего токена, "
            "а затем /set_token для установки нового."
        )
        return
    
    await UserStates.waiting_for_token.set()
    await message.answer(
        "Пожалуйста, отправьте ваш токен Jira.\n"
        "Его можно получить в настройках вашего аккаунта Jira:\n"
        "1. Перейдите в Profile -> Security -> Create and manage API tokens\n"
        "2. Нажмите Create API token\n"
        "3. Скопируйте и отправьте токен в следующем сообщении\n\n"
        "⚠️ Сообщение с токеном будет автоматически удалено для безопасности"
    )

@dp.message_handler(state=UserStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    # Удаляем сообщение с токеном для безопасности
    await message.delete()
    
    token = message.text.strip()
    
    # Проверяем токен
    try:
        jira = JiraService(token=token)
        if not jira.test_connection():
            await message.answer("❌ Ошибка: неверный токен. Пожалуйста, проверьте токен и попробуйте снова.")
            return
        
        # Получаем информацию о пользователе для проверки
        user_info = jira.client.myself()
        
        # Сохраняем токен в базу
        db = get_db()
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.jira_token = token
        else:
            user = User(telegram_id=message.from_user.id, jira_token=token)
            db.add(user)
        db.commit()
        
        await state.finish()
        await message.answer(
            f"✅ Токен успешно сохранен!\n"
            f"Вы авторизованы как: {user_info.get('displayName')}\n\n"
            f"Теперь вы можете использовать следующие команды:\n"
            f"/worklog - Получить отчет о работе за последние 3 дня\n"
            f"/get_issue - Получить информацию о задаче"
        )
    except Exception as e:
        logger.error(f"Error setting token: {e}")
        await message.answer(
            "❌ Ошибка при проверке токена. Убедитесь, что:\n"
            "1. Токен введен правильно\n"
            "2. У вас есть доступ к Jira\n"
            "3. Токен не истек\n\n"
            "Попробуйте получить новый токен и установить его снова."
        )

@dp.message_handler(commands=['remove_token'])
async def remove_token_command(message: types.Message):
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        user.jira_token = None
        db.commit()
        await message.reply(
            "✅ Токен успешно удален.\n"
            "Вы можете установить новый токен с помощью команды /set_token"
        )
    else:
        await message.reply("❌ У вас не установлен токен.")

@dp.message_handler(commands=['get_issue'])
async def get_issue_command(message: types.Message):
    await UserStates.waiting_for_issue_key.set()
    await message.reply("Введите ключ задачи (например, PROJ-123):")

@dp.message_handler(state=UserStates.waiting_for_issue_key)
async def process_issue_key(message: types.Message, state: FSMContext):
    issue_key = message.text.strip().upper()
    
    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        await message.reply("❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
        await state.finish()
        return
    
    try:
        jira = JiraService(token=user.jira_token)
        issue = jira.get_issue(issue_key)
        
        response = format_issue_message(
            issue_key=issue.key,
            summary=issue.fields.summary,
            status=issue.fields.status.name
        )
        await message.reply(response)
    except Exception as e:
        logger.error(f"Error getting issue: {e}")
        await message.reply(f"❌ Ошибка при получении задачи: {str(e)}")
    
    await state.finish()

async def on_startup(dp):
    logger.info("Бот запущен")

async def on_shutdown(dp):
    logger.info("Бот остановлен")

def start_bot():
    """Запуск бота"""
    from aiogram import executor
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
