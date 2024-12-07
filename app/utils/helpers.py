from datetime import datetime
from app.core.config import settings
import json

def format_datetime(dt: datetime) -> str:
    """Format datetime to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def escape_markdown(text: str) -> str:
    """Экранирование специальных символов для MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_worklog_message(worklog_entries: dict) -> str:
    """Форматирование сообщения с отчетом о работе."""
    if not worklog_entries:
        return "За последние 3 дня нет записей о работе\\."

    message = "📊 *Отчет о затраченном времени за последние 3 дня*\n\n"

    for issue_key, entries in worklog_entries.items():
        safe_issue_key = escape_markdown(issue_key)
        safe_url = escape_markdown(f"{settings.JIRA_URL}/browse/{issue_key}")
        safe_summary = escape_markdown(entries[0]['issue_summary'])
        
        message += f"🔹 *Задача:* [{safe_issue_key}]({safe_url})\n"
        message += f"*Название:* {safe_summary}\n\n"

        for entry in entries:
            date = parse_jira_datetime(entry["date"]).strftime("%d\\-%m\\-%y %H:%M")
            safe_time_spent = escape_markdown(entry['time_spent'])
            message += f"⏰ {date}\n"
            message += f"⌛️ *Затрачено:* {safe_time_spent}\n"
            if entry["comment"]:
                safe_comment = escape_markdown(entry['comment'])
                message += f"💬 *Комментарий:*\n{safe_comment}\n"
            message += "\n"

        message += "─────────────────\n"

    return message

def worklog_to_prompt(worklog_entries: dict) -> str:
    """Convert worklog entries to a prompt for the neuro service."""
    message = ""
    for issue_key, entries in worklog_entries.items():
        message += f"*Задача ({issue_key}):* {entries[0]['issue_summary']} \n"
        for entry in entries:
            if entry["comment"]:
                message += f"{entry['comment']}\n"
            message += "\n"
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
