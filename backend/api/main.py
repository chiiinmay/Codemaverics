"""
FastAPI Backend for NUDGE.
Provides REST and SSE endpoints for agent runs, human approval decisions,
world state inspection, chaos injection, and cryptographic audit verification.
"""
from __future__ import annotations
import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.agent.llm_client import LLMClient
from backend.agent.loop import AgentLoop
from backend.events.log import EventLog
from backend.executor.approvals import ApprovalDecision, ApprovalStore
from backend.executor.executor import Executor
from backend.executor.policy import PolicyEngine
from backend.tools.registry import ToolRegistry
from backend.world.chaos import ChaosController
from backend.world.fake_world import FakeWorld
from backend.world.google_world import GoogleWorld

app = FastAPI(title="NUDGE Agent Backend", version="1.0.0")

# Security: CORS supporting local dev and Vercel cloud deployments
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
custom_origin = os.getenv("ALLOWED_ORIGIN")
if custom_origin:
    origins.append(custom_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global runtime state store
class SessionContainer:
    def __init__(self, run_id: str, world_type: str = "fake", chaos: Optional[ChaosController] = None):
        self.run_id = run_id
        self.chaos = chaos or ChaosController()
        if world_type == "google":
            self.world = GoogleWorld()
        else:
            self.world = FakeWorld(chaos=self.chaos)
        self.events = EventLog(run_id=run_id)
        self.approvals = ApprovalStore()
        self.registry = ToolRegistry()
        self.policy = PolicyEngine()
        self.executor = Executor(
            registry=self.registry,
            policy=self.policy,
            world=self.world,
            event_log=self.events,
            approvals=self.approvals
        )
        self.llm = LLMClient()
        self.loop = AgentLoop(
            llm=self.llm,
            executor=self.executor,
            event_log=self.events
        )
        self.task: Optional[asyncio.Task] = None

active_sessions: Dict[str, SessionContainer] = {}
shared_chaos = ChaosController()

class StartRunRequest(BaseModel):
    goal: str = Field(default="Follow up on our 3 overdue client invoices, check for replies, update their status, and schedule reminder calls.")
    world_mode: str = Field(default="fake")  # "fake" or "google"
    chaos_bounced_email: Optional[str] = None
    chaos_calendar_conflict: Optional[str] = None
    chaos_missing_row: Optional[str] = None

class ChaosToggleRequest(BaseModel):
    bounced_email: Optional[str] = None
    calendar_conflict_slot: Optional[str] = None
    missing_row_id: Optional[str] = None
    tool_error_name: Optional[str] = None
    tool_error_msg: Optional[str] = None
    reset: bool = False

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "service": "NUDGE Agent Framework",
        "active_runs": len(active_sessions),
        "chaos": shared_chaos.get_status()
    }

@app.post("/api/runs")
async def start_run(req: StartRunRequest):
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    
    # Configure run-specific chaos
    run_chaos = ChaosController()
    if req.chaos_bounced_email:
        run_chaos.set_bounced_email(req.chaos_bounced_email, True)
    if req.chaos_calendar_conflict:
        run_chaos.set_calendar_conflict(req.chaos_calendar_conflict, True)
    if req.chaos_missing_row:
        run_chaos.set_missing_row(req.chaos_missing_row, True)

    session = SessionContainer(run_id=run_id, world_type=req.world_mode, chaos=run_chaos)
    active_sessions[run_id] = session

    # Launch agent loop in background
    async def _runner():
        try:
            await session.loop.run(goal=req.goal, run_id=run_id)
        except Exception as e:
            await session.events.emit("error", payload={"fatal_error": str(e)})

    session.task = asyncio.create_task(_runner())
    return {"run_id": run_id, "status": "started", "goal": req.goal, "world_mode": req.world_mode}

@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str):
    session = active_sessions.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Run session not found")

    q = session.events.subscribe()

    async def event_generator():
        try:
            while True:
                evt = await q.get()
                yield f"data: {evt.model_dump_json()}\n\n"
                if evt.type in ("done", "error") and "fatal_error" in evt.payload:
                    # Final event sent
                    break
        except asyncio.CancelledError:
            pass
        finally:
            session.events.unsubscribe(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/runs/{run_id}/approvals")
async def get_pending_approvals(run_id: str):
    session = active_sessions.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Run session not found")
    return {"pending": session.approvals.list_for_run(run_id)}

@app.post("/api/runs/{run_id}/approve")
async def submit_approval_decision(run_id: str, decision: ApprovalDecision):
    session = active_sessions.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Run session not found")
    try:
        resolved = session.approvals.resolve(decision)
        return {"status": "decision_recorded", "action_id": decision.action_id, "kind": decision.kind}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/runs/{run_id}/state")
async def get_run_world_state(run_id: str):
    session = active_sessions.get(run_id)
    if not session:
        raise HTTPException(status_code=404, detail="Run session not found")
    return {
        "run_id": run_id,
        "world_state": session.world.get_state_snapshot(),
        "total_events": len(session.events.events),
        "last_hash": session.events.last_hash
    }

@app.get("/api/chaos")
async def get_chaos():
    return shared_chaos.get_status()

@app.post("/api/chaos/toggle")
async def toggle_chaos(req: ChaosToggleRequest):
    if req.reset:
        shared_chaos.reset_all()
        return {"status": "reset", "chaos": shared_chaos.get_status()}

    if req.bounced_email:
        active = req.bounced_email not in shared_chaos.bounced_emails
        shared_chaos.set_bounced_email(req.bounced_email, active)

    if req.calendar_conflict_slot:
        active = req.calendar_conflict_slot not in shared_chaos.conflicting_slots
        shared_chaos.set_calendar_conflict(req.calendar_conflict_slot, active)

    if req.missing_row_id:
        active = req.missing_row_id not in shared_chaos.missing_rows
        shared_chaos.set_missing_row(req.missing_row_id, active)

    if req.tool_error_name:
        shared_chaos.set_tool_error(req.tool_error_name, req.tool_error_msg)

    return {"status": "updated", "chaos": shared_chaos.get_status()}

@app.post("/api/verify-audit")
async def verify_audit(req: Dict[str, Any]):
    run_id = req.get("run_id")
    session = active_sessions.get(run_id) if run_id else None
    
    events_to_check = []
    if session:
        events_to_check = session.events.events
    elif run_id:
        # Check from saved file
        filepath = os.path.join(os.getcwd(), "eval_runs", f"{run_id}_audit.jsonl")
        if os.path.exists(filepath):
            from backend.events.schema import RunEvent
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        events_to_check.append(RunEvent(**json.loads(line)))

    if not events_to_check:
        raise HTTPException(status_code=404, detail="No audit log found for verification.")

    is_valid, failing_step, message = EventLog.verify_chain(events_to_check)
    return {
        "run_id": run_id,
        "is_valid": is_valid,
        "total_events": len(events_to_check),
        "failing_step": failing_step,
        "message": message,
        "root_hash": events_to_check[0].hash if events_to_check else None,
        "latest_hash": events_to_check[-1].hash if events_to_check else None
    }
