from typing import List


class SlackNotificationChannelDuplicateReferenceException(Exception):
    def __init__(self, channel_names: List[str]) -> None:
        channel_names = sorted(channel_names)
        channel_names_str = ", ".join(channel_names)
        super().__init__(
            f"Duplicate referecne for slack notification channel references=[{channel_names_str}]"
        )


class SlackNotificationChannelNotFoundException(Exception):
    def __init__(self, channel_name: str) -> None:
        super().__init__(f"Slack notification channel '{channel_name}' not found.")


class SlackNotificationSendFailedException(Exception):
    def __init__(self, channel_name: str, status_code: int, response_body: str) -> None:
        super().__init__(
            f"Failed to send Slack notification to channel '{channel_name}'. "
            f"Status Code: {status_code}, Response: {response_body}"
        )
