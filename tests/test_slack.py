import logging
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

from SlackNotifications.exceptions import (
    SlackNotificationChannelDuplicateReferenceException,
    SlackNotificationChannelNotFoundException,
    SlackNotificationSendFailedException,
)
from SlackNotifications.slack import (
    SlackChannelConfig,
    SlackNotificationService,
    SlackNotificationServiceConfig,
)


@pytest.fixture
def channel_configs() -> List[SlackChannelConfig]:
    return [
        SlackChannelConfig(
            channel_reference="alerts",
            channel_webhook_url="https://hooks.slack.com/services/T000/A000/alerts",
        ),
        SlackChannelConfig(
            channel_reference="errors",
            channel_webhook_url="https://hooks.slack.com/services/T000/A000/errors",
        ),
    ]


@pytest.fixture
def service_config(channel_configs: List[SlackChannelConfig]) -> SlackNotificationServiceConfig:
    return SlackNotificationServiceConfig(
        channels=channel_configs,
        send_to_slack=True,
        verbose=False,
    )


@pytest.fixture
def service_for_helpers(service_config: SlackNotificationServiceConfig) -> SlackNotificationService:
    # No need to hit real Slack webhooks for helper tests
    return SlackNotificationService(service_config)


class TestInitialization:
    @patch("SlackNotifications.slack.WebhookClient")
    def test_init_creates_webhook_clients(
        self,
        mock_webhook_client: MagicMock,
        service_config: SlackNotificationServiceConfig,
        channel_configs: List[SlackChannelConfig],
    ) -> None:
        SlackNotificationService(service_config)

        # One WebhookClient per channel config
        assert mock_webhook_client.call_count == len(channel_configs)
        urls_called = {call.args[0] for call in mock_webhook_client.call_args_list}
        assert urls_called == {cc.channel_webhook_url for cc in channel_configs}

    @patch("SlackNotifications.slack.WebhookClient")
    def test_init_stores_channels_dict(
        self,
        mock_webhook_client: MagicMock,
        service_config: SlackNotificationServiceConfig,
        channel_configs: List[SlackChannelConfig],
    ) -> None:
        mock_webhook_client.side_effect = [
            MagicMock(name="alerts"),
            MagicMock(name="errors"),
        ]

        service = SlackNotificationService(service_config)

        assert set(service.channels.keys()) == {"alerts", "errors"}
        assert isinstance(service.channels["alerts"], MagicMock)

    def test_init_logs_channels_when_verbose(
        self, channel_configs: List[SlackChannelConfig], caplog: pytest.LogCaptureFixture
    ) -> None:
        config = SlackNotificationServiceConfig(
            channels=channel_configs,
            send_to_slack=True,
            verbose=True,
        )

        with caplog.at_level(logging.INFO):
            SlackNotificationService(config)

        assert "SlackNotificationService initialized with the following channels:" in caplog.text
        assert "alerts" in caplog.text
        assert "errors" in caplog.text

    def test_duplicate_channel_references_raise_exception(self) -> None:
        duplicate_configs = [
            SlackChannelConfig(
                channel_reference="alerts",
                channel_webhook_url="https://hooks.slack.com/services/T000/FAKEFAKE/alerts",
            ),
            SlackChannelConfig(
                channel_reference="alerts",
                channel_webhook_url="https://hooks.slack.com/services/T000/FAKEFAKE/other-alerts",
            ),
        ]

        config = SlackNotificationServiceConfig(
            channels=duplicate_configs,
            send_to_slack=True,
            verbose=False,
        )

        with pytest.raises(SlackNotificationChannelDuplicateReferenceException):
            SlackNotificationService(config)


class TestGetWebhook:
    @patch("SlackNotifications.slack.WebhookClient")
    def test_get_webhook_returns_existing_channel(
        self, mock_webhook_client: MagicMock, service_config: SlackNotificationServiceConfig
    ) -> None:
        mock_webhook_instance = MagicMock()
        mock_webhook_client.return_value = mock_webhook_instance

        service = SlackNotificationService(service_config)

        webhook = service.get_webhook("alerts")
        assert webhook is mock_webhook_instance

    @patch("SlackNotifications.slack.WebhookClient")
    def test_get_webhook_raises_for_unknown_channel(
        self, service_config: SlackNotificationServiceConfig
    ) -> None:
        service = SlackNotificationService(service_config)

        with pytest.raises(SlackNotificationChannelNotFoundException) as exc:
            service.get_webhook("nonexistent")

        assert "nonexistent" in str(exc.value)


