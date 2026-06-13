"""Row-level locking helpers."""

import threading
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.db.models.cluster import Cluster
from app.db.models.hold_queue import HoldQueue
from app.db.models.publication import Publication
from app.db.models.publication_outbox import PublicationOutbox

_thread_local = threading.local()


def assert_no_slow_ops() -> None:
    assert not getattr(_thread_local, "in_slow_op", False), (
        "FORBIDDEN: embedding/similarity inside lock transaction"
    )


def mark_slow_op(active: bool = True) -> None:
    _thread_local.in_slow_op = active


@contextmanager
def cluster_lock(session: Session, cluster_id: int):
    assert_no_slow_ops()
    cluster = session.query(Cluster).filter_by(id=cluster_id).with_for_update().one()
    yield cluster


@contextmanager
def outbox_lock(session: Session, outbox_id: int):
    assert_no_slow_ops()
    outbox = session.query(PublicationOutbox).filter_by(id=outbox_id).with_for_update().one()
    yield outbox


@contextmanager
def hold_lock(session: Session, hold_id: int):
    assert_no_slow_ops()
    hold = session.query(HoldQueue).filter_by(id=hold_id).with_for_update().one()
    yield hold


@contextmanager
def publication_lock(session: Session, publication_id: int):
    assert_no_slow_ops()
    pub = session.query(Publication).filter_by(id=publication_id).with_for_update().one()
    yield pub
