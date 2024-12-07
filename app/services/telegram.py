import logging
import telebot
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage

from app.core.config import settings
from app.core.database import SessionLocal, User
from app.services.jira import JiraService
from app.services.neuro import send_message
from app.utils.helpers import format_issue_message, format_worklog_message, worklog_to_prompt

from jira import JIRAError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота и хранилища состояний
state_storage = StateMemoryStorage()
bot = telebot.TeleBot(settings.TELEGRAM_BOT_TOKEN, state_storage=state_storage)

class UserStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_issue_key = State()

def get_db():
    logger.debug("Getting database session")
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()
        logger.debug("Database session closed")

@bot.message_handler(commands=['start'])
def start_command(message):
    logger.info(f"User {message.from_user.id} started the bot")
    bot.reply_to(
        message,
        "Привет! Я бот для работы с Jira. "
        "Для начала работы установите ваш токен Jira с помощью команды /set_token\n\n"
        "Доступные команды:\n"
        "/set_token - Установить токен Jira\n"
        "/remove_token - Удалить токен\n"
        "/get_issue - Получить информацию о задаче\n"
        "/worklog - Получить отчет о работе за последние 3 дня\n"
        "/help - Показать справку"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    logger.info(f"User {message.from_user.id} requested help")
    bot.reply_to(
        message,
        "Доступные команды:\n"
        "/set_token - Установить токен Jira\n"
        "/remove_token - Удалить токен\n"
        "/get_issue - Получить информацию о задаче\n"
        "/worklog - Получить отчет о работе за последние 3 дня\n"
        "/help - Показать справку"
    )

@bot.message_handler(commands=['worklog'])
def worklog_command(message):
    """Получение отчета о работе за последние 3 дня."""
    logger.info(f"User {message.from_user.id} requested worklog")
    
    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        bot.reply_to(message, "❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
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
            bot.reply_to(message, response, parse_mode="MarkdownV2", disable_web_page_preview=True)
        except Exception as parse_error:
            # Если возникла ошибка парсинга, отправляем без форматирования
            logger.error(f"Error parsing markdown: {parse_error}")
            bot.reply_to(message, response, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Error getting worklog: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении отчета: {str(e)}")

@bot.message_handler(commands=["worklog_neuro"])
def worklog_neuro_command(message):
    """Получение отчета о работе за последние 3 дня с помощью нейросети."""
    logger.info(f"User {message.from_user.id} requested neuro worklog")
    
    # Проверяем наличие токена  
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        bot.reply_to(
            message,
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
        message_wait = bot.reply_to(message, f"Отправляю данные в нейросеть.\nЭто может занять некоторое время...")
        response = send_message(formatted_worklog)
        bot.delete_message(message_wait.chat.id, message_wait.message_id)
        bot.reply_to(message, response)
    except Exception as e:
        logger.error(f"Error getting neuro worklog: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении отчета: {str(e)}")

@bot.message_handler(commands=['set_token'])
def set_token_command(message):
    logger.info(f"User {message.from_user.id} initiated token setup")
    # Удаляем сообщение с командой для безопасности
    bot.delete_message(message.chat.id, message.message_id)
    
    # Проверяем, есть ли уже токен у пользователя
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        logger.info(f"User {message.from_user.id} already has a token")
        bot.send_message(
            message.chat.id,
            "У вас уже установлен токен. Хотите установить новый?\n"
            "Используйте /remove_token для удаления текущего токена, "
            "а затем /set_token для установки нового."
        )
        return
    
    bot.set_state(message.from_user.id, UserStates.waiting_for_token, message.chat.id)
    bot.send_message(
        message.chat.id,
        "Пожалуйста, отправьте ваш токен Jira.\n"
        "Его можно получить в настройках вашего аккаунта Jira:\n"
        "1. Перейдите в Profile -> Security -> Create and manage API tokens\n"
        "2. Нажмите Create API token\n"
        "3. Скопируйте и отправьте токен в следующем сообщении\n\n"
        "⚠️ Сообщение с токеном будет автоматически удалено для безопасности"
    )

@bot.message_handler(state=UserStates.waiting_for_token)
def process_token(message):
    logger.info(f"Processing token for user {message.from_user.id}")
    # Удаляем сообщение с токеном для безопасности
    bot.delete_message(message.chat.id, message.message_id)
    
    token = message.text.strip()
    
    # Проверяем токен
    try:
        logger.debug("Testing Jira connection")
        jira = JiraService(token=token)
        if not jira.test_connection():
            logger.warning(f"Invalid token provided by user {message.from_user.id}")
            bot.send_message(message.chat.id, "❌ Ошибка: неверный токен. Пожалуйста, проверьте токен и попробуйте снова.")
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
        
        bot.delete_state(message.from_user.id, message.chat.id)
        logger.info(f"Token successfully set for user {message.from_user.id}")
        bot.send_message(
            message.chat.id,
            f"✅ Токен успешно сохранен!\n"
            f"Вы авторизованы как: {user_info.get('displayName')}\n\n"
            f"Теперь вы можете использовать следующие команды:\n"
            f"/worklog - Получить отчет о работе за последние 3 дня\n"
            f"/get_issue - Получить информацию о задаче"
        )
    except Exception as e:
        logger.error(f"Error setting token for user {message.from_user.id}: {e}")
        bot.send_message(
            message.chat.id,
            "❌ Ошибка при проверке токена. Убедитесь, что:\n"
            "1. Токен введен правильно\n"
            "2. У вас есть доступ к Jira\n"
            "3. Токен не истек\n\n"
            "Попробуйте получить новый токен и установить его снова."
        )

@bot.message_handler(commands=['remove_token'])
def remove_token_command(message):
    logger.info(f"User {message.from_user.id} requested token removal")
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if user and user.jira_token:
        user.jira_token = None
        db.commit()
        logger.info(f"Token removed for user {message.from_user.id}")
        bot.reply_to(
            message,
            "✅ Токен успешно удален.\n"
            "Вы можете установить новый токен с помощью команды /set_token"
        )
    else:
        logger.warning(f"No token found for user {message.from_user.id}")
        bot.reply_to(message, "❌ У вас не установлен токен.")

@bot.message_handler(commands=['get_issue'])
def get_issue_command(message):
    logger.info(f"User {message.from_user.id} initiated issue request")
    bot.set_state(message.from_user.id, UserStates.waiting_for_issue_key, message.chat.id)
    bot.reply_to(
        message,
        "Введите ключ задачи (например, PROJ-123):"
    )

@bot.message_handler(state=UserStates.waiting_for_issue_key)
def process_issue_key(message):
    logger.info(f"Processing issue key for user {message.from_user.id}")
    issue_key = message.text.strip().upper()

    # Проверяем наличие токена
    db = get_db()
    user = db.query(User).filter(User.telegram_id == message.from_user.id).first()
    if not user or not user.jira_token:
        logger.warning(f"User {message.from_user.id} has no token")
        bot.reply_to(message, "❌ Токен не установлен. Используйте /set_token чтобы установить токен.")
        bot.delete_state(message.from_user.id, message.chat.id)
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
        bot.reply_to(message, response, parse_mode="Markdown")
        logger.info(f"Issue {issue_key} successfully retrieved")
    except JIRAError as e:
        logger.error(f"Jira error getting issue {issue_key}: {e.text}")
        bot.reply_to(message, f"❌ Ошибка при получении задачи: {e.text}")
    except Exception as e:
        logger.error(f"Error getting issue {issue_key}: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении задачи: {str(e)}")

    bot.delete_state(message.from_user.id, message.chat.id)

def start_bot():
    """Запуск бота"""
    logger.info("Starting bot")
    bot.infinity_polling()
