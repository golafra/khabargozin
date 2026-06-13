# خبرگزین (Khabargozin)

سامانه جمع‌آوری، خوشه‌بندی، پردازش AI و انتشار خبر از کانال‌های تلگرام.

## معماری

```
Fetch (ICA) → Cluster (MiniLM+pgvector) → AI (gpt-4o-mini) → Publish (Fast/Batch)
```

## پیش‌نیاز

- Docker & Docker Compose
- Python 3.11+ (برای توسعه محلی)

## راه‌اندازی سریع

```bash
cp .env.example .env
# ویرایش OPENAI_API_KEY و TELEGRAM_BOT_TOKEN

docker compose up -d postgres redis
pip install -e ".[dev]"

# migration + seed
alembic upgrade head
python -m scripts.seed_sources

# Spike ICA (Sprint 0)
python -m scripts.ica_spike

# worker + beat
docker compose up -d worker beat
```

## تلگرام — راه‌اندازی ربات

```bash
python -m scripts.setup_telegram
python -m scripts.setup_telegram --send-test
```

1. ربات `@iNewsRobot` را در کانال خروجی **ادمین** کنید (با دسترسی Post Messages)
2. کانال تست `@khabargozin_test` — ربات باید ادمین با دسترسی Post Messages باشد
3. پس از ادمین شدن: `PUBLISH_MODE=test` یا `production` و `python -m scripts.retry_publish`

## PUBLISH_MODE

| mode | رفتار |
|------|-------|
| `dry_run` | رندر + outbox بدون ارسال |
| `test` | ارسال به کانال تست |
| `production` | ارسال به کانال اصلی |

## CLI Debug

```bash
python -m scripts.inspect_source KhabarFouri
python -m scripts.inspect_cluster --id 123
python -m scripts.ai_dry_run --limit 30
python -m scripts.dry_run_publish --cluster-id 123
python -m scripts.reconcile_outbox
python -m scripts.kpi_report --date today
```

## Celery Beat

پس از تغییر `BEAT_*` در `.env`:

```bash
docker compose restart beat
```

## pgvector

ایندکس HNSW با `vector_cosine_ops` — همه similarity با `<=>` (cosine distance).

## تست

```bash
pytest tests/ -v
```

## فازبندی

- **MVP (A–D):** Fetch → Cluster → AI → Publish
- **فاز ۲ (E–H):** Redis buffer, Archive, Hold, Retraction, Supplemental, KPI
