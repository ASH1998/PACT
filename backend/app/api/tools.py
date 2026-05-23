"""Tools API route — execute tools through the PACT gateway."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ToolCallRequest, ToolCallResponse

router = APIRouter()


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(
    req: ToolCallRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a tool call through the PACT gateway.

    This endpoint only accepts PACT Action Envelopes.
    Raw tool calls are rejected.
    """
    # The envelope must be present
    if not req.envelope:
        raise HTTPException(status_code=400, detail="PACT Action Envelope required")

    # For direct tool calls (not through scenario runner), we need a simplified gateway
    # This is mainly used by the scenario runner; direct calls go through /scenarios/run/{name}
    raise HTTPException(
        status_code=501,
        detail="Direct tool calls should use /scenarios/run/{name}. This endpoint is for future use.",
    )
