"""V1 API surface — a cleaner REST API over existing PACT services."""

from fastapi import APIRouter

from app.api.v1.runs import router as runs_router
from app.api.v1.actions import router as actions_router
from app.api.v1.tools import router as tools_router
from app.api.v1.policies import router as policies_router
from app.api.v1.approvals import router as approvals_router
from app.api.v1.intents import router as intents_router
from app.api.v1.capabilities import router as capabilities_router
from app.api.v1.gateway import router as gateway_router
from app.api.v1.agents import router as agents_router

v1_router = APIRouter()
v1_router.include_router(runs_router, prefix="/runs", tags=["V1 Runs"])
v1_router.include_router(actions_router, prefix="/actions", tags=["V1 Actions"])
v1_router.include_router(tools_router, prefix="/tools", tags=["V1 Tools"])
v1_router.include_router(policies_router, prefix="/policies", tags=["V1 Policies"])
v1_router.include_router(approvals_router, prefix="/approvals", tags=["V1 Approvals"])
v1_router.include_router(intents_router, prefix="/intents", tags=["V1 Intents"])
v1_router.include_router(capabilities_router, prefix="/capabilities", tags=["V1 Capabilities"])
v1_router.include_router(gateway_router, prefix="/gateway", tags=["V1 Gateway"])
v1_router.include_router(agents_router, prefix="/agents", tags=["V1 Agents"])
