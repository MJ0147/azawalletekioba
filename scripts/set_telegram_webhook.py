"""
Point the Telegram bot at the AI assistant's webhook, or inspect or remove that link.

Telegram delivers each message to the registered URL and includes TELEGRAM_WEBHOOK_SECRET in the
X-Telegram-Bot-Api-Secret-Token header; the assistant refuses deliveries without it. Only message
updates are requested, since those are all the bot answers.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_WEBHOOK_SECRET from the environment, falling back to
ai_assistant/.env. The token is never printed.

Usage:
    python scripts/set_telegram_webhook.py --info
    python scripts/set_telegram_webhook.py --url https://ai.example.com
    python scripts/set_telegram_webhook.py --delete
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / "ai_assistant" / ".env"
WEBHOOK_PATH = "/telegram/webhook"


def _setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value or not ENV_FILE.is_file():
        return value
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _call(token: str, method: str, params: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(params or {}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            return json.load(exc)
        except ValueError:
            return {"ok": False, "description": f"HTTP {exc.code}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "description": f"network error: {exc.reason}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Public HTTPS base URL of the AI assistant (the webhook path is added).")
    group.add_argument("--info", action="store_true", help="Show where Telegram currently delivers messages.")
    group.add_argument("--delete", action="store_true", help="Stop Telegram delivering to any webhook.")
    args = parser.parse_args()

    token = _setting("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set.", file=sys.stderr)
        return 1

    if args.info:
        result = _call(token, "getWebhookInfo")
        if not result.get("ok"):
            print(f"getWebhookInfo failed: {result.get('description')}", file=sys.stderr)
            return 1
        info = result["result"]
        print(f"url: {info.get('url') or '(none)'}")
        print(f"pending updates: {info.get('pending_update_count')}")
        print(f"last error: {info.get('last_error_message') or 'none'}")
        return 0

    if args.delete:
        result = _call(token, "deleteWebhook")
        print("Webhook removed." if result.get("ok") else f"deleteWebhook failed: {result.get('description')}")
        return 0 if result.get("ok") else 1

    url = args.url.rstrip("/")
    if not url.startswith("https://"):
        print("Telegram only delivers to https:// URLs.", file=sys.stderr)
        return 1
    if not url.endswith(WEBHOOK_PATH):
        url += WEBHOOK_PATH

    secret = _setting("TELEGRAM_WEBHOOK_SECRET")
    if not secret:
        print("TELEGRAM_WEBHOOK_SECRET is not set; the assistant would refuse every delivery.", file=sys.stderr)
        return 1

    result = _call(token, "setWebhook", {"url": url, "secret_token": secret, "allowed_updates": ["message"]})
    if not result.get("ok"):
        print(f"setWebhook failed: {result.get('description')}", file=sys.stderr)
        return 1
    print(f"Telegram will deliver messages to {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
