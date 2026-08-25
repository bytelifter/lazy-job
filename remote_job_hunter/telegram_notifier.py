"""
telegram_notifier.py — Instant Telegram Bot notifications for matches, applications, and reports.

Sends:
1. Real-time application alert cards with direct links & AI letters.
2. Summary reports of new high-match & automatable jobs.
3. Direct CSV attachment to your Telegram chat.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import requests


class TelegramNotifier:
    """Dispatches formatted notifications and CSV files directly to Telegram chat."""

    def __init__(self, config: dict[str, Any]) -> None:
        """
        Initializes Telegram notifier with token and chat ID.

        Args:
            config: Configuration dictionary from config.json.
        """
        self._config = config
        self._tg_settings: dict[str, Any] = config.get("telegram_settings", {})
        self._enabled: bool = self._tg_settings.get("enabled", False)

        # Bot token & Chat ID from config or environment variables
        self._bot_token: str = (
            self._tg_settings.get("bot_token")
            or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        )
        self._chat_id: str = str(
            self._tg_settings.get("chat_id")
            or os.environ.get("TELEGRAM_CHAT_ID", "")
        )

        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"

    @property
    def is_configured(self) -> bool:
        """Checks if Telegram notifications are enabled and credentials provided."""
        return bool(self._enabled and self._bot_token and self._chat_id)

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """
        Sends an HTML-formatted message to Telegram.

        Args:
            text: Message body (HTML supported).
            parse_mode: Parsing mode ('HTML' or 'Markdown').

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self.is_configured:
            return False

        try:
            url = f"{self._base_url}/sendMessage"
            payload = {
                "chat_id": self._chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": False,
            }
            resp = requests.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """
        Sends a file (e.g. results CSV) directly to the Telegram chat.

        Args:
            file_path: Absolute or relative file path.
            caption: Optional message caption.

        Returns:
            True if file sent successfully, False otherwise.
        """
        if not self.is_configured:
            return False

        path = Path(file_path)
        if not path.exists():
            return False

        try:
            url = f"{self._base_url}/sendDocument"
            with path.open("rb") as doc:
                files = {"document": doc}
                data = {
                    "chat_id": self._chat_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                }
                resp = requests.post(url, data=data, files=files, timeout=20)
                return resp.status_code == 200
        except Exception:
            return False

    def send_application_alert(
        self,
        job_title: str,
        company: str,
        channel: str,
        status: str,
        details: str,
        direct_link: str,
        salary: str = "",
        cover_letter: str = "",
    ) -> bool:
        """
        Sends an instant alert when a job is applied to or requires manual click.

        Args:
            job_title: Position title.
            company: Company name.
            channel: Email / ATS Form.
            status: AUTO_FILLED / SENT / MANUAL_REQUIRED.
            details: Human readable details.
            direct_link: Link to offer.
            salary: Salary info if available.
            cover_letter: Generated cover letter.
        """
        if not self.is_configured:
            return False

        status_emoji = "✅" if status in ("SENT", "AUTO_FILLED") else "⚠️"
        salary_line = f"💵 <b>Budget:</b> {salary}\n" if salary else ""

        msg = (
            f"🎯 <b>LAZYJOBHUNTER APPLICATION UPDATE</b>\n\n"
            f"💼 <b>Role:</b> {job_title}\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"{salary_line}"
            f"📡 <b>Channel:</b> {channel}\n"
            f"{status_emoji} <b>Status:</b> <code>{status}</code>\n"
            f"ℹ️ <b>Details:</b> {details}\n\n"
            f"🔗 <a href='{direct_link}'><b>Open Direct Job Link</b></a>\n"
        )

        if cover_letter:
            clean_letter = cover_letter.replace("<", "&lt;").replace(">", "&gt;")
            msg += (
                f"\n📄 <b>FULL READY-TO-PASTE COVER LETTER:</b>\n"
                f"<blockquote>{clean_letter}</blockquote>\n"
            )

        return self.send_message(msg)

    def send_match_summary(
        self,
        total_matched: int,
        top_offers: list[Any],
        csv_path: str = "",
    ) -> bool:
        """
        Sends an executive summary of new job matches and attaches the CSV.
        """
        if not self.is_configured:
            return False

        lines = [
            f"🚀 <b>LAZYJOBHUNTER — NEW BATCH REPORT</b>",
            f"📊 <b>Found {total_matched} matching contractor positions!</b>\n",
        ]

        for i, offer in enumerate(top_offers[:5], 1):
            sal = f" | 💵 {offer.salary}" if offer.salary else ""
            auto_badge = " ⚡🤖" if getattr(offer, "is_highly_automatable", False) else ""
            lines.append(
                f"<b>#{i:02d} [{offer.match_score}/100]{auto_badge}</b> "
                f"<a href='{offer.url}'>{offer.title}</a> @ <b>{offer.company}</b>{sal}"
            )

        msg = "\n".join(lines)
        sent = self.send_message(msg)

        # Attach CSV
        if csv_path:
            self.send_document(csv_path, caption="📁 <b>Full Matches CSV Report</b>")

        return sent
