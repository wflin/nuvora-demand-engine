"""FastAPI application entrypoint.

P0-002 exposes the legacy-compatible Research / Research Job endpoints under
``/api`` together with health and readiness checks. Versioned ``/api/v1``
endpoints are introduced in later phases.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.research import router as research_router
from app.api.research_jobs import router as research_jobs_router
from app.core.settings import settings

logging.basicConfig(level=settings.log_level)

app = FastAPI(title="Nuvora Demand Engine API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(health_router)
app.include_router(research_router, prefix="/api")
app.include_router(research_jobs_router, prefix="/api")
