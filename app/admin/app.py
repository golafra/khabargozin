"""Minimal read-only admin panel."""

import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from app.admin.stats import (
    get_cluster_detail,
    get_dashboard,
    list_clusters,
    list_pipeline_traces,
    list_sources,
    pipeline_step_status,
)
from app.config import get_settings
from app.db.session import get_session

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_security = HTTPBasic(auto_error=False)

app = FastAPI(title="Khabargozin Admin", docs_url=None, redoc_url=None)


def _verify(credentials: HTTPBasicCredentials | None = Depends(_security)) -> None:
    password = get_settings().ADMIN_PASSWORD
    if not password:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ADMIN_PASSWORD not set")
    if credentials is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username.encode(), b"admin")
    pass_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, _: None = Depends(_verify)) -> HTMLResponse:
    session = get_session()
    try:
        stats = get_dashboard(session)
    finally:
        session.close()
    return _TEMPLATES.TemplateResponse(
        request, "dashboard.html", {"stats": stats, "active": "dashboard"}
    )


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request, _: None = Depends(_verify)) -> HTMLResponse:
    session = get_session()
    try:
        rows = list_sources(session)
        stale_min = get_settings().SOURCE_STALE_ALERT_MINUTES
    finally:
        session.close()
    return _TEMPLATES.TemplateResponse(
        request, "sources.html", {"sources": rows, "stale_min": stale_min, "active": "sources"}
    )


@app.get("/clusters", response_class=HTMLResponse)
def clusters(
    request: Request,
    status: str | None = None,
    _: None = Depends(_verify),
) -> HTMLResponse:
    session = get_session()
    try:
        rows = list_clusters(session, status=status or None)
        status_counts = get_dashboard(session).clusters_by_status
    finally:
        session.close()
    return _TEMPLATES.TemplateResponse(
        request,
        "clusters.html",
        {
            "clusters": rows,
            "filter_status": status or "",
            "status_counts": status_counts,
            "active": "clusters",
        },
    )


@app.get("/clusters/{cluster_id}", response_class=HTMLResponse)
def cluster_detail(
    request: Request, cluster_id: int, _: None = Depends(_verify)
) -> HTMLResponse:
    session = get_session()
    try:
        detail = get_cluster_detail(session, cluster_id)
    finally:
        session.close()
    if not detail:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cluster not found")
    return _TEMPLATES.TemplateResponse(
        request, "cluster.html", {"detail": detail, "active": "clusters"}
    )


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline_feed(
    request: Request,
    hours: float = 3,
    _: None = Depends(_verify),
) -> HTMLResponse:
    hours = max(0.5, min(hours, 72))
    session = get_session()
    try:
        traces, unclustered, since = list_pipeline_traces(session, hours=hours)
        trace_rows = [(t, pipeline_step_status(t)) for t in traces]
    finally:
        session.close()
    return _TEMPLATES.TemplateResponse(
        request,
        "pipeline.html",
        {
            "traces": trace_rows,
            "unclustered": unclustered,
            "hours": hours,
            "since": since,
            "active": "pipeline",
        },
    )
