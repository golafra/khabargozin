"""Seed news sources with credibility policy."""

import sys

from sqlalchemy.dialects.postgresql import insert

from app.db.models.source import Source
from app.db.session import get_session
from scripts._util import configure_stdout

SOURCES = [
    # news_agency — primary producers
    {"username": "Tasnimnews", "display_name": "تسنیم", "source_type": "news_agency",
     "credibility_weight": 1.4, "is_primary_source": True},
    {"username": "Farsna", "display_name": "فارس", "source_type": "news_agency",
     "credibility_weight": 1.3, "is_primary_source": True},
    {"username": "Isna94", "display_name": "ایسنا", "source_type": "news_agency",
     "credibility_weight": 1.3, "is_primary_source": True},
    {"username": "Mehrnews", "display_name": "مهر", "source_type": "news_agency",
     "credibility_weight": 1.2, "is_primary_source": True},
    # general — newspapers / analysis
    {"username": "SharghDaily", "display_name": "شرق", "source_type": "general",
     "credibility_weight": 1.2, "is_primary_source": False},
    {"username": "Jamarannews", "display_name": "جماران", "source_type": "general",
     "credibility_weight": 1.0, "is_primary_source": False},
    # general — breaking / republish
    {"username": "KhabarFouri", "display_name": "خبر فوری", "source_type": "general",
     "credibility_weight": 0.8, "is_primary_source": False},
    {"username": "Akharinkhabar", "display_name": "آخرین خبر", "source_type": "general",
     "credibility_weight": 0.7, "is_primary_source": False},
    # tech — topic-dependent (1.3 tech / 0.9 politics in scorer via topic; MVP topic=0)
    {"username": "Digiato", "display_name": "دیجیاتو", "source_type": "tech",
     "credibility_weight": 1.3, "is_primary_source": False},
    # religious
    {"username": "aghigh_ir", "display_name": "عقیق", "source_type": "religious",
     "credibility_weight": 1.0, "is_primary_source": False},
]


def seed() -> int:
    configure_stdout()
    session = get_session()
    try:
        for src in SOURCES:
            stmt = (
                insert(Source)
                .values(is_active=True, **src)
                .on_conflict_do_update(
                    index_elements=["username"],
                    set_={
                        "display_name": src["display_name"],
                        "credibility_weight": src["credibility_weight"],
                        "source_type": src["source_type"],
                        "is_primary_source": src["is_primary_source"],
                    },
                )
            )
            session.execute(stmt)
        session.commit()
        print(f"Seeded {len(SOURCES)} sources.")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(seed())
