"""Versioned API route for the Google source connector."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.google_collect import GoogleCollectResponse, GoogleCollectStats
from connectors.google.google_connector import GoogleConnector
from connectors.google.query import GoogleQuery

router = APIRouter(prefix="/api/v1/sources/google", tags=["google-source"])


def get_google_connector() -> GoogleConnector:
    """Dependency that supplies the Google connector (overridable in tests)."""
    return GoogleConnector()


@router.post(
    "/collect",
    response_model=GoogleCollectResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid request"},
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Every requested source capability failed"
        },
    },
)
def collect_google(
    payload: GoogleQuery,
    connector: GoogleConnector = Depends(get_google_connector),
) -> GoogleCollectResponse:
    """Collect Google Suggest / Google Trends candidates for a seed query."""
    if not payload.seed_query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="seed_query must not be blank",
        )
    if not payload.include_suggest and not payload.include_trends:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="at least one of include_suggest / include_trends must be true",
        )

    result = connector.collect(payload)
    if result.all_requested_sources_failed:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "all requested sources failed",
                "sources": [
                    source.model_dump(mode="json") for source in result.sources
                ],
            },
        )

    stats = GoogleCollectStats(
        total_count=result.stats.total_count,
        by_capability=result.stats.by_capability,
    )
    return GoogleCollectResponse(
        items=result.candidates,
        stats=stats,
        sources=result.sources,
    )


__all__ = ["get_google_connector", "router"]
