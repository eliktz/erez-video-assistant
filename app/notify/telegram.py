"""Telegram delivery. Long polling: no webhook, no domain, no TLS cert."""

import httpx

# Telegram hard-caps a message at 4096 characters. A digest with ten deeply-analyzed
# videos is longer than that, so long texts are split at line breaks and sent in parts.
TEXT_LIMIT = 4096


def chunks(text: str, limit: int = TEXT_LIMIT):
    """Split at line breaks so no part exceeds Telegram's cap."""
    while len(text) > limit:
        cut = text.rfind("\n", 1, limit)
        if cut == -1:
            cut = limit
        yield text[:cut]
        text = text[cut:].lstrip("\n")
    if text:
        yield text


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, client: httpx.Client | None = None):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=30)

    def send(self, text: str) -> None:
        # Plain text on purpose: Markdown parsing made Telegram reject any model-written
        # digest with an unbalanced '*' or '_' (400), and we send model text every day.
        for part in chunks(text):
            response = self._client.post(self._url, json={"chat_id": self._chat_id, "text": part})
            if response.status_code != 200:
                # Never re-raise httpx's own error: its message embeds the request URL,
                # and our URL embeds the bot token — which must never reach the logs.
                raise RuntimeError(f"Telegram sendMessage failed: {response.text[:200]}")
