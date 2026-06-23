# راهنمای پنل ادمین و تست فرآیند خبرگزین

این سند برای **مدیر سیستم** است: رصد pipeline از جمع‌آوری تا انتشار، و تست دستی وقتی می‌خواهید ببینید «خبر خام چه بود» و «خروجی چه شد».

---

## پیش‌نیاز: سرویس‌ها

```powershell
cd d:\Source\khabargozin

# همه سرویس‌های لازم (redis برای worker ضروری است)
docker compose up -d postgres redis worker beat admin
```

در `.env`:

```env
ADMIN_PASSWORD=رمز-قوی-شما
PUBLISH_MODE=test          # برای تست: dry_run | test | production
OPENAI_API_KEY=...
TELEGRAM_BOT_TOKEN=...
TEST_OUTPUT_CHANNEL_ID=@khabargozin_test
```

**بعد از هر تغییر `.env`:**

```powershell
docker compose up -d --force-recreate worker beat admin
```

---

## ورود به پنل

| مورد | مقدار |
|------|--------|
| آدرس | http://localhost:8080 |
| کاربر | `admin` |
| رمز | مقدار `ADMIN_PASSWORD` در `.env` |

پنل **فقط read-only** است؛ برای اجرای دستی مراحل از CLI استفاده کنید (پایین سند).

---

## نقشه صفحات

```
داشبورد ──► نمای کلی سلامت سیستم
مسیر پردازش ──► خبرهای اخیر از fetch تا publish (صفحه اصلی رصد)
منابع ──► وضعیت fetch هر کانال
خوشه‌ها ──► لیست + جزئیات هر خوشه
```

### ۱. داشبورد زنده (`/`) — **صفحه اصلی**

- **بدون refresh** — هر ۸ ثانیه از `/api/live` به‌روز می‌شود (نقطه سبز = زنده)
- **جریان زنده** — هر پیام با کاندیدهای مقایسه (sim) و پیام‌های هم‌خوشه
- **منابع** — آخرین fetch هر کانال در نوار بالا
- اگر فعالیت جدید نباشد → آخرین پیام‌های آرشیو نمایش داده می‌شود

### ۲. مسیر پردازش (`/pipeline`)

هر کارت = یک **خوشه** که در بازه انتخاب‌شده (۱/۳/۶/۱۲/۲۴ ساعت) حداقل یک پیام **خوانده شده** (`created_at`).

مراحل روی کارت:

| مرحله | معنی |
|--------|------|
| ① جمع‌آوری | متن خام از منابع تلگرام (ICA) |
| ② خوشه‌بندی | ادغام پیام‌های مشابه |
| ③ آستانه | امتیاز ≥ ۶.۰؟ (در فاز steady) |
| ④ تحلیل AI | headline و summary |
| ⑤ Outbox | صف انتشار (fast/batch) |
| ⑥ انتشار | post_id در کانال تلگرام |

پایین کارت: **مقایسه ورودی ↔ خروجی** — پیام منبع در کنار headline نهایی.

**تفسیر رنگ مراحل:** سبز = انجام شد · زرد = در صف · قرمز = خطا/رد · کم‌رنگ = رد شده (مثلاً زیر آستانه)

**انتهای صفحه:** پیام‌های «در انتظار خوشه‌بندی» — fetch شده ولی هنوز cluster نشده.

### ۳. منابع (`/sources`)

برای هر کانال:

- آخرین fetch موفق
- تعداد خطا و متن `last_error`
- فعال/غیرفعال، اعتبار (credibility)

اگر **هرگز** fetch نشده یا **stale** است → مشکل از ICA یا worker/redis است، نه از AI.

### ۴. خوشه‌ها (`/clusters`)

فیلتر بر اساس `status`:

| status | معنی معمول |
|--------|------------|
| `below_threshold` | امتیاز کم؛ به AI نمی‌رود (عادی برای خبر تک‌منبعی) |
| `ai_ready` | آماده پردازش AI |
| `ai_done` | AI تمام؛ منتظر outbox/publish |
| `ai_failed` | خطای OpenAI یا parse |
| `published` | منتشر شده |
| `hold` | نگه‌داشته شده برای تأیید منبع دوم |

کلیک روی شماره خوشه → جزئیات کامل (همه پیام‌ها، AI، outbox، انتشار).

---

## ادغام بین کانال‌ها — آیا همه اخبار ساعات قبل چک می‌شوند؟

