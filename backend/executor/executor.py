"""
Executor: The sole execution gateway between the LLM and real/simulated tools.
Enforces the NUDGE Security Axiom: The LLM NEVER touches a tool directly.
"""
from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from backend.events.log import EventLog
from backend.events.schema import RiskTier
from backend.executor.approvals import ApprovalDecision, ApprovalStore, PendingAction
from backend.executor.policy import PolicyEngine
from backend.tools.registry import ToolRegistry
from backend.world.base import World

class Executor:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: PolicyEngine,
        world: World,
        event_log: EventLog,
        approvals: Optional[ApprovalStore] = None
    ):
        self.registry = registry
        self.policy = policy
        self.world = world
        self.events = event_log
        self.approvals = approvals or ApprovalStore()
        self.tool_history: List[str] = []

    async def execute_tool_request(
        self,
        run_id: str,
        tool_name: str,
        raw_args: Dict[str, Any],
        step_number: int
    ) -> Dict[str, Any]:
        """
        Processes an LLM-requested tool invocation through the 5-step security gate.
        """
        # Step 1: Tool existence & registry check
        if not self.registry.has(tool_name):
            reason = f"Unknown tool '{tool_name}' requested by model."
            await self.events.emit(
                event_type="blocked",
                step=step_number,
                tool=tool_name,
                tier="forbid",
                payload={"reason": reason, "raw_args": raw_args}
            )
            return {"error": True, "blocked": True, "reason": reason}

        spec = self.registry.get(tool_name)
        tier: RiskTier = spec.tier

        # Step 2: Strict Pydantic Argument Validation
        try:
            validated_model = spec.schema_class(**raw_args)
            args = validated_model.model_dump()
        except ValidationError as val_err:
            reason = f"Malformed tool arguments for '{tool_name}': {val_err.errors()}"
            await self.events.emit(
                event_type="error",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={"error": reason, "raw_args": raw_args}
            )
            return {"error": True, "validation_error": True, "reason": reason}

        # Step 3: Policy Engine Verification
        verdict = self.policy.check(
            tool_name=tool_name,
            tier=tier,
            args=args,
            step_count=step_number,
            tool_history=self.tool_history
        )

        if verdict.forbidden:
            await self.events.emit(
                event_type="blocked",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={"reason": verdict.reason, "args": args}
            )
            return {"error": True, "blocked": True, "forbidden": True, "reason": verdict.reason}

        # Step 4: The Approval Gate (Pause & Wait for Human "Nudge Moment")
        action_id = f"act_{run_id}_{step_number:02d}"
        if verdict.requires_approval or tier == "approve":
            pending = self.approvals.create(run_id=run_id, tool_name=tool_name, args=args)
            action_id = pending.action_id
            
            await self.events.emit(
                event_type="approval_required",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={
                    "action_id": action_id,
                    "tool": tool_name,
                    "args": args,
                    "prompt": f"Approval required to execute {tool_name} with target: {args.get('to') or args.get('title') or args}"
                }
            )

            # Wait asynchronously for the human operator to submit decision via /approve endpoint
            decision: ApprovalDecision = await pending.future

            await self.events.emit(
                event_type="approval_decision",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={
                    "action_id": action_id,
                    "decision": decision.kind,
                    "decided_by": decision.decided_by,
                    "timestamp": decision.timestamp,
                    "edited_args": decision.edited_args
                }
            )

            if decision.kind == "reject":
                return {
                    "rejected": True,
                    "reason": "Human operator rejected the action. You must replan or proceed with alternate steps."
                }

            if decision.kind == "edit" and decision.edited_args:
                # Anti-tamper: re-validate edited payload through Pydantic and Policy
                try:
                    revalidated = spec.schema_class(**decision.edited_args)
                    args = revalidated.model_dump()
                    re_verdict = self.policy.check(
                        tool_name=tool_name,
                        tier=tier,
                        args=args,
                        step_count=step_number,
                        tool_history=self.tool_history
                    )
                    if re_verdict.forbidden:
                        await self.events.emit(
                            event_type="blocked",
                            step=step_number,
                            tool=tool_name,
                            tier=tier,
                            payload={"reason": f"Edited payload forbidden: {re_verdict.reason}", "args": args}
                        )
                        return {"error": True, "blocked": True, "reason": re_verdict.reason}
                except ValidationError as ve:
                    return {"error": True, "reason": f"Edited arguments invalid: {ve.errors()}"}

        # Step 5: Execution within World + Hash-chained Audit Recording
        await self.events.emit(
            event_type="tool_call",
            step=step_number,
            tool=tool_name,
            tier=tier,
            payload={"args": args, "idem_key": action_id}
        )

        try:
            result = await self.world.execute(tool_name=tool_name, args=args, idem_key=action_id)
            self.tool_history.append(tool_name)

            # If sheets were read, update policy recipient allowlist dynamically
            if tool_name == "sheets_read_invoices" and "invoices" in result:
                self.policy.update_recipients_from_invoices(result["invoices"])

            await self.events.emit(
                event_type="tool_result",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={"result": result, "status": "success"}
            )
            return result

        except Exception as exec_err:
            error_msg = str(exec_err)
            await self.events.emit(
                event_type="error",
                step=step_number,
                tool=tool_name,
                tier=tier,
                payload={"error": error_msg, "tool": tool_name}
            )
            return {"error": True, "execution_failure": True, "message": error_msg}