class TestSendMessageToSlack:
    def test_send_message_to_slack_success(
        self, service_config: SlackNotificationServiceConfig
    ) -> None:
        service = SlackNotificationService(service_config)

        mock_webhook = MagicMock()
        mock_response = MagicMock(status_code=200, body="ok")
        mock_webhook.send.return_value = mock_response
        service.channels = {"alerts": mock_webhook}

        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}
        ]

        service.send_message_to_slack("alerts", blocks)

        mock_webhook.send.assert_called_once_with(blocks=blocks)

    def test_send_message_to_slack_failure_raises_exception(
        self, service_config: SlackNotificationServiceConfig
    ) -> None:
        service = SlackNotificationService(service_config)

        mock_webhook = MagicMock()
        mock_response = MagicMock(status_code=500, body="internal error")
        mock_webhook.send.return_value = mock_response
        service.channels = {"alerts": mock_webhook}

        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}
        ]

        with pytest.raises(SlackNotificationSendFailedException) as exc:
            service.send_message_to_slack("alerts", blocks)

        mock_webhook.send.assert_called_once_with(blocks=blocks)
        assert "alerts" in str(exc.value)
        assert "500" in str(exc.value)

    def test_send_message_to_slack_logs_when_verbose(
        self, service_config: SlackNotificationServiceConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        service = SlackNotificationService(service_config)
        service.verbose = True

        mock_webhook = MagicMock()
        mock_response = MagicMock(status_code=200, body="ok")
        mock_webhook.send.return_value = mock_response
        service.channels = {"alerts": mock_webhook}

        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}
        ]

        with caplog.at_level(logging.INFO):
            service.send_message_to_slack("alerts", blocks)

        assert "Message sent successfully to alerts channel" in caplog.text
        assert "200" in caplog.text
        assert "ok" in caplog.text


class TestSendMessageRouting:
    def test_send_message_uses_real_slack_when_flag_true(
        self, service_config: SlackNotificationServiceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SlackNotificationService(service_config)
        service.send_to_slack = True

        mock_real = MagicMock()
        mock_dummy = MagicMock()
        monkeypatch.setattr(service, "send_message_to_slack", mock_real)
        monkeypatch.setattr(service, "send_dummy_message", mock_dummy)

        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}
        ]

        service.send_message("alerts", blocks)

        mock_real.assert_called_once_with("alerts", blocks)
        mock_dummy.assert_not_called()

    def test_send_message_uses_dummy_when_flag_false(
        self, service_config: SlackNotificationServiceConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        service = SlackNotificationService(service_config)
        service.send_to_slack = False

        mock_real = MagicMock()
        mock_dummy = MagicMock()
        monkeypatch.setattr(service, "send_message_to_slack", mock_real)
        monkeypatch.setattr(service, "send_dummy_message", mock_dummy)

        blocks: List[Dict[str, Any]] = [
            {"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}
        ]

        service.send_message("alerts", blocks)

        mock_dummy.assert_called_once_with("alerts", blocks)
        mock_real.assert_not_called()

    def test_send_dummy_message_logs(
        self, service_config: SlackNotificationServiceConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        service = SlackNotificationService(service_config)

        blocks: List[Dict[str, Any]] = [{"dummy": "block"}]
        with caplog.at_level(logging.INFO):
            service.send_dummy_message("alerts", blocks)

        assert "[DUMMY SLACK MESSAGE] alerts : [{'dummy': 'block'}]" in caplog.text


class TestHelperBlocksAndFormatting:
    def test_generic_message_blocks(self, service_for_helpers: SlackNotificationService) -> None:
        blocks = service_for_helpers.generic_message_blocks("Title", "Message")
        assert isinstance(blocks, list)
        assert len(blocks) == 1
        block = blocks[0]
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert "*Title*" in block["text"]["text"]
        assert "Message" in block["text"]["text"]

    def test_divider_block(self, service_for_helpers: SlackNotificationService) -> None:
        block = service_for_helpers.divider_block()
        assert block == {"type": "divider"}

    def test_section_block(self, service_for_helpers: SlackNotificationService) -> None:
        text = "Some text"
        block = service_for_helpers.section_block(text)
        assert block["type"] == "section"
        assert block["text"]["type"] == "mrkdwn"
        assert block["text"]["text"] == text

    def test_url_link(self, service_for_helpers: SlackNotificationService) -> None:
        result = service_for_helpers.url_link("click here", "https://example.com")
        assert result == "<https://example.com|click here>"

    def test_list_items(self, service_for_helpers: SlackNotificationService) -> None:
        items = ["first", "second", "third"]
        result = service_for_helpers.list_items(items)
        lines = result.split("\n")
        assert lines == ["• first", "• second", "• third"]

    def test_list_items_numbered(self, service_for_helpers: SlackNotificationService) -> None:
        items = ["first", "second", "third"]
        result = service_for_helpers.list_items_numbered(items)
        lines = result.split("\n")
        assert lines == ["1. first", "2. second", "3. third"]

    def test_bold_text(self, service_for_helpers: SlackNotificationService) -> None:
        assert service_for_helpers.bold_text("bold") == "*bold*"

    def test_italic_text(self, service_for_helpers: SlackNotificationService) -> None:
        assert service_for_helpers.italic_text("italics") == "_italics_"

    def test_footer_block(self, service_for_helpers: SlackNotificationService) -> None:
        footer = "Footer message"
        block = service_for_helpers.footer_block(footer)
        assert block["type"] == "context"
        assert "elements" in block
        assert block["elements"][0]["type"] == "mrkdwn"
        assert block["elements"][0]["text"] == footer