**بله، ولی هوشمند و محدود — نه نمایش همه در UI.**

### مکانیزم (خلاصه فنی)

```
پیام جدید کانال A
    → embedding
    → pgvector: ۱۰ خوشه باز نزدیک (همه کانال‌ها، ۶ ساعت اخیر)
    → sim ≥ 0.72؟ → ادغام با خوشه B که پیام کانال C دارد
    → وگرنه خوشه تازه (اغلب below_threshold)
```

| پارامتر | پیش‌فرض | معنی |
|---------|---------|------|
| `CLUSTER_ACTIVE_WINDOW_MINUTES` | 360 | پنجره merge — خوشه‌های قدیمی‌تر از ۶h کاندید نیستند |
| `MERGE_OPEN_SIM` | 0.72 | حداقل شباهت برای ادغام |
| `CLUSTER_LOOKBACK_HOURS` | 24 | پیام خیلی قدیمی fetch نمی‌شود |

### چرا داشبورد «همه چیز» نشان نمی‌دهد؟

- روزانه **صدها پیام** × **۱۰ کانال** = هزاران ردیف بی‌فایده
- **۹۰٪+** تک‌منبعی و زیر آستانه — noise است
- رصد درست = **سیگنال**: چندمنبعی، ai_ready، منتشرشده، خطا

### چه کار کنید

1. **داشبورد** → بخش «فعالیت ۳ ساعت» و «رویدادهای چندمنبعی»
2. **مسیر پردازش** → فقط خوشه‌هایی که در بازه فعالیت داشتند
3. **جزئیات خوشه** → همه پیام‌های منابع داخل یک رویداد
4. اگر `چندمنبعی = 0` ولی `خوانده‌شده` زیاد → سیستم سالم است؛ خبر مشترک نبوده

---

## فرآیند کامل (مرجع)

```
Fetch (ICA) → Cluster (MiniLM) → آستانه امتیاز → AI → Outbox → تلگرام
                     ↑
              Beat هر ۵ دقیقه (fetch/cluster)
              Beat هر ۲ دقیقه (AI)
              Beat هر ۵ دقیقه (publish batch)
```

**نکته:** خبر **تک‌منبعی** اغلب در مرحله ③ متوقف می‌شود. برای دیدن مسیر کامل تا انتشار، خوشه **چندمنبعی** با امتیاز بالا لازم است.

---

## تست دستی: آوردن خبر جدید

وقتی در «مسیر پردازش» چیزی نیست یا می‌خواهید فوراً تست کنید:

### گام ۱ — اطمینان از redis و worker

```powershell
docker compose ps
# redis و worker باید Up باشند
```

### گام ۲ — اجرای pipeline (داخل worker)

**Fetch کامل** حدود ۵–۱۰ دقیقه طول می‌کشد (محدودیت ICA):

```powershell
docker compose exec worker python -c "
from app.tasks.fetch import fetch_all_sources
from app.tasks.cluster import cluster_pending_messages
from app.tasks.ai import process_cloud_ai
from app.tasks.publish import publish_batch_queue
print('FETCH:', fetch_all_sources())
print('CLUSTER:', cluster_pending_messages())
for i in range(5):
    r = process_cloud_ai()
    print('AI:', r)
    if r.get('processed', 0) == 0 and not r.get('skipped'): break
print('PUBLISH:', publish_batch_queue())
"
```

### گام ۳ — smoke test آماده

```powershell
docker compose exec worker python -m scripts.e2e_smoke
# سریع‌تر (بدون fetch):
docker compose exec worker python -m scripts.e2e_smoke --skip-fetch
```

### گام ۴ — بررسی در پنل

1. برو به http://localhost:8080/pipeline?hours=3
2. Refresh کن
3. کارت خوشه را باز کن و **ورودی ↔ خروجی** را مقایسه کن
4. اگر منتشر شد، کانال `@khabargozin_test` را هم چک کن

---

## حالت‌های انتشار (`PUBLISH_MODE`)

| mode | پنل | تلگرام | کاربرد |
|------|-----|--------|--------|
| `dry_run` | outbox با status خاص | ارسال نمی‌شود | تست رندر و outbox |
| `test` | انتشار به کانال تست | `@khabargozin_test` | **تست روزمره (پیشنهادی)** |
| `production` | کانال اصلی | `@khabar_gozin` | فقط وقتی کیفیت تأیید شد |

