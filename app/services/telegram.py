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
from app.services.neuro import send_message
from app.utils.helpers import format_issue_message, format_worklog_message, worklog_to_prompt

from jira import JIRAError

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
    logger.debug("Getting database session")
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()
        logger.debug("Database session closed")

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    logger.info(f"User {message.from_user.id} started the bot")
    await message.reply(
        "Привет! Я бот для работы с Jira. "
        "Для начала работы установите ваш токен Jira с помощью команды /set_token\n\n"
        "Доступные команды:\n"
        "/set_token - Установить токен Jira\n"
        "/remove_token - Удалить токен\n"
        "/get_issue - Получить информацию о задаче\n"
        "/worklog - Получить отчет о работе за последние 3 дня\n"
        "/help - Показать справку"
    )

@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
    logger.info(f"User {message.from_user.id} requested help")
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
    logger.info(f"User {message.from_user.id} requested worklog")
    
    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        await message.reply("❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
        return

    try:
        # Получаем данные из Jira
        logger.debug(f"Getting worklog for user {message.from_user.id}")
        jira = JiraService(token=user.jira_token)
        worklog_entries = jira.get_recent_worklog(days=3)

        # Форматируем и отправляем сообщение
        response = format_worklog_message(worklog_entries)
        try:
            logger.debug("Sending formatted worklog message")
            await message.reply(response, parse_mode="MarkdownV2", disable_web_page_preview=True)
        except Exception as parse_error:
            # Если возникла ошибка парсинга, отправляем без форматирования
            logger.error(f"Error parsing markdown: {parse_error}")
            await message.reply(response, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error getting worklog: {e}")
        await message.reply(f"❌ Ошибка при получении отчета: {str(e)}")


@dp.message_handler(commands=["worklog_neuro"])
async def worklog_neuro_command(message: types.Message):
    """Получение отчета о работе за последние 3 дня с помощью нейросети."""
    logger.info(f"User {message.from_user.id} requested neuro worklog")
    
    # Проверяем наличие токена  
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        await message.reply(
            "❌ Токен не установлен. Используйте /set_token чтобы установить токен."
        )
        return

    try:
        # Получаем данные из Jira
        logger.debug(f"Getting worklog for user {message.from_user.id}")
        jira = JiraService(token=user.jira_token)
        worklog_entries = jira.get_recent_worklog(days=3)

        formatted_worklog = worklog_to_prompt(worklog_entries)
        # Форматируем и отправляем сообщение
        logger.debug("Sending worklog to neuro service")
        await message.reply(f"Отправляю данные в нейросеть.\nЭто может занять некоторое время...")
        response = send_message(formatted_worklog)
        await message.reply(response)
    except Exception as e:
        logger.error(f"Error getting neuro worklog: {e}")
        await message.reply(f"❌ Ошибка при получении отчета: {str(e)}")


@dp.message_handler(commands=['set_token'])
async def set_token_command(message: types.Message):
    logger.info(f"User {message.from_user.id} initiated token setup")
    # Удаляем сообщение с командой для безопасности
    await message.delete()
    
    # Проверяем, есть ли уже токен у пользователя
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        logger.info(f"User {message.from_user.id} already has a token")
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
    logger.info(f"Processing token for user {message.from_user.id}")
    # Удаляем сообщение с токеном для безопасности
    await message.delete()
    
    token = message.text.strip()
    
    # Проверяем токен
    try:
        logger.debug("Testing Jira connection")
        jira = JiraService(token=token)
        if not jira.test_connection():
            logger.warning(f"Invalid token provided by user {message.from_user.id}")
            await message.answer("❌ Ошибка: неверный токен. Пожалуйста, проверьте токен и попробуйте снова.")
            return
        
        # Получаем информацию о пользователе для проверки
        user_info = jira.client.myself()
        
        # Сохраняем токен в базу
        logger.debug("Saving token to database")
        db = get_db()
        user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
        if user:
            user.jira_token = token
        else:
            user = User(telegram_id=message.from_user.id, jira_token=token)
            db.add(user)
        db.commit()
        
        await state.finish()
        logger.info(f"Token successfully set for user {message.from_user.id}")
        await message.answer(
            f"✅ Токен успешно сохранен!\n"
            f"Вы авторизованы как: {user_info.get('displayName')}\n\n"
            f"Теперь вы можете использовать следующие команды:\n"
            f"/worklog - Получить отчет о работе за последние 3 дня\n"
            f"/get_issue - Получить информацию о задаче"
        )
    except Exception as e:
        logger.error(f"Error setting token for user {message.from_user.id}: {e}")
        await message.answer(
            "❌ Ошибка при проверке токена. Убедитесь, что:\n"
            "1. Токен введен правильно\n"
            "2. У вас есть доступ к Jira\n"
            "3. Токен не истек\n\n"
            "Попробуйте получить новый токен и установить его снова."
        )

@dp.message_handler(commands=['remove_token'])
async def remove_token_command(message: types.Message):
    logger.info(f"User {message.from_user.id} requested token removal")
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        user.jira_token = None
        db.commit()
        logger.info(f"Token removed for user {message.from_user.id}")
        await message.reply(
            "✅ Токен успешно удален.\n"
            "Вы можете установить новый токен с помощью команды /set_token"
        )
    else:
        logger.warning(f"No token found for user {message.from_user.id}")
        await message.reply("❌ У вас не установлен токен.")

@dp.message_handler(commands=['get_issue'])
async def get_issue_command(message: types.Message):
    logger.info(f"User {message.from_user.id} initiated issue request")
    await UserStates.waiting_for_issue_key.set()
    await message.reply(
        "Введите ключ задачи (например, PROJ-123):", parse_mode="Markdown"
    )

@dp.message_handler(state=UserStates.waiting_for_issue_key)
async def process_issue_key(message: types.Message, state: FSMContext):
    logger.info(f"Processing issue key for user {message.from_user.id}")
    issue_key = message.text.strip().upper()

    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        await message.reply("❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
        await state.finish()
        return

    try:
        logger.debug(f"Getting issue {issue_key}")
        jira = JiraService(token=user.jira_token)
        issue = jira.get_issue(issue_key)

        response = format_issue_message(
            issue_key=issue.key,
            summary=issue.fields.summary,
            status=issue.fields.status.name
        )
        await message.reply(response, parse_mode="Markdown")
        logger.info(f"Issue {issue_key} successfully retrieved")
    except JIRAError as e:
        logger.error(f"Jira error getting issue {issue_key}: {e.text}")
        await message.reply(f"❌ Ошибка при получении задачи: {e.text}")
    except Exception as e:
        logger.error(f"Error getting issue {issue_key}: {e}")
        await message.reply(f"❌ Ошибка при получении задачи: {str(e)}")

    await state.finish()

async def on_startup(dp):
    logger.info("Бот запущен")

async def on_shutdown(dp):
    logger.info("Бот остановлен")

def start_bot():
    """Запуск бота"""
    logger.info("Starting bot")
    from aiogram import executor
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
