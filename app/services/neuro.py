import ollama
from app.core.config import settings
import os
import re

# Инициализация клиента Ollama
ollama_client = ollama.Client(host=settings.OLLAMA_HOST)


def get_issue(client, model, message):
    response = client.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": message,
            },
        ],
    )
    if re.findall(r"[\u4e00-\u9fff]+", response["message"]["content"]):
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": message,
                },
            ],
        )
    return response["message"]["content"]


def send_message(message: str, model: str = "qwen2.5") -> str:
    """
    Отправляет сообщение в модель Ollama и возвращает ответ.

    Args:
        message (str): Текст сообщения для отправки
        model (str): Название модели (по умолчанию "qwen")

    Returns:
        str: Ответ от модели
    """
    try:
        # Загружаем модель из Modelfile
        modelfile_path = os.path.join(settings.FILES_DIR, "Modelfile")
        with open(modelfile_path, "r") as file:
            modelfile_content = file.read()
        ollama_client.create(model="worklog", modelfile=modelfile_content)
        return get_issue(ollama_client, model, str(message))
    except Exception as e:
        return f"Ошибка при отправке сообщения: {str(e)}"
