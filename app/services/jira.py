from jira import JIRA
from app.core.config import settings
from datetime import datetime, timedelta

class JiraService:
    def __init__(self, token: str):
        """
        Initialize Jira client with token.
        
        Args:
            token (str): Personal Jira API token
        """
        self.client = JIRA(
            server=settings.JIRA_URL,
            token_auth=token
        )

    def get_issue(self, issue_key: str):
        """Get issue by key."""
        return self.client.issue(issue_key)

    def get_issues_in_status(self, status: str, project: str = None):
        """Get all issues in specific status."""
        jql = f"status = '{status}'"
        if project:
            jql += f" AND project = {project}"
        return self.client.search_issues(jql)

    def update_issue_status(self, issue_key: str, status_name: str):
        """Update issue status."""
        issue = self.get_issue(issue_key)
        transitions = self.client.transitions(issue)
        for t in transitions:
            if t['name'].lower() == status_name.lower():
                self.client.transition_issue(issue, t['id'])
                return True
        return False

    def test_connection(self) -> bool:
        """Test if the Jira connection is working."""
        try:
            self.client.myself()
            return True
        except Exception:
            return False

    def get_recent_worklog(self, days: int = 3) -> dict:
        """
        Get worklog entries for the current user based on current time period.
        
        Returns:
            dict: Dictionary with issue keys as keys and worklog entries as values
        """
        today = datetime.now()
        weekday = today.weekday()  # 0 = понедельник, 6 = воскресенье
        current_time = today.time()
        mid_day = datetime.strptime("14:30", "%H:%M").time()
        
        # Определяем начальную дату для запроса в зависимости от текущего дня и времени
        if weekday == 0 and current_time <= mid_day:  # Понедельник до 14:30
            days = 3  # С пятницы 14:30
        elif weekday == 0 and current_time > mid_day:  # Понедельник после 14:30
            days = 0  # С понедельника 14:30
        elif weekday == 1:  # Вторник
            days = 1
        elif weekday == 2 and current_time <= mid_day:  # Среда до 14:30
            days = 2
        elif weekday == 2 and current_time > mid_day:  # Среда после 14:30
            days = 0  # С среды 14:30
        elif weekday == 3:  # Четверг
            days = 1
        elif weekday == 4 and current_time <= mid_day:  # Пятница до 14:30
            days = 2
        elif weekday == 4 and current_time > mid_day:  # Пятница после 14:30
            days = 0  # С пятницы 14:30
        elif weekday == 5:  # Суббота
            days = 1
        else:  # Воскресенье
            days = 2

        # Формируем JQL запрос для поиска всех задач с журналом работ пользователя
        jql_query = f"worklogAuthor = currentUser() AND worklogDate >= startOfDay(-{days})"

        # Получаем задачи
        issues = self.client.search_issues(jql_query, maxResults=100)

        worklog_entries = {}
        days_ago = today - timedelta(days=days)

        # Обрабатываем каждую задачу
        for issue in issues:
            worklogs = self.client.worklogs(issue.key)

            for worklog in worklogs:
                worklog_date = datetime.strptime(worklog.started[:10], "%Y-%m-%d")

                if worklog_date.date() >= days_ago.date():
                    if issue.key not in worklog_entries:
                        worklog_entries[issue.key] = []

                    worklog_entries[issue.key].append({
                        "issue_key": issue.key,
                        "issue_summary": issue.fields.summary,
                        "date": worklog.started,
                        "time_spent": worklog.timeSpent,
                        "time_spent_seconds": worklog.timeSpentSeconds,
                        "comment": worklog.comment,
                        "author": worklog.author.displayName,
                        "created": worklog.created,
                        "updated": worklog.updated,
                    })

        # Сортируем записи по дате
        for key in worklog_entries:
            worklog_entries[key].sort(key=lambda x: x["date"], reverse=True)

        return worklog_entries
