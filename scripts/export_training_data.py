"""Export review feedback as JSONL for calibration."""

from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models.review_feedback import ReviewFeedback
from app.db.session import get_session
from scripts._util import configure_stdout


def export_training_data(path: str = "training_data.jsonl") -> int:
    configure_stdout()
    session = get_session()
    count = 0
    try:
        rows = session.scalars(select(ReviewFeedback).order_by(ReviewFeedback.id.asc())).all()
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                meta = row.metadata_ or {}
                record = {
                    "cluster_id": row.cluster_id,
                    "action": row.action,
                    "label": 0 if row.action.startswith("reject") else 1,
                    "reject_reason": meta.get("reject_reason"),
                    "message_ids": row.message_ids,
                    "metadata": meta,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return count
    finally:
        session.close()


if __name__ == "__main__":
    print(f"exported {export_training_data()} rows")