اعتبارسنجی ربات:

```powershell
docker compose exec worker python -m scripts.setup_telegram --send-test
```

---

## چک‌لیست روزانه (۵ دقیقه)

1. **داشبورد** — `ai_failed`، stale sources، circuit breaker
2. **مسیر پردازش ۳h** — آیا fetch و cluster جلو می‌رود؟
3. **منابع** — همه منابع فعال fetch شده‌اند؟
4. CLI (اختیاری):

```powershell
docker compose exec worker python -m scripts.kpi_report --date today
```

---

## عیب‌یابی سریع

| علامت در پنل | احتمال | اقدام |
|--------------|--------|--------|
| «پیام خوشه‌شده‌ای خوانده نشده» | fetch نشده یا بازه زمانی کوتاه | fetch دستی؛ بازه ۶/۱۲h؛ redis را چک کن |
| خوشه‌نشده زیاد در داشبورد | cluster عقب است | `cluster_pending_messages` دستی |
| همه `below_threshold` | خبر تک‌منبعی یا امتیاز پایین | طبیعی؛ خوشه چندمنبعی صبر کن یا `inspect_cluster` |
| `ai_failed` زیاد | OpenAI / parse | `retry_ai_failed`؛ `inspect_cluster --id X` |
| outbox `pending` | publish batch نرسیده | `publish_batch_queue` دستی |
| outbox `unknown` | ارسال نامشخص | `reconcile_outbox --dry-run` |
| Circuit breaker | بودجه AI | `OPENAI_MONTHLY_BUDGET_USD` یا صبر تا ماه بعد |
| منابع stale | worker/beat/redis down | `docker compose up -d redis worker beat` |
| headline اشتباه | over-merge یا AI | `ai_dry_run`؛ جزئیات خوشه را ببین |

### CLI مکمل پنل

```powershell
# منبع
docker compose exec worker python -m scripts.inspect_source KhabarFouri

# خوشه
docker compose exec worker python -m scripts.inspect_cluster --id 183

# کیفیت AI بدون publish
docker compose exec worker python -m scripts.ai_dry_run --limit 10

# پیش‌نمایش HTML
docker compose exec worker python -m scripts.dry_run_publish --cluster-id 183

# پردازش مجدد یک خوشه
docker compose exec worker python -m scripts.reprocess_cluster --id 183

# retry همه ai_failed
docker compose exec worker python -m scripts.retry_ai_failed

# انتشار مجدد
docker compose exec worker python -m scripts.retry_publish
```

---

## سناریوهای تست پیشنهادی

### A — فقط رصد (بدون دستکاری)

Beat + Worker بالا باشند. هر چند ساعت «مسیر پردازش» را ببین.

### B — تست انتشار امن

1. `PUBLISH_MODE=test`
2. `e2e_smoke` یا fetch+cluster+AI دستی
3. پنل + کانال تست

### C — بررسی کیفیت AI

1. در خوشه‌ها فیلتر `ai_done` یا `published`
2. خوشه‌های با `independent_source_count ≥ 2`
3. مقایسه پیام منبع با headline در جزئیات خوشه
4. `ai_dry_run --limit 20` برای نمونه بیشتر

### D — بعد از تغییر کد

```powershell
pytest tests/ -v
docker compose exec worker python -m scripts.e2e_smoke --skip-fetch
```

---

## Flower (صف Celery — اختیاری)

برای دیدن worker و taskها (نه محتوای خبر):

```powershell
docker compose --profile monitoring up -d flower
# http://localhost:5555
```

---

## محدودیت‌های فعلی پنل

- فقط **مشاهده**؛ دکمه reprocess/retry ندارد (از CLI)
- «مسیر پردازش» بر اساس **`created_at` پیام** (زمان fetch به DB)، نه `published_at` تلگرام
- حداکثر ۵۰ خوشه در هر بازه pipeline
- زمان‌ها UTC در برخی برچسب‌ها

---

## جمع‌بندی

| هدف | کجا |
|-----|-----|
| سلامت کلی | داشبورد |
| دیدن مسیر خبر خام → خروجی | **مسیر پردازش** |
| مشکل fetch | منابع |
| جزئیات یک خبر | خوشه → کلیک روی id |
| اجرای دستی | CLI / `e2e_smoke` |
| انتشار تست | `PUBLISH_MODE=test` + کانال تست |
