from fastapi import APIRouter, Depends

from app.dependencies import require_roles
from app.models import User, UserRole
from app.utils.metrics_store import metrics_store

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/summary")
def summary(_user: User = Depends(require_roles(UserRole.ADMIN.value))) -> dict:
    """JSON summary for the operations dashboard."""
    return metrics_store.snapshot()
