"""V1 Tools API — register and list tools with metadata (DB-backed)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tool_registry import ToolRegistry as ToolRegistryModel
from app.core.registry import get_default_registry

router = APIRouter()

# Valid side-effect classes (matches SideEffect enum in core/tool_metadata.py)
VALID_SIDE_EFFECTS = frozenset([
    "none", "read", "internal_write", "external_write",
    "delete", "payment", "shell", "network", "privileged",
])

# Valid sensitivity / risk tiers
VALID_SENSITIVITY = frozenset(["low", "medium", "high", "critical"])


class RegisterToolRequest(BaseModel):
    tool_id: str
    name: str
    description: str = ""
    side_effect: str = "none"      # none|read|internal_write|external_write|delete|payment|shell|network|privileged
    sensitivity: str = "medium"    # low|medium|high|critical
    resource_type: str = "default"
    requires_approval: bool = False


@router.post("/register")
async def register_tool(req: RegisterToolRequest, db: AsyncSession = Depends(get_db)):
    """Register a tool with metadata. Persists to DB and updates core registry."""
    # Validate side_effect
    if req.side_effect not in VALID_SIDE_EFFECTS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid side_effect '{req.side_effect}'. Must be one of: {sorted(VALID_SIDE_EFFECTS)}",
        )
    if req.sensitivity not in VALID_SENSITIVITY:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sensitivity '{req.sensitivity}'. Must be one of: {sorted(VALID_SENSITIVITY)}",
        )

    now = datetime.now(timezone.utc)

    # Upsert to DB
    result = await db.execute(select(ToolRegistryModel).where(ToolRegistryModel.tool_id == req.tool_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.display_name = req.name
        existing.description = req.description
        existing.side_effect = req.side_effect
        existing.sensitivity = req.sensitivity
        existing.resource_type = req.resource_type
        existing.default_requires_approval = req.requires_approval
        await db.commit()
    else:
        tool = ToolRegistryModel(
            tool_id=req.tool_id,
            display_name=req.name,
            description=req.description,
            side_effect=req.side_effect,
            sensitivity=req.sensitivity,
            resource_type=req.resource_type,
            default_requires_approval=req.requires_approval,
            registered_at=now,
        )
        db.add(tool)
        await db.commit()

    # Also register in core registry (in-memory cache)
    try:
        registry = get_default_registry()
        registry.register_tool(req.tool_id, {
            "display_name": req.name,
            "description": req.description,
            "side_effect": req.side_effect,
            "sensitivity": req.sensitivity,
            "resource_type": req.resource_type,
            "default_requires_approval": req.requires_approval,
        })
    except Exception:
        pass  # non-fatal if core registry fails

    return {
        "tool_id": req.tool_id,
        "name": req.name,
        "description": req.description,
        "side_effect": req.side_effect,
        "sensitivity": req.sensitivity,
        "resource_type": req.resource_type,
        "requires_approval": req.requires_approval,
        "registered_at": now.isoformat(),
    }


@router.get("")
async def list_tools(db: AsyncSession = Depends(get_db)):
    """List all registered tools from DB."""
    result = await db.execute(select(ToolRegistryModel))
    tools = result.scalars().all()
    return {
        "tools": [
            {
                "tool_id": t.tool_id,
                "name": t.display_name,
                "description": t.description,
                "side_effect": t.side_effect,
                "sensitivity": t.sensitivity,
                "resource_type": t.resource_type,
                "requires_approval": t.default_requires_approval,
                "registered_at": t.registered_at.isoformat() if t.registered_at else None,
            }
            for t in tools
        ],
        "count": len(tools),
    }


@router.get("/{tool_id}")
async def get_tool(tool_id: str, db: AsyncSession = Depends(get_db)):
    """Get tool details from DB."""
    result = await db.execute(select(ToolRegistryModel).where(ToolRegistryModel.tool_id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool {tool_id} not found")
    return {
        "tool_id": tool.tool_id,
        "name": tool.display_name,
        "description": tool.description,
        "side_effect": tool.side_effect,
        "sensitivity": tool.sensitivity,
        "resource_type": tool.resource_type,
        "requires_approval": tool.default_requires_approval,
        "registered_at": tool.registered_at.isoformat() if tool.registered_at else None,
    }
