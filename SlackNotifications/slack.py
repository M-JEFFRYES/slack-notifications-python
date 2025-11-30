from dataclasses import dataclass
from logging import getLogger
from typing import Any, Dict, List

from slack_sdk.webhook import WebhookClient

from SlackNotifications.exceptions import (
    SlackNotificationChannelDuplicateReferenceException,
    SlackNotificationChannelNotFoundException,
    SlackNotificationSendFailedException,
)

logger = getLogger(__file__)


@dataclass
class SlackChannelConfig:
    channel_reference: str
    channel_webhook_url: str


@dataclass
class SlackNotificationServiceConfig:
    channels: List[SlackChannelConfig]
    send_to_slack: bool = True
    verbose: bool = False


class SlackNotificationService:
    send_to_slack: bool
    verbose: bool
    channels: Dict[str, WebhookClient]

    def __init__(self, config: SlackNotificationServiceConfig) -> None:
        self.send_to_slack = config.send_to_slack
        self.verbose = config.verbose
        self.load_channel_webhooks(config.channels)

    def load_channel_webhooks(self, channel_configs: List[SlackChannelConfig]) -> None:
        channel_refs = [cc.channel_reference for cc in channel_configs]
        if len(channel_refs) != len(set(channel_refs)):
            raise SlackNotificationChannelDuplicateReferenceException(channel_refs)

        self.channels = {
            cc.channel_reference: WebhookClient(cc.channel_webhook_url) for cc in channel_configs
        }

        if self.verbose:
            logger.info(
                "SlackNotificationService initialized with the following channels: "
                f"{', '.join(list(self.channels.keys()))}"
            )

    def get_webhook(self, channel_reference: str) -> WebhookClient:
        channel_webhook = self.channels.get(channel_reference)
        if channel_webhook is None:
            raise SlackNotificationChannelNotFoundException(channel_reference)
        return channel_webhook

    def send_message_to_slack(self, reference: str, blocks: List[Dict[str, Any]]) -> None:
        webhook = self.get_webhook(reference)
        response = webhook.send(blocks=blocks)

        if response.status_code != 200:
            raise SlackNotificationSendFailedException(
                reference, response.status_code, response.body
            )

        if self.verbose:
            logger.info(
                f"Message sent successfully to {reference} channel. Slack response:"
                f" {response.status_code} - {response.body}"
            )

    def send_dummy_message(self, reference: str, blocks: List[Dict[str, Any]]) -> None:
        logger.info(f"[DUMMY SLACK MESSAGE] {reference} : {blocks}")

    def send_message(self, reference: str, blocks: List[Dict[str, Any]]) -> None:
        if self.send_to_slack:
            self.send_message_to_slack(reference, blocks)
            return
        self.send_dummy_message(reference, blocks)

    def generic_message_blocks(self, title: str, message: str) -> List[Dict[str, Any]]:
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n{message}"},
            },
        ]

    def divider_block(self) -> Dict[str, Any]:
        return {"type": "divider"}

    def section_block(self, text: str) -> Dict[str, Any]:
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    def url_link(self, text: str, url: str) -> str:
        return f"<{url}|{text}>"

    def list_items(self, items: List[str]) -> str:
        return "\n".join([f"• {item}" for item in items])

    def list_items_numbered(self, items: List[str]) -> str:
        return "\n".join([f"{i + 1}. {item}" for i, item in enumerate(items)])

    def bold_text(self, text: str) -> str:
        return f"*{text}*"

    def italic_text(self, text: str) -> str:
        return f"_{text}_"

    def footer_block(self, footer_message: str) -> Dict[str, Any]:
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": footer_message}],
        }
