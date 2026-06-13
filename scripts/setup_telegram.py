"""Validate Telegram bot and channel access."""

import argparse
import asyncio
import sys

from app.config import get_settings
from app.publisher.bot import cache_chat_id, get_cached_chat_id
from scripts._util import configure_stdout


async def check_channel(bot, label: str, channel: str) -> bool:
    print(f"\n--- {label}: {channel} ---")
    if not channel:
        print("  NOT CONFIGURED")
        return False
    try:
        chat = await bot.get_chat(channel)
        print(f"  OK: id={chat.id} title={chat.title} type={chat.type}")
        cache_chat_id(label.lower(), str(chat.id))
        print(f"  Cached as telegram_chat_id:{label.lower()}")
        return True
    except Exception as exc:
        print(f"  FAIL: {exc}")
        print("  -> Bot must be added as ADMIN to the channel.")
        print("  -> For private channels, forward a post to @userinfobot to get numeric ID.")
        return False


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Validate Telegram bot setup")
    parser.add_argument("--send-test", action="store_true", help="Send a test message")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not set in .env")
        return 1

    from telegram import Bot

    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    async def run():
        me = await bot.get_me()
        print(f"Bot: @{me.username} (id={me.id})")

        test_ok = await check_channel(bot, "test", settings.TEST_OUTPUT_CHANNEL_ID)
        prod_ok = await check_channel(bot, "production", settings.PRODUCTION_OUTPUT_CHANNEL_ID)

        if args.send_test:
            for label, ok in [("test", test_ok), ("production", prod_ok)]:
                if not ok:
                    continue
                chat_id = get_cached_chat_id(label) or (
                    settings.TEST_OUTPUT_CHANNEL_ID if label == "test"
                    else settings.PRODUCTION_OUTPUT_CHANNEL_ID
                )
                try:
                    msg = await bot.send_message(
                        chat_id=chat_id,
                        text="<b>خبرگزین</b> — تست اتصال موفق بود.",
                        parse_mode="HTML",
                    )
                    print(f"\n[{label}] Test message sent: post_id={msg.message_id}")
                except Exception as exc:
                    print(f"\n[{label}] Send FAILED: {exc}")
                    print("  -> Add bot as channel ADMIN with 'Post Messages' permission.")

        return 0 if (test_ok or prod_ok) else 1

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
