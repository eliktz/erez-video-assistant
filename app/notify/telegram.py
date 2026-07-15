"""Telegram delivery. Long polling: no webhook, no domain, no TLS cert."""

import httpx


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, client: httpx.Client | None = None):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=30)

    def send(self, text: str) -> None:
        response = self._client.post(
            self._url,
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
        )
        response.raise_for_status()
