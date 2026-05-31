"""Proxy endpoints — provider-agnostic chat proxy with PACT model event recording."""

from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
from app.adapters.providers.base import ModelResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_provider(name: str):
    """Return a provider instance by name."""
    if name == "gemini":
        from app.adapters.providers.gemini import GeminiProvider
        return GeminiProvider()
    elif name == "bedrock":
        from app.adapters.providers.bedrock import BedrockProvider
        return BedrockProvider()
    elif name in ("openai", "openai_compatible"):
        from app.adapters.providers.openai_compatible import OpenAICompatibleProvider
        return OpenAICompatibleProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")


def _provider_error_detail(prefix: str, exc: Exception) -> str:
    """Return provider error detail without leaking credentials from URLs."""
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        return f"{prefix}: HTTP {status_code}"
    return f"{prefix}: {exc.__class__.__name__}"


async def _ensure_run(
    db: AsyncSession,
    run_id: str | None,
    agent_id: str,
) -> str:
    """Find or create a run record. Returns the run_id."""
    if not run_id:
        run_id = f"run_{uuid.uuid4().hex[:12]}"

    result = await db.execute(select(Run).where(Run.run_id == run_id))
    existing = result.scalar_one_or_none()
    if not existing:
        run = Run(
            run_id=run_id,
            agent_id=agent_id or "proxy_user",
            scenario_name="proxy",
            user_goal="proxied model call",
            status="running",
        )
        db.add(run)
        await db.commit()

    return run_id


def _hash_text(text: str) -> str:
    """SHA-256 hash of a text string. Returns 'sha256:hex'."""
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


async def _persist_model_event(
    db: AsyncSession,
    run_id: str,
    event_type: str,
    provider: str,
    model: str,
    request_json: str = '{}',
    response_json: str = '{}',
    tool_calls: list | None = None,
    token_usage: dict | None = None,
    raw_request_json: str = '{}',
    raw_response_json: str = '{}',
) -> dict:
    """Persist a model event to the database and return a summary dict."""
    from app.models.model_event import ModelEvent
    event_id = f"mevt_{uuid.uuid4().hex[:12]}"
    event = ModelEvent(
        run_id=run_id,
        event_id=event_id,
        provider=provider,
        model=model,
        request_json=request_json,
        response_json=response_json,
        tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
        token_usage_json=json.dumps(token_usage) if token_usage else None,
        raw_request_json=raw_request_json,
        raw_response_json=raw_response_json,
    )
    db.add(event)
    await db.commit()
    return {
        "event_id": event_id,
        "event_type": event_type,
        "run_id": run_id,
        "provider": provider,
        "model": model,
    }


async def _create_provenance_event(
    db: AsyncSession,
    run_id: str,
    provider_name: str,
    model: str,
    text_content: str | None = None,
) -> str:
    """Create a provenance event for model output. Returns the event_id."""
    from app.models.provenance_event import ProvenanceEvent
    prov_event_id = f"pevt_{uuid.uuid4().hex[:12]}"
    prov_event = ProvenanceEvent(
        run_id=run_id,
        event_id=prov_event_id,
        source_type="model_output",
        source_label="agent.generated",
        content_digest=_hash_text(text_content) if text_content else None,
        metadata_json=json.dumps({"provider": provider_name, "model": model}),
    )
    db.add(prov_event)
    await db.commit()
    return prov_event_id


# ---------------------------------------------------------------------------
# /v1/proxy/chat — provider-agnostic chat proxy
# ---------------------------------------------------------------------------

