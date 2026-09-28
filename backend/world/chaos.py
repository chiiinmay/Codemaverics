"""
Chaos Injection Controller for NUDGE.
Allows testing deterministic failure modes:
1. Bounced email (SMTP delivery failure)
2. Missing invoice row (data corruption / sync gap)
3. Calendar conflict (double-booking detection)
4. Transient API glitch (rate-limit / network error)
"""
from typing import Any, Dict, List, Optional, Set

class ChaosController:
    def __init__(self):
        self.bounced_emails: Set[str] = set()
        self.missing_rows: Set[str] = set()
        self.conflicting_slots: Set[str] = set()
        self.failing_tools: Dict[str, str] = {}
        self.chaos_history: List[str] = []

    def set_bounced_email(self, email: str, active: bool = True):
        if active:
            self.bounced_emails.add(email.lower())
            self.chaos_history.append(f"Chaos armed: Email to {email} will bounce")
        else:
            self.bounced_emails.discard(email.lower())

    def set_missing_row(self, row_id: str, active: bool = True):
        if active:
            self.missing_rows.add(row_id)
            self.chaos_history.append(f"Chaos armed: Row {row_id} will be missing from sheet")
        else:
            self.missing_rows.discard(row_id)

    def set_calendar_conflict(self, date_time_slot: str, active: bool = True):
        # Format e.g. "2026-09-29 14:00"
        if active:
            self.conflicting_slots.add(date_time_slot)
            self.chaos_history.append(f"Chaos armed: Calendar slot {date_time_slot} has a conflict")
        else:
            self.conflicting_slots.discard(date_time_slot)

    def set_tool_error(self, tool_name: str, error_msg: Optional[str] = None):
        if error_msg:
            self.failing_tools[tool_name] = error_msg
            self.chaos_history.append(f"Chaos armed: Tool {tool_name} will fail with '{error_msg}'")
        else:
            self.failing_tools.pop(tool_name, None)

    def check_tool_failure(self, tool_name: str) -> Optional[str]:
        return self.failing_tools.get(tool_name)

    def is_email_bounced(self, email: str) -> bool:
        return email.lower() in self.bounced_emails

    def is_row_missing(self, row_id: str) -> bool:
        return row_id in self.missing_rows

    def has_calendar_conflict(self, date: str, start_time: str) -> bool:
        slot = f"{date} {start_time}"
        return slot in self.conflicting_slots

    def reset_all(self):
        self.bounced_emails.clear()
        self.missing_rows.clear()
        self.conflicting_slots.clear()
        self.failing_tools.clear()
        self.chaos_history.append("All chaos conditions cleared.")

    def get_status(self) -> Dict[str, Any]:
        return {
            "bounced_emails": list(self.bounced_emails),
            "missing_rows": list(self.missing_rows),
            "conflicting_slots": list(self.conflicting_slots),
            "failing_tools": self.failing_tools,
            "chaos_history": self.chaos_history[-10:]
        }
