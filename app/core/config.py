import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Jira settings
    JIRA_URL = os.getenv("JIRA_URL")
    
    # Telegram settings
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

settings = Settings() 