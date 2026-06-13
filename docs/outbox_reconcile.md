# Outbox Reconcile Algorithm

When `publication_outbox.status = unknown`, the system cannot safely retry blindly.

## When `unknown` Happens

Outbox item stuck in `sending` beyond `OUTBOX_LOCK_TIMEOUT_MINUTES` with
`send_started_at` set but no matching `publications` row.

## Reconcile Steps (`scripts/reconcile_outbox.py`)

1. Load all `status=unknown` outbox rows.
2. For each row, fetch recent bot updates / channel messages (post-bot only).
3. Match by:
   - `rendered_text_hash` exact match on message text hash, or
   - headline prefix (first 80 chars of payload_preview).
4. If match found:
   - Set `status=sent`
   - Create `publications` row with `telegram_post_id`
5. If no match:
   - Log for manual CLI review — **never** auto-retry send.

## Manual Review

```bash
python -m scripts.reconcile_outbox --dry-run
python -m scripts.reconcile_outbox --apply
```

## Rules

- Never blind retry `unknown` — risk of duplicate posts.
- Bot API does not provide full channel history.
- Prefer `rendered_text_hash` over fuzzy match.
