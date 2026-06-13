# Test Matrix

## MVP (Sprint A–D)

| سناریو | فایل | انتظار |
|--------|------|--------|
| FetcherBackend swap | `scenarios/test_fetcher_backend.py` | mock backend inject |
| merge دو منبع | `scenarios/test_merge_open.py` | یک خوشه |
| lineage بازنشر | `scenarios/test_lineage.py` | sim>0.95 → ۱ independent |
| Fast confidence gating | `scenarios/test_confidence_gating.py` | downgrade Batch |
| Outbox / dry_run | `scenarios/test_outbox_publish.py` | dry_run no send |
| Cold start / percentile | `scenarios/test_cold_start.py`, `test_percentile_fallback.py` | fallback 6.0 |
| pgvector | `scenarios/test_vector_search.py` | cosine در DB |
| Batch adaptive | `scenarios/test_batch_adaptive.py` | interval 5min when busy |
| Task singleton | `scenarios/test_task_lock.py` | overlap → skip |
| Telegram FloodWait | `scenarios/test_telegram_retry.py` | retry on 429 |
| Race merge | `scenarios/test_merge_race.py` | FOR UPDATE |

## فاز ۲ (Sprint F–G)

| سناریو | فایل | انتظار |
|--------|------|--------|
| Hold confirm | `scenarios/test_hold_confirm.py` | independent≥2 |
| Hold expire | `scenarios/test_hold_expire.py` | reject |
| Hold re-run AI | `scenarios/test_hold_rerun.py` | re-run on source change |
| merge published | `scenarios/test_merge_published_strict.py` | strict sim+NER |
| Retraction FSM | `scenarios/test_retraction_fsm.py` | classify + action |
| Retraction vs update | `scenarios/test_retraction_vs_update.py` | update→supplemental |
