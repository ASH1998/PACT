"""V1 Actions API — propose and execute actions through the PACT runtime."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.models.action import Action

router = APIRouter()


class ProposeActionRequest(BaseModel):
    run_id: str
    agent_id: str
    tool: str
    args: dict = {}
    intent_hash: str = ""
    capability_token_hash: str = ""
    agent_private_key: str = ""  # optional; if provided, envelope is signed


@router.post("/propose")
async def propose_action(req: ProposeActionRequest, db: AsyncSession = Depends(get_db)):
    """Propose an action — evaluate policy without executing the tool.

    Uses PactRuntime.evaluate_action() which is the true dry-run path:
    builds an envelope, runs it through passport/sig/cap/intent/policy checks,
    records ledger entry and policy decision, but does NOT execute the tool.
    """
    # Verify run exists
    result = await db.execute(select(Run).where(Run.run_id == req.run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {req.run_id} not found")

    from app.core.factory import get_runtime
    runtime = get_runtime()

    result = await runtime.evaluate_action(
        db=db,
        run_id=req.run_id,
        agent_id=req.agent_id,
        tool=req.tool,
        args=req.args,
        intent_hash=req.intent_hash,
        capability_token_hash=req.capability_token_hash,
        agent_private_key=req.agent_private_key or None,
    )

    return result


class AttachResultRequest(BaseModel):
    result: dict = {}


@router.post("/{action_hash}/result")
async def attach_result(
    action_hash: str, req: AttachResultRequest, db: AsyncSession = Depends(get_db)
):
    """Attach a client-executed tool result to an action.

    Used by external clients that execute tools locally after the gateway
    returns ALLOW. The result is persisted on the action record for the
    dashboard and replay views.
    """
    result = await db.execute(select(Action).where(Action.action_hash == action_hash))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_hash} not found")

    from app.core.factory import get_runtime

    runtime = get_runtime()
    await runtime.record_tool_result(db, action_hash, req.result)
    return {"action_hash": action_hash, "status": action.status, "recorded": True}


@router.post("/{action_id}/execute")
async def execute_action(action_id: str, db: AsyncSession = Depends(get_db)):
    """Execute an approved action.

    Looks up an action by its hash and, if its status is ``allowed``,
    executes the underlying tool via the registry.
    """
    result = await db.execute(
        select(Action).where(Action.action_hash == action_id)
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

    if action.status == "blocked":
        raise HTTPException(status_code=403, detail="Action is blocked and cannot be executed")

    if action.status not in ("allowed", "pending_approval"):
        raise HTTPException(
            status_code=400,
            detail=f"Action status is '{action.status}', cannot execute",
        )

    # Look up tool in registry (falls back to legacy mock tools)
    from app.tools import get_mock_tool

    tool_fn = get_mock_tool(action.tool)
    tool_result = None
    if tool_fn:
        try:
            args = json.loads(action.args_json) if action.args_json else {}
        except json.JSONDecodeError:
            args = {}
        tool_result = tool_fn(**args)

    # Persist result (sensitive fields stripped — never store secret content)
    if tool_result is not None:
        from app.core.result_sanitizer import strip_sensitive_fields
        action.result_json = json.dumps(strip_sensitive_fields(tool_result))
        await db.commit()

    return {
        "action_hash": action.action_hash,
        "tool": action.tool,
        "status": action.status,
        "result": tool_result,
    }
