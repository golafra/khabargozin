"""Sprint 0 — ICA API spike script."""

import json
import re
import sys
import time
from datetime import datetime, timezone

import httpx

CHANNEL = "Tasnimnews"
BASE = "https://tg.i-c-a.su/json"


def fetch_page(page: int, limit: int = 5, retries: int = 3) -> dict:
    url = f"{BASE}/{CHANNEL}?limit={limit}&page={page}"
    for attempt in range(retries):
        resp = httpx.get(url, timeout=30)
        if resp.status_code == 429:
            wait = 15
            match = re.search(r"FLOOD_WAIT_(\d+)", resp.text)
            if match:
                wait = int(match.group(1)) + 1
            print(f"Rate limited — waiting {wait}s (attempt {attempt + 1})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    resp.raise_for_status()
    return {}


def main() -> int:
    print("=== ICA API Spike ===\n")

    p1 = fetch_page(1, limit=5)
    p2 = fetch_page(2, limit=5)
    msgs1 = p1.get("messages") or []
    msgs2 = p2.get("messages") or []

    print(f"Page 1 count: {len(msgs1)}")
    print(f"Page 2 count: {len(msgs2)}")

    if msgs1:
        m = msgs1[0]
        print(f"\nNewest id: {m['id']}")
        print(f"date (unix): {m['date']} -> {datetime.fromtimestamp(m['date'], tz=timezone.utc)}")
        print(f"edit_date: {m.get('edit_date', 'N/A')}")
        print(f"has media: {'media' in m}")
        if m.get("media"):
            print(f"media type: {m['media'].get('_')}")
        print(f"reply_to: {m.get('reply_to', 'N/A')}")

    if msgs1 and msgs2:
        print(f"\nPagination: page1[0].id={msgs1[0]['id']} > page2[0].id={msgs2[0]['id']}? "
              f"{msgs1[0]['id'] > msgs2[0]['id']}")
        print("Order: newest->oldest CONFIRMED" if msgs1[0]["id"] > msgs2[0]["id"] else "Order: CHECK")

    print("\n--- Rate limit probe (3 rapid requests) ---")
    start = time.monotonic()
    for i in range(3):
        fetch_page(1, limit=1)
    elapsed = time.monotonic() - start
    print(f"3 requests in {elapsed:.1f}s - recommend >=4s between pages")

    print("\n--- Sample message keys ---")
    if msgs1:
        print(json.dumps(list(msgs1[0].keys()), ensure_ascii=False))

    print("\nSpike complete. See docs/ica_api_notes.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
