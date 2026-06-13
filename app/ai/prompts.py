"""OpenAI prompts."""

CLUSTER_ANALYSIS_SYSTEM = """شما یک ویراستار خبری فارسی هستید. خروجی فقط JSON معتبر باشد.
تیتر خنثی و خبری بنویسید. ادعاها و منابع را حفظ کنید.
اگر روایت‌ها متفاوت است conflicts را پر کنید.
برای طنز یا نقل‌قول، needs_human_review=true بگذارید."""

CLUSTER_ANALYSIS_USER = """خبرهای زیر از چند منبع تلگرامی جمع‌آوری شده:

{messages_block}

تعداد منابع مستقل: {independent_source_count}
امتیاز خوشه: {cluster_score}

خروجی JSON با فیلدهای:
status (publish|reject|hold), editorial_priority (1-5), confidence (0-1),
headline, summary, why_it_matters, conflicts (array), sources_used (array),
rejection_reason, sensitivity (normal|political|security|casualty|market|medical),
needs_human_review (bool)"""

RETRACTION_CLASSIFY_USER = """متن منتشرشده:
{published_text}

پیام جدید:
{new_text}

خروجی JSON: type (update|correction|retraction|noise), confidence (0-1), corrected_text"""

DELTA_CHECK_USER = """متن منتشرشده:
{published_text}

پیام(های) جدید:
{new_text}

خروجی JSON: has_new_value (bool), supplement_text, reason"""

SIMPLE_JSON_RETRY = """پاسخ قبلی JSON معتبر نبود. فقط JSON خالص برگردان بدون markdown."""
