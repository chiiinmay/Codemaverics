"""
Event Schema for NUDGE Event Stream and Hash-Chained Audit Log.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

EventType = Literal[
    "run_started",
    "plan",
    "tool_call",
    "tool_result",
    "approval_required",
    "approval_decision",
    "blocked",
    "replan",
    "chaos_injected",
    "error",
    "done"
]

RiskTier = Literal["auto", "notify", "approve", "forbid"]

class RunEvent(BaseModel):
    id: str = Field(description="Unique event ID, e.g. evt_001")
    run_id: str = Field(description="Run session ID")
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: EventType = Field(description="Category of event")
    step: int = Field(default=0, description="Step number in the agent loop")
    tool: Optional[str] = Field(default=None, description="Tool name if tool-related")
    tier: Optional[RiskTier] = Field(default=None, description="Risk tier of the action")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Event data details")
    prev_hash: str = Field(default="0" * 64, description="SHA-256 hash of previous event")
    hash: str = Field(default="", description="Cryptographic hash of current event")

    def compute_hash(self, prev_hash: str) -> str:
        import hashlib
        import json
        
        # Consistent payload serialization
        payload_str = json.dumps(self.payload, sort_keys=True, separators=(',', ':'))
        raw = f"{prev_hash}|{self.id}|{self.run_id}|{self.ts}|{self.type}|{self.step}|{self.tool or ''}|{self.tier or ''}|{payload_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
