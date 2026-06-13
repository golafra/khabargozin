"""Reconcile unknown outbox items."""

import argparse

from app.config import get_settings
from app.db.session import get_session
from app.publisher.reconcile import reconcile_unknown_outbox
from scripts._util import configure_stdout


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply matches to DB")
    args = parser.parse_args()

    get_settings.cache_clear()
    session = get_session()
    try:
        results = reconcile_unknown_outbox(session, apply=args.apply)
        if not results:
            print("No unknown outbox items (or dry_run mode).")
            return 0

        for r in results:
            status = "MATCHED" if r["matched"] else "NO MATCH"
            print(f"outbox {r['outbox_id']} cluster {r['cluster_id']}: {status}")
            if r["telegram_post_id"]:
                print(f"  -> telegram_post_id={r['telegram_post_id']}")

        if args.apply:
            session.commit()
            print(f"\nApplied {sum(1 for r in results if r['matched'])} reconciliations.")
        else:
            print("\nDry run — use --apply to commit matches.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
