from datetime import datetime

def format_datetime(dt: datetime) -> str:
    """Format datetime to string."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

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
    return f"🎯 **Задача:** [{issue_key}]\n📝 **Название:** {summary}\n📊 **Статус:** {status}"
