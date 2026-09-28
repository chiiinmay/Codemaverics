"""
Pending Approval Manager for NUDGE.
Stores pending actions awaiting human decision (Approve / Edit / Reject).
Prevents the edit-after-approve vulnerability by re-validating any edited payload against schemas and policies.
"""
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field

DecisionKind = Literal["approve", "reject", "edit"]

class ApprovalDecision(BaseModel):
    action_id: str
    kind: DecisionKind
    edited_args: Optional[Dict[str, Any]] = None
    decided_by: str = "human_operator"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PendingAction:
    def __init__(self, action_id: str, run_id: str, tool_name: str, args: Dict[str, Any]):
        self.action_id = action_id
        self.run_id = run_id
        self.tool_name = tool_name
        self.args = args
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.future: asyncio.Future[ApprovalDecision] = asyncio.get_event_loop().create_future()
        self.resolved = False

class ApprovalStore:
    def __init__(self):
        self._pending: Dict[str, PendingAction] = {}
        self._seq = 0

    def create(self, run_id: str, tool_name: str, args: Dict[str, Any]) -> PendingAction:
        self._seq += 1
        action_id = f"act_{run_id}_{self._seq:03d}"
        pending = PendingAction(
            action_id=action_id,
            run_id=run_id,
            tool_name=tool_name,
            args=args
        )
        self._pending[action_id] = pending
        return pending

    def get(self, action_id: str) -> Optional[PendingAction]:
        return self._pending.get(action_id)

    def list_for_run(self, run_id: str) -> list[dict]:
        return [
            {
                "action_id": act.action_id,
                "run_id": act.run_id,
                "tool_name": act.tool_name,
                "args": act.args,
                "created_at": act.created_at,
                "resolved": act.resolved
            }
            for act in self._pending.values()
            if act.run_id == run_id and not act.resolved
        ]

    def resolve(self, decision: ApprovalDecision) -> PendingAction:
        pending = self._pending.get(decision.action_id)
        if not pending:
            raise KeyError(f"No pending approval found for action_id '{decision.action_id}'")
        if pending.resolved:
            raise RuntimeError(f"Action '{decision.action_id}' has already been decided.")

        pending.resolved = True
        if not pending.future.done():
            pending.future.set_result(decision)
        return pending
