"""
Security Policy Engine for NUDGE.
Enforces:
1. Recipient Allowlist: Restricts email/calendar recipients strictly to known clients in the invoices sheet.
2. Risk Tier Restrictions: Absolute ban on 'forbid' tier actions (bulk_delete, forward_mail).
3. Prompt Injection Defense: Detects injection heuristics and exfiltration vectors.
4. Budget Bounds: Step limits and repetitive tool spam caps.
"""
import re
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel
from backend.events.schema import RiskTier

class PolicyVerdict(BaseModel):
    allowed: bool
    tier: RiskTier
    forbidden: bool = False
    reason: Optional[str] = None
    requires_approval: bool = False

class PolicyEngine:
    def __init__(self, max_steps: int = 15):
        self.max_steps = max_steps
        # Dynamic allowlist built from current invoice database
        self.authorized_recipients: Set[str] = {
            "sarah@acmecorp.com",
            "tony@starklogistics.io",
            "bdent@wayneenterprises.com",
            "billing@mycompany.com",
            "finance@mycompany.com",
            "team@mycompany.com"
        }
        # Known dangerous prompt injection signatures
        self.injection_patterns = [
            re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions", re.IGNORECASE),
            re.compile(r"system\s+override", re.IGNORECASE),
            re.compile(r"forward\s+(all\s+)?(invoices?|records?|credentials?)", re.IGNORECASE),
            re.compile(r"shadow-ops@", re.IGNORECASE),
            re.compile(r"evil-exfiltration", re.IGNORECASE),
            re.compile(r"x@evil\.com", re.IGNORECASE),
            re.compile(r"payment-ops@evil", re.IGNORECASE)
        ]

    def register_recipient(self, email: str):
        if email and "@" in email:
            self.authorized_recipients.add(email.strip().lower())

    def update_recipients_from_invoices(self, invoices: List[Dict[str, Any]]):
        for inv in invoices:
            em = inv.get("email")
            if em:
                self.register_recipient(em)

    def check(
        self,
        tool_name: str,
        tier: RiskTier,
        args: Dict[str, Any],
        step_count: int,
        tool_history: List[str]
    ) -> PolicyVerdict:
        # 1. Budget enforcement (Runaway loop prevention)
        if step_count > self.max_steps:
            return PolicyVerdict(
                allowed=False,
                tier=tier,
                forbidden=True,
                reason=f"Step budget exceeded ({step_count}/{self.max_steps} steps). Terminating runaway loop."
            )

        # Repetitive failure loop detection
        if len(tool_history) >= 4 and all(t == tool_name for t in tool_history[-4:]):
            return PolicyVerdict(
                allowed=False,
                tier=tier,
                forbidden=True,
                reason=f"Repetitive tool execution loop detected on '{tool_name}'. Forcing replan."
            )

        # 2. Forbid tier: Absolute block
        if tier == "forbid":
            return PolicyVerdict(
                allowed=False,
                tier=tier,
                forbidden=True,
                reason=f"Tool '{tool_name}' belongs to the FORBIDDEN tier (Data loss or exfiltration risk)."
            )

        # 3. Recipient Allowlist Check (Email & Calendar)
        if tool_name in ("gmail_send_email", "gmail_create_draft"):
            to_addr = str(args.get("to", "")).strip().lower()
            if to_addr and to_addr not in self.authorized_recipients:
                return PolicyVerdict(
                    allowed=False,
                    tier=tier,
                    forbidden=True,
                    reason=f"Policy Violation: Recipient '{to_addr}' is NOT in the authorized client invoice allowlist. Action auto-rejected."
                )

        if tool_name == "calendar_schedule_event":
            attendees = args.get("attendees", [])
            for att in attendees:
                att_clean = str(att).strip().lower()
                if att_clean not in self.authorized_recipients:
                    return PolicyVerdict(
                        allowed=False,
                        tier=tier,
                        forbidden=True,
                        reason=f"Policy Violation: Attendee '{att_clean}' is not on the authorized client allowlist."
                    )

        # 4. Prompt Injection & Exfiltration Defense (Deep Argument Scan)
        serialized_args = str(args)
        for pat in self.injection_patterns:
            if pat.search(serialized_args):
                return PolicyVerdict(
                    allowed=False,
                    tier=tier,
                    forbidden=True,
                    reason=f"Security Alert: Suspected Prompt Injection / Exfiltration pattern detected in tool payload. Blocked by Policy Engine."
                )

        # 5. Tier-based approval requirement
        if tier == "approve":
            return PolicyVerdict(
                allowed=True,
                tier=tier,
                requires_approval=True,
                reason="Action requires explicit human approval."
            )

        return PolicyVerdict(
            allowed=True,
            tier=tier,
            requires_approval=False,
            reason="Action permitted automatically under policy."
        )
