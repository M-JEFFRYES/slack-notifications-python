# Slack Notifications Python

`SlackNotifications` is a lightweight, extensible Python library that simplifies sending rich notifications to Slack channels via incoming webhooks.

## Installation

```
pip install slack-notifications-python
```

## Quick Start

```
from typing import Dict, List

from traitlets import Any

from SlackNotifications.slack import (
    SlackChannelConfig,
    SlackNotificationService,
    SlackNotificationServiceConfig,
)


class ExtendedSlackNotificationService(SlackNotificationService):
    def __init__(self, config: SlackNotificationServiceConfig) -> None:
        super().__init__(config)

    def example_custom_method(
        self, channel_reference: str, title: str, line1: str, line2: str, line3: str
    ) -> None:
        blocks: List[Dict[str, Any]] = [
            self.divider_block(),
            self.section_block(self.bold_text(title)),
            self.section_block(self.italic_text(line1)),
            self.section_block(self.italic_text(line2)),
            self.section_block(self.italic_text(line3)),
            self.footer_block("Example Custom Message"),
        ]

        self.send_message(channel_reference, blocks)


# Example configuration for slack channels
channel_configs = [
    SlackChannelConfig(
        channel_reference="alerts",
        channel_webhook_url="https://hooks.slack.com/services/T00000000/B00000000/FAKEFAKEFAKEFAKEFAKEFAKE",
    ),
    SlackChannelConfig(
        channel_reference="notifications",
        channel_webhook_url="https://hooks.slack.com/services/T00000000/B00000000/FAKEFAKEFAKEFAKEFAKEFAKE",
    ),
]

# Initialize the Slack notification service
service_config = SlackNotificationServiceConfig(
    channels=channel_configs,
    send_to_slack=True,
    verbose=True,
)

# Initialise the extended service
slack_service = ExtendedSlackNotificationService(config=service_config)

# Example of sending a message
slack_service.example_custom_method(
    channel_reference="alerts",
    title="Alert Title",
    line1="This is the first line of the alert.",
    line2="This is the second line of the alert.",
    line3="This is the third line of the alert.",
)

```