@router.post("/v1/proxy/chat")
async def proxy_chat(request: Request, db: AsyncSession = Depends(get_db)):
    """Provider-agnostic chat proxy.

    Accepts a JSON body with ``provider``, ``model``, ``messages``, optional
    ``tools``, and generation parameters.  Forwards to the specified provider,
    records the model event in the PACT run, and returns the provider response.
    """
    body = await request.json()
    raw_request_json = json.dumps(body)

    provider_name = body.pop("provider", "openai")
    try:
        provider = _get_provider(provider_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Extract PACT metadata
    pact_run_id = request.headers.get("X-PACT-Run-Id")
    agent_id = body.get("agent_id", request.headers.get("X-PACT-Agent-Id", "proxy_user"))

    run_id = await _ensure_run(db, pact_run_id, agent_id)

    # Build normalized request
    req = provider.normalize_request(body)
    req.run_id = run_id
    req.agent_id = agent_id

    # Invoke provider
    try:
        response: ModelResponse = await provider.invoke(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_provider_error_detail("Provider error", exc))

    # Persist model event (response)
    request_json = json.dumps({
        "provider": provider_name,
        "model": req.model,
        "message_count": len(req.messages),
        "tool_count": len(req.tool_declarations),
    })
    response_json = json.dumps({
        "provider": response.provider,
        "model": response.model,
        "text_length": len(response.text_content),
        "tool_call_count": len(response.tool_calls),
        "finish_reason": response.finish_reason,
    })
    raw_response_json = json.dumps(response.raw_response) if response.raw_response else '{}'

    event_info = await _persist_model_event(
        db=db,
        run_id=run_id,
        event_type="model_response",
        provider=provider_name,
        model=response.model,
        request_json=request_json,
        response_json=response_json,
        tool_calls=[{"tool_id": tc.tool_id, "args": tc.args, "tool_call_id": tc.tool_call_id} for tc in response.tool_calls] if response.tool_calls else None,
        token_usage=response.token_usage,
        raw_request_json=raw_request_json,
        raw_response_json=raw_response_json,
    )

    # Create provenance event
    await _create_provenance_event(
        db=db,
        run_id=run_id,
        provider_name=provider_name,
        model=response.model,
        text_content=response.text_content,
    )

    # Build result — return provider response in normalized format
    result = {
        "run_id": run_id,
        "provider": response.provider,
        "model": response.model,
        "text_content": response.text_content,
        "tool_calls": [
            {"tool_id": tc.tool_id, "args": tc.args, "tool_call_id": tc.tool_call_id}
            for tc in response.tool_calls
        ],
        "token_usage": response.token_usage,
        "safety_ratings": response.safety_ratings,
        "finish_reason": response.finish_reason,
        "event_id": event_info["event_id"],
    }

    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# /v1/proxy/gemini/{model_path} — Gemini-compatible proxy
# ---------------------------------------------------------------------------

@router.post("/v1/proxy/gemini/{model_path:path}")
async def proxy_gemini(model_path: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Gemini-compatible proxy endpoint.

    Accepts a Gemini generateContent request body and forwards to the Gemini
    provider.  Preserves the Gemini response format.
    """
    body = await request.json()
    raw_request_json = json.dumps(body)

    provider = _get_provider("gemini")

    pact_run_id = request.headers.get("X-PACT-Run-Id")
    agent_id = request.headers.get("X-PACT-Agent-Id", "proxy_user")

    # Inject model from path if not in body
    if "model" not in body:
        # model_path is like "gemini-pro:generateContent"
        body["model"] = model_path.split(":")[0] if ":" in model_path else model_path

    run_id = await _ensure_run(db, pact_run_id, agent_id)

    # Normalize to ModelRequest
    req = provider.normalize_request(body)
    req.run_id = run_id
    req.agent_id = agent_id

    # Invoke
    try:
        response = await provider.invoke(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_provider_error_detail("Gemini error", exc))

    # Persist model event
    request_json = json.dumps({
        "provider": "gemini",
        "model": req.model,
        "message_count": len(req.messages),
    })
    response_json = json.dumps({
        "provider": "gemini",
        "model": response.model,
        "text_length": len(response.text_content),
        "tool_call_count": len(response.tool_calls),
    })
    raw_response_json = json.dumps(response.raw_response) if response.raw_response else '{}'

    await _persist_model_event(
        db=db,
        run_id=run_id,
        event_type="model_response",
        provider="gemini",
        model=response.model,
        request_json=request_json,
        response_json=response_json,
        tool_calls=[{"tool_id": tc.tool_id, "args": tc.args, "tool_call_id": tc.tool_call_id} for tc in response.tool_calls] if response.tool_calls else None,
        token_usage=None,
        raw_request_json=raw_request_json,
        raw_response_json=raw_response_json,
    )

    # Create provenance event
    await _create_provenance_event(
        db=db,
        run_id=run_id,
        provider_name="gemini",
        model=response.model,
        text_content=response.text_content,
    )

    # Return in Gemini response format
    return JSONResponse(content=response.raw_response)


# ---------------------------------------------------------------------------
# /v1/proxy/bedrock/converse — Bedrock Converse-compatible proxy
# ---------------------------------------------------------------------------

@router.post("/v1/proxy/bedrock/converse")
async def proxy_bedrock(request: Request, db: AsyncSession = Depends(get_db)):
    """Bedrock Converse-compatible proxy endpoint.

    Accepts a Bedrock Converse request body and forwards to the Bedrock
    provider.  Preserves the Bedrock response format.
    """
    body = await request.json()
    raw_request_json = json.dumps(body)

    provider = _get_provider("bedrock")

    pact_run_id = request.headers.get("X-PACT-Run-Id")
    agent_id = request.headers.get("X-PACT-Agent-Id", "proxy_user")

    run_id = await _ensure_run(db, pact_run_id, agent_id)

    # Normalize to ModelRequest
    req = provider.normalize_request(body)
    req.run_id = run_id
    req.agent_id = agent_id

    # Invoke (currently mocked)
    try:
        response = await provider.invoke(req)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=_provider_error_detail("Bedrock error", exc))

    # Persist model event
    request_json = json.dumps({
        "provider": "bedrock",
        "model": req.model,
        "message_count": len(req.messages),
    })
    response_json = json.dumps({
        "provider": "bedrock",
        "model": response.model,
        "text_length": len(response.text_content),
        "tool_call_count": len(response.tool_calls),
    })
    raw_response_json = json.dumps(response.raw_response) if response.raw_response else '{}'

    await _persist_model_event(
        db=db,
        run_id=run_id,
        event_type="model_response",
        provider="bedrock",
        model=response.model,
        request_json=request_json,
        response_json=response_json,
        tool_calls=[{"tool_id": tc.tool_id, "args": tc.args, "tool_call_id": tc.tool_call_id} for tc in response.tool_calls] if response.tool_calls else None,
        token_usage=None,
        raw_request_json=raw_request_json,
        raw_response_json=raw_response_json,
    )

    # Create provenance event
    await _create_provenance_event(
        db=db,
        run_id=run_id,
        provider_name="bedrock",
        model=response.model,
        text_content=response.text_content,
    )

    # Return in Bedrock Converse response format
    return JSONResponse(content=response.raw_response)
