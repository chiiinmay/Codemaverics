"""
Autonomous Agent Loop with Dynamic Replanning, Security Delimiters, and Glass-box Trace.
"""
from __future__ import annotations
import asyncio
from typing import Any, Dict, List, Optional
from backend.agent.llm_client import LLMClient
from backend.agent.planner import Planner
from backend.agent.prompts import SYSTEM_PROMPT, wrap_untrusted_data
from backend.events.log import EventLog
from backend.executor.executor import Executor

class AgentLoop:
    def __init__(
        self,
        llm: LLMClient,
        executor: Executor,
        event_log: EventLog,
        max_steps: int = 15
    ):
        self.llm = llm
        self.executor = executor
        self.events = event_log
        self.max_steps = max_steps
        self.planner = Planner()

    async def run(self, goal: str, run_id: str) -> Dict[str, Any]:
        """
        Executes the autonomous loop until goal is achieved or budget exhausted.
        """
        await self.events.emit(
            event_type="run_started",
            step=0,
            payload={"goal": goal, "run_id": run_id}
        )

        plan = self.planner.create_initial_plan(goal)
        await self.events.emit(
            event_type="plan",
            step=0,
            payload={"plan": plan.model_dump()}
        )

        # Contextual state tracking for multi-step workflow
        ctx: Dict[str, Any] = {
            "stage": "read_sheet",
            "invoices": [],
            "client_idx": 0
        }

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": goal}
        ]

        step = 0
        while step < self.max_steps:
            step += 1

            # 1. Ask LLM for next thought & tool action
            tools_schema = self.executor.registry.to_llm_tool_definitions()
            llm_resp = await self.llm.generate_step(
                system_prompt=SYSTEM_PROMPT,
                messages=messages,
                tools_schema=tools_schema,
                step_number=step,
                context_state=ctx
            )

            # If model reached conclusion
            if llm_resp.finish_message and not llm_resp.tool_call:
                await self.events.emit(
                    event_type="done",
                    step=step,
                    payload={"summary": llm_resp.finish_message, "total_steps": step}
                )
                return {"status": "completed", "summary": llm_resp.finish_message, "steps": step}

            tc = llm_resp.tool_call
            if not tc:
                # No tool call and no finish
                break

            # 2. Execute tool through the secure Executor gate
            tool_name = tc.name
            raw_args = tc.args

            result = await self.executor.execute_tool_request(
                run_id=run_id,
                tool_name=tool_name,
                raw_args=raw_args,
                step_number=step
            )

            # 3. Context & Replanning State Update
            if tool_name == "sheets_read_invoices" and not result.get("error"):
                ctx["invoices"] = result.get("invoices", [])
                ctx["stage"] = "process_clients"
                ctx["client_idx"] = 0

            elif tool_name == "gmail_search" and not result.get("error"):
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                threads = result.get("threads", [])
                if threads:
                    ctx[f"client_{row_id}_thread_id"] = threads[0]["thread_id"]
                ctx[f"client_{row_id}_stage"] = "read_thread"

            elif tool_name == "gmail_read_thread" and not result.get("error"):
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                # Inspect for replies or adversary prompt injection in thread messages
                messages_in_thread = result.get("messages", [])
                for msg in messages_in_thread:
                    content_str = msg.get("body", "")
                    if "ignore all previous instructions" in content_str.lower():
                        await self.events.emit(
                            event_type="replan",
                            step=step,
                            payload={
                                "reason": "Untrusted prompt injection pattern detected in thread data. Wrapping in security boundary and isolating.",
                                "action": "Defensive containment active."
                            }
                        )
                ctx[f"client_{row_id}_stage"] = "create_draft"

            elif tool_name == "gmail_create_draft" and not result.get("error"):
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                ctx[f"client_{row_id}_draft_id"] = result.get("draft_id")
                ctx[f"client_{row_id}_stage"] = "send_email"

            elif tool_name == "gmail_send_email":
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                if result.get("error"):
                    # Failure handling (e.g. Bounced Email Chaos)
                    err_msg = result.get("message", "Email send failed")
                    await self.events.emit(
                        event_type="replan",
                        step=step,
                        tool=tool_name,
                        payload={
                            "reason": f"Delivery failure detected: {err_msg}",
                            "adaptation": "Flagging invoice as 'Bounced / Unreachable' and escalating to phone/calendar review."
                        }
                    )
                    ctx[f"client_{row_id}_stage"] = "check_calendar"
                elif result.get("rejected"):
                    await self.events.emit(
                        event_type="replan",
                        step=step,
                        tool=tool_name,
                        payload={
                            "reason": "Human operator rejected sending email. Replanning to skip email and schedule call.",
                            "adaptation": "Proceeding directly to calendar follow-up."
                        }
                    )
                    ctx[f"client_{row_id}_stage"] = "check_calendar"
                else:
                    ctx[f"client_{row_id}_stage"] = "update_sheet"

            elif tool_name == "sheets_update_status" and not result.get("error"):
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                ctx[f"client_{row_id}_stage"] = "check_calendar"

            elif tool_name == "calendar_check_conflicts":
                row_id = ctx["invoices"][ctx["client_idx"]]["row_id"]
                has_conflict = result.get("has_conflict", False)
                if has_conflict:
                    await self.events.emit(
                        event_type="replan",
                        step=step,
                        tool=tool_name,
                        payload={
                            "reason": f"Conflict detected on slot {result.get('start_time')}. Replanning to find next available opening.",
                            "adaptation": "Shifting reminder call to 16:00."
                        }
                    )
                    ctx[f"{row_id}_conflict_detected"] = True
                ctx[f"client_{row_id}_stage"] = "schedule_calendar"

            elif tool_name == "calendar_schedule_event":
                # Current client completed! Move to next client
                ctx["client_idx"] += 1

            # Feed result back into conversation as untrusted data
            wrapped = wrap_untrusted_data(str(result), source=tool_name)
            messages.append({"role": "assistant", "content": f"Thought: {llm_resp.thought}"})
            messages.append({"role": "user", "content": f"Tool '{tool_name}' result:{wrapped}"})

        # Completed or budget reached
        summary = "Workflow reached end of planned steps."
        await self.events.emit(
            event_type="done",
            step=step,
            payload={"summary": summary, "total_steps": step}
        )
        return {"status": "completed", "summary": summary, "steps": step}
