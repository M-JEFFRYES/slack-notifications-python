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
    """Service for sending formatted notifications to multiple Slack channels.

    Manages multiple Slack webhook channels with dry-run support and verbose logging.
    Provides helper methods for building common Slack block layouts.

    Example:
        service = SlackNotificationService(config)
        service.send_message("deployments", service.generic_message_blocks("Deploy", "v1.2.3"))
    """

    send_to_slack: bool
    """Whether to send actual messages to Slack or log as dummy."""

    verbose: bool
    """Enable detailed logging of Slack operations."""

    channels: Dict[str, WebhookClient]
    """Mapping of channel references to WebhookClient instances."""

    def __init__(self, config: SlackNotificationServiceConfig) -> None:
        """Initialize the service with configuration.

        Args:
            config: Configuration object containing send_to_slack, verbose, and channels.
        """
        self.send_to_slack = config.send_to_slack
        self.verbose = config.verbose
        self.load_channel_webhooks(config.channels)

    def load_channel_webhooks(self, channel_configs: List[SlackChannelConfig]) -> None:
        """Load and validate Slack channel webhook configurations.

        Validates no duplicate channel references exist and creates WebhookClient instances.

        Args:
            channel_configs: List of channel configuration objects.

        Raises:
            SlackNotificationChannelDuplicateReferenceException: If duplicate channel refs found.
        """

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
        """Retrieve WebhookClient for specified channel.

        Args:
            channel_reference: Unique identifier for the Slack channel.

        Returns:
            WebhookClient instance for the channel.

        Raises:
            SlackNotificationChannelNotFoundException: If channel not configured.
        """

        channel_webhook = self.channels.get(channel_reference)
        if channel_webhook is None:
            raise SlackNotificationChannelNotFoundException(channel_reference)
        return channel_webhook

    def send_message_to_slack(self, reference: str, blocks: List[Dict[str, Any]]) -> None:
        """Send message blocks to Slack channel via webhook.

        Args:
            reference: Channel reference identifier.
            blocks: List of Slack block dictionaries.

        Raises:
            SlackNotificationSendFailedException: If HTTP response not 200.
        """

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
        """Log message blocks instead of sending to Slack (dry-run mode).

        Args:
            reference: Channel reference identifier.
            blocks: List of Slack block dictionaries to log.
        """

        logger.info(f"[DUMMY SLACK MESSAGE] {reference} : {blocks}")

    def send_message(self, reference: str, blocks: List[Dict[str, Any]]) -> None:
        """Send message to Slack channel or log as dummy based on configuration.

        Args:
            reference: Channel reference identifier.
            blocks: List of Slack block dictionaries.
        """

        if self.send_to_slack:
            self.send_message_to_slack(reference, blocks)
            return
        self.send_dummy_message(reference, blocks)

    def generic_message_blocks(self, title: str, message: str) -> List[Dict[str, Any]]:
        """Create simple title + message Slack block layout.

        Args:
            title: Bold title text.
            message: Message body text.

        Returns:
            List containing single section block with formatted title and message.
        """
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{title}*\n{message}"},
            },
        ]

    def divider_block(self) -> Dict[str, Any]:
        """Create horizontal divider Slack block."""
        return {"type": "divider"}

    def section_block(self, text: str) -> Dict[str, Any]:
        """Create section block with mrkdwn text.

        Args:
            text: Text content supporting Slack mrkdwn formatting.

        Returns:
            Section block dictionary.
        """
        return {"type": "section", "text": {"type": "mrkdwn", "text": text}}

    def url_link(self, text: str, url: str) -> str:
        """Format Slack link syntax: <url|text>.

        Args:
            text: Display text for link.
            url: Target URL.

        Returns:
            Slack-formatted link string.
        """
        return f"<{url}|{text}>"

    def list_items(self, items: List[str]) -> str:
        """Format bullet list for Slack mrkdwn.

        Args:
            items: List of strings to bulletize.

        Returns:
            Newline-separated bullet list string.
        """
        return "\n".join([f"• {item}" for item in items])

    def list_items_numbered(self, items: List[str]) -> str:
        """Format numbered list for Slack mrkdwn.

        Args:
            items: List of strings to number.

        Returns:
            Newline-separated numbered list string.
        """
        return "\n".join([f"{i + 1}. {item}" for i, item in enumerate(items)])

    def bold_text(self, text: str) -> str:
        """Wrap text in Slack bold mrkdwn (*text*).

        Args:
            text: Text to bold.

        Returns:
            Bold-formatted string.
        """
        return f"*{text}*"

    def italic_text(self, text: str) -> str:
        """Wrap text in Slack italic mrkdwn (_text_).

        Args:
            text: Text to italicize.

        Returns:
            Italic-formatted string.
        """
        return f"_{text}_"

    def footer_block(self, footer_message: str) -> Dict[str, Any]:
        """Create footer context block with mrkdwn text.

        Args:
            footer_message: Text to display in footer.

        Returns:
            Context block dictionary with footer message.
        """
        return {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": footer_message}],
        }
