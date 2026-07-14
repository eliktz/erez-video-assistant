"""The interface layer sits behind this port.

Telegram now; WhatsApp when Meta's paperwork clears. Swapping one for the other
should touch this folder and nothing else.
"""

from typing import Protocol


class Notifier(Protocol):
    def send(self, text: str) -> None:
        """Deliver a message to its recipient. Raises on permanent failure."""
        ...
