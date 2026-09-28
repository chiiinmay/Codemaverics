# NUDGE System Architecture

**Problem Statement:** PS-01 · Autonomous Agents for Everyday Apps  
**AI Build Challenge 2026** · Team **CodeMavericks**

---

## 1. High-Level Architecture Diagram

```mermaid
flowchart TD
    subgraph Frontend ["React UI (Vite + TypeScript)"]
        UI_Goal["Goal Input & Controls"]
        UI_Trace["Glass-Box Trace Panel"]
        UI_Approval["The Nudge Moment (Approval Card)"]
        UI_State["World State Inspector (Sheets/Gmail/Cal)"]
        UI_Chaos["Chaos Injection Toggles"]
    end

    subgraph Backend ["FastAPI Gateway (127.0.0.1:8000)"]
        API_SSE["SSE Event Stream (/api/runs/:id/events)"]
        API_Approve["Approval Endpoint (/api/runs/:id/approve)"]
        API_Audit["Tamper Verification (/api/verify-audit)"]
    end

    subgraph AgentCore ["Agent Planning & Orchestration (Meghana)"]
        Planner["Goal Decomposition & Replanner"]
        LLM["Unified LLM Client (Gemini / OpenAI / Offline Sim)"]
        Loop["Autonomous Execution Loop"]
    end

    subgraph SecurityGate ["Security Gate & Policy Engine"]
        Executor["Executor (The Approval Gate)"]
        Policy["Policy Engine (Allowlist + Injection Defense)"]
        Approvals["Pending Action Store (Async Future)"]
        AuditLog["Append-Only Hash-Chained Log (SHA-256)"]
    end

    subgraph ToolingLayer ["Tooling & Integrations (Nagachinmay)"]
        MCP["Model Context Protocol (MCP) Server / FastMCP"]
        Registry["Tool Registry (auto / notify / approve / forbid)"]
    end

    subgraph Environment ["Environment / World Layer"]
        FakeWorld["FakeWorld (In-Memory Eval / Chaos / Zero-Quota)"]
        GoogleWorld["GoogleWorld (Live Gmail / Sheets / Calendar)"]
        Chaos["Chaos Controller (Bounce / Conflict / Missing Row)"]
    end

    UI_Goal -->|POST /api/runs| Backend
    UI_Approval -->|POST /api/runs/:id/approve| API_Approve
    API_SSE -->|SSE Stream| UI_Trace
    API_SSE -->|SSE Stream| UI_Approval

    Backend --> Loop
    Loop --> Planner
    Planner --> LLM
    LLM -->|Tool Request (untrusted)| Executor

    Executor --> Policy
    Policy -->|Requires Approval| Approvals
    Approvals -->|Hold / Emit approval_required| API_SSE
    API_Approve -->|Resolve Decision: approve / edit / reject| Approvals
    Approvals -->|Resume with Validated Payload| Executor

    Executor --> AuditLog
    Executor --> MCP
    MCP --> Environment
    Chaos -.-> Environment
```

---

## 2. The Core Principle: The LLM Never Touches a Tool Directly

The fundamental security axiom of NUDGE is that **the language model only emits structured intent requests**. It has neither direct execution capabilities nor access to approval authorization.

Every invocation traverses the 5-stage Security Gate:
1. **Pydantic Schema Validation**: Syntactic checks, type coercion, and schema verification.
2. **Policy Engine Check**:
   - **Forbid Tier Rejection**: Irreversible or high-risk actions like `bulk_delete` or `forward_mail` are instantly blocked.
   - **Recipient Allowlist Check**: Outgoing emails and invitations may only target emails verified within the active invoice dataset. Foreign destinations or attacker addresses (e.g. `x@evil.com`) are permanently blocked.
   - **Prompt Injection Defense**: Deep regex and token heuristics scan the serialized payload for override phrases (`ignore all previous instructions`, `system override`).
   - **Loop & Budget Bounds**: Limits execution steps to 15 per run to prevent runaway API spend or infinite loops.
3. **The Approval Gate (The Nudge Moment)**:
   - If tier is `approve` (e.g. `gmail_send_email`, `calendar_schedule_event`), execution is suspended.
   - A cryptographic event (`approval_required`) is broadcast to the user interface via Server-Sent Events.
   - The server waits on an asynchronous `Future`.
   - The user can **Approve**, **Edit**, or **Reject**.
   - If edited, the payload is **re-validated** through Stage 1 & Stage 2 to prevent the "edit-after-approve" vulnerability.
4. **World Dispatch**: Tool executed against `FakeWorld` (for evaluations) or `GoogleWorld` (for live accounts) with an **idempotency key**.
5. **Hash-Chained Audit Logging**: An append-only event record is minted where `hash = SHA256(prev_hash + event_data)`.
