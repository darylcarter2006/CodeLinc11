"""Outgoing email (password reset links). Amazon SES in AWS; an in-memory outbox locally."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(ABC):
    @abstractmethod
    async def send(self, message: EmailMessage) -> None:
        """Deliver the message; never raises (a failure is logged without the recipient)."""


class OutboxEmailSender(EmailSender):
    """Local development and tests: keeps messages in memory instead of sending them."""

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
        # Local only (settings refuse this sender elsewhere), so the link can be opened by hand.
        print(f"[local email] to {message.to}: {message.subject}\n{message.text}", flush=True)


class SesEmailSender(EmailSender):
    """Amazon SES v2. Credentials come from the ECS task role; nothing is stored in the app."""

    def __init__(self, sender: str, region: str, client: Any | None = None) -> None:
        if client is None:
            import boto3

            client = boto3.client("sesv2", region_name=region)
        self._client = client
        self._sender = sender

    async def send(self, message: EmailMessage) -> None:
        try:
            await asyncio.to_thread(
                self._client.send_email,
                FromEmailAddress=self._sender,
                Destination={"ToAddresses": [message.to]},
                Content={
                    "Simple": {
                        "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {"Data": message.text, "Charset": "UTF-8"},
                            "Html": {"Data": message.html, "Charset": "UTF-8"},
                        },
                    }
                },
            )
            logger.info("email_sent")
        except Exception as exc:
            logger.warning("email_failed", extra={"error_code": type(exc).__name__})
