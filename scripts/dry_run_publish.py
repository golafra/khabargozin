"""Preview publication HTML without sending."""

import argparse
import sys

from sqlalchemy import select

from app.ai.schemas import AIClusterOutput
from app.db.models.ai_result import AIResult
from app.publisher.formatter import format_publication_html
from app.db.session import get_session
from scripts._util import configure_stdout


def main() -> int:
    configure_stdout()
    parser = argparse.ArgumentParser()
    parser.add_argument("--cluster-id", type=int, required=True)
    args = parser.parse_args()

    session = get_session()
    try:
        ai_row = session.scalars(
            select(AIResult)
            .where(AIResult.cluster_id == args.cluster_id)
            .order_by(AIResult.created_at.desc())
            .limit(1)
        ).first()
        if not ai_row:
            print("No AI result for cluster")
            return 1

        result = AIClusterOutput(
            status=ai_row.status,
            editorial_priority=ai_row.editorial_priority,
            confidence=ai_row.confidence,
            headline=ai_row.headline,
            summary=ai_row.summary,
            why_it_matters=ai_row.why_it_matters,
            conflicts=ai_row.conflicts or [],
            sources_used=ai_row.sources_used or [],
            rejection_reason=ai_row.rejection_reason,
            sensitivity=ai_row.sensitivity,
            needs_human_review=ai_row.needs_human_review,
        )
        html = format_publication_html(session, args.cluster_id, result)
        print(html)
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
