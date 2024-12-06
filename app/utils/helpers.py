from datetime import datetime
from app.core.config import settings

def format_datetime(dt: datetime) -> str:
    """Format datetime to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_worklog_message(worklog_entries: dict) -> str:
    """Форматирование сообщения с отчетом о раоте."""
    if not worklog_entries:
        return "За последние 3 дня нет записей о работе."

    message = "📊 *Отчет о затраченном времени за последние 3 дня*\n\n"

    for issue_key, entries in worklog_entries.items():
        message += (
            f"🔹 *Задача:* [{issue_key}]({settings.JIRA_URL}/browse/{issue_key})\n"
        )
        message += f"*Название:* {entries[0]['issue_summary']}\n\n"

        for entry in entries:
            date = parse_jira_datetime(entry["date"]).strftime("%d-%m-%y %H:%M")
            message += f"⏰ {date}\n"
            message += f"⌛️ *Затрачено:* {entry['time_spent']}\n"
            if entry["comment"]:
                message += f"💬 *Комментарий:*\n{entry['comment']}\n"
            message += "\n"

        message += "─────────────────\n"

    return message


def parse_jira_datetime(dt_str: str) -> datetime:
    """Parse Jira datetime string to datetime object."""
    try:
        return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    except ValueError:
        try:
            return datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")

def format_issue_message(issue_key: str, summary: str, status: str) -> str:
    """Format Jira issue message for Telegram."""
    return f"🎯 *Задача:* [{issue_key}]({settings.JIRA_URL}/browse/{issue_key})\n📝 *Название:* {summary}\n📊 *Статус:* {status}"
