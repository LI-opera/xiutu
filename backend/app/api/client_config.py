from fastapi import APIRouter, Depends, Request

from app.api.dependencies import authenticated
from app.domain.schemas import ClientConfig

router = APIRouter(prefix="/api/v2/client-config", tags=["client"])


@router.get("", response_model=ClientConfig)
def client_config(request: Request, principal=Depends(authenticated)):
    """Expose only non-secret limits that the authenticated UI must enforce."""

    settings = request.app.state.settings
    return {
        "upload_max_bytes": settings.upload_max_bytes,
        "retrieval_profile": settings.retrieval_profile,
    }
