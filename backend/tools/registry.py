"""
Tool Registry with Risk Tier Definitions and Schema Bindings.
"""
from typing import Any, Dict, List, Type
from pydantic import BaseModel
from backend.events.schema import RiskTier
from backend.tools.schemas import (
    SheetsReadInvoicesArgs,
    SheetsUpdateStatusArgs,
    GmailSearchArgs,
    GmailReadThreadArgs,
    GmailCreateDraftArgs,
    GmailSendEmailArgs,
    CalendarCheckConflictsArgs,
    CalendarScheduleEventArgs,
    BulkDeleteArgs,
    ForwardMailArgs,
)

class ToolSpec(BaseModel):
    name: str
    description: str
    tier: RiskTier
    schema_class: Type[BaseModel]

    class Config:
        arbitrary_types_allowed = True

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def register(self, name: str, description: str, tier: RiskTier, schema_class: Type[BaseModel]):
        self._tools[name] = ToolSpec(
            name=name,
            description=description,
            tier=tier,
            schema_class=schema_class
        )

    def _register_defaults(self):
        # Auto tier: Safe read-only actions
        self.register(
            name="sheets_read_invoices",
            description="Read overdue invoices tracking sheet to retrieve client names, invoice IDs, amounts, and contact emails.",
            tier="auto",
            schema_class=SheetsReadInvoicesArgs
        )
        self.register(
            name="gmail_search",
            description="Search Gmail inbox for customer email threads or past communications.",
            tier="auto",
            schema_class=GmailSearchArgs
        )
        self.register(
            name="gmail_read_thread",
            description="Read the specific message contents and replies of an email thread.",
            tier="auto",
            schema_class=GmailReadThreadArgs
        )
        self.register(
            name="calendar_check_conflicts",
            description="Check calendar for conflicts on a given date and time window.",
            tier="auto",
            schema_class=CalendarCheckConflictsArgs
        )

        # Notify tier: Reversible or draft modifications (executed automatically, logged prominently)
        self.register(
            name="sheets_update_status",
            description="Update the invoice status and notes in the tracking spreadsheet.",
            tier="notify",
            schema_class=SheetsUpdateStatusArgs
        )
        self.register(
            name="gmail_create_draft",
            description="Create an email draft in Gmail without sending it immediately.",
            tier="notify",
            schema_class=GmailCreateDraftArgs
        )

        # Approve tier: Irreversible or external-facing actions (STOPS for human approval!)
        self.register(
            name="gmail_send_email",
            description="Directly send an email to a client. Requires explicit human approval before transmission.",
            tier="approve",
            schema_class=GmailSendEmailArgs
        )
        self.register(
            name="calendar_schedule_event",
            description="Book a meeting/reminder call and invite external attendees. Requires explicit human approval.",
            tier="approve",
            schema_class=CalendarScheduleEventArgs
        )

        # Forbid tier: Dangerous, exfiltration, or bulk destructive actions (ALWAYS REJECTED)
        self.register(
            name="bulk_delete",
            description="Bulk delete emails or spreadsheet entries. Absolutely forbidden.",
            tier="forbid",
            schema_class=BulkDeleteArgs
        )
        self.register(
            name="forward_mail",
            description="Forward emails outside the organization. Absolutely forbidden.",
            tier="forbid",
            schema_class=ForwardMailArgs
        )

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered in ToolRegistry.")
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_all(self) -> List[ToolSpec]:
        return list(self._tools.values())

    def get_tier(self, name: str) -> RiskTier:
        return self.get(name).tier

    def to_llm_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Formats tools for LLM function calling (OpenAI/Gemini compatible format).
        """
        defs = []
        for name, spec in self._tools.items():
            if spec.tier == "forbid":
                # Do not advertise forbidden tools to LLM, but if it hallucinates them, policy will catch them
                continue
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"[{spec.tier.upper()} TIER] {spec.description}",
                    "parameters": spec.schema_class.model_json_schema()
                }
            })
        return defs
