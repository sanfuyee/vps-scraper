"""Telegram Bot 通知模块

通过 Telegram Bot API 发送 VPS 低价通知
完全免费，无需额外依赖，仅使用 requests
"""

import logging
import os

import requests

from models import VpsDeal

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org/bot{token}"
MAX_MESSAGE_LENGTH = 4000


def send_deals(deals: list[VpsDeal], token: str = "", chat_id: str = "") -> bool:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
        return False

    if not deals:
        logger.info("没有新的 deal 需要推送")
        return True

    messages = _format_messages(deals)

    success = True
    for msg in messages:
        if not _send_message(token, chat_id, msg):
            success = False

    return success


def send_test(token: str = "", chat_id: str = "") -> bool:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    return _send_message(token, chat_id, "VPS 低价监控已启动，通知测试成功 ✓")


def _format_messages(deals: list[VpsDeal]) -> list[str]:
    header = f"🔔 *发现 {len(deals)} 条低价 VPS*\n\n"
    messages = []
    current = header

    for i, deal in enumerate(deals):
        entry = deal.format_telegram()
        separator = "\n─────────────\n" if i < len(deals) - 1 else ""
        block = entry + separator

        if len(current) + len(block) > MAX_MESSAGE_LENGTH:
            messages.append(current)
            current = f"🔔 *低价 VPS（续）*\n\n{block}"
        else:
            current += block

    if current.strip():
        messages.append(current)

    return messages


def _send_message(token: str, chat_id: str, text: str) -> bool:
    url = f"{API_BASE.format(token=token)}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            logger.info("Telegram 消息发送成功")
            return True
        logger.error("Telegram 发送失败: %s %s", resp.status_code, resp.text)
        return False
    except Exception:
        logger.exception("Telegram 发送异常")
        return False
