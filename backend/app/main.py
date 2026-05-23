"""FastAPI application entrypoint for PACT backend."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB on startup, close on shutdown."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="PACT — Provenance-Aware Capability Tokens",
    description="Runtime security protocol for autonomous AI agent actions.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "pact-backend", "version": "0.1.0"}


# API routers
from app.api import agents, intents, capabilities, tools, scenarios, runs, dashboard

app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(intents.router, prefix="/intents", tags=["Intents"])
app.include_router(capabilities.router, prefix="/capabilities", tags=["Capabilities"])
app.include_router(tools.router, prefix="/tools", tags=["Tools"])
app.include_router(scenarios.router, prefix="/scenarios", tags=["Scenarios"])
app.include_router(runs.router, prefix="/runs", tags=["Runs"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
