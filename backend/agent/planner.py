"""
Agent Planner: Breaks natural language goals into structured execution steps,
maintains tracking state, and manages failure replanning.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class PlanStep(BaseModel):
    step_id: int
    description: str
    target_tool: str
    status: str = "pending"  # pending, executing, completed, failed, replanned

class ExecutionPlan(BaseModel):
    goal: str
    steps: List[PlanStep] = []
    current_step_index: int = 0

class Planner:
    def __init__(self):
        pass

    def create_initial_plan(self, goal: str) -> ExecutionPlan:
        steps = [
            PlanStep(step_id=1, description="Read overdue client invoices from spreadsheet", target_tool="sheets_read_invoices"),
            PlanStep(step_id=2, description="Check past email communications and responses for each client", target_tool="gmail_search"),
            PlanStep(step_id=3, description="Draft customized reminder messages for overdue invoices", target_tool="gmail_create_draft"),
            PlanStep(step_id=4, description="Request human approval to send reminder emails (NUDGE Moment)", target_tool="gmail_send_email"),
            PlanStep(step_id=5, description="Update status in tracking spreadsheet to Follow-Up Sent", target_tool="sheets_update_status"),
            PlanStep(step_id=6, description="Check availability and request booking follow-up reminder calls", target_tool="calendar_schedule_event")
        ]
        return ExecutionPlan(goal=goal, steps=steps)
