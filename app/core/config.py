import os
from dotenv import load_dotenv

load_dotenv()

class Settings:

    BASE_DIR = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )

    FILES_DIR = os.path.join(BASE_DIR, "app/config_files")

    # Jira settings
    JIRA_URL = os.getenv("JIRA_URL")

    # Telegram settings
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")

    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sql_app.db")

    # Ollama settings
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def __str__(self):
        """Вывод всех настроек в виде строки."""
        settings_dict = {
            "BASE_DIR": self.BASE_DIR,
            "FILES_DIR": self.FILES_DIR,
            "JIRA_URL": self.JIRA_URL,
            "TELEGRAM_BOT_TOKEN": self.TELEGRAM_BOT_TOKEN,
            "DATABASE_URL": self.DATABASE_URL,
            "OLLAMA_HOST": self.OLLAMA_HOST,
        }

        return "\n".join([f"{key}: {value}" for key, value in settings_dict.items()])


settings = Settings()
print(settings)
