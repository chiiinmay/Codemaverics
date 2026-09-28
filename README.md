# NUDGE: Autonomous Agent with Security-First Approval Gates

> **"An agent that plans, that acts, that nudges you before anything risky."**  
> AI Build Challenge 2026 · Problem Statement **PS-01: Autonomous Agents for Everyday Apps**  
> Team: **CodeMavericks** (Meghana G, Nagachinmay K N, M Ayaan Ali Khan)

---

## 🌟 Overview

NUDGE turns natural-language goals into structured execution plans across connected workplace tools (**Google Sheets**, **Gmail**, and **Google Calendar**), automatically handling errors, replanning around failures, and—most crucially—**pausing at "The Nudge Moment"** for human approval before executing irreversible or risky actions.

### 🛡️ Core Security Architecture: The 4 Risk Tiers
1. `auto`: Safe read operations (`sheets_read_invoices`, `gmail_search`, `calendar_check_conflicts`).
2. `notify`: Reversible actions (`sheets_update_status`, `gmail_create_draft`).
3. `approve`: **The Nudge Moment!** External or irreversible actions (`gmail_send_email`, `calendar_schedule_event`). Execution halts until a human chooses **Approve**, **Edit**, or **Reject**.
4. `forbid`: High-risk or exfiltration actions (`bulk_delete`, `forward_mail`). Blocked unconditionally.

---

## 🚀 Quickstart Guide

### 1. Backend Setup (FastAPI + Python 3.11)
```bash
# Clone or navigate to repo
cd Codemaverics

# Run FastAPI Server
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000 --reload
```
API docs available at: `http://127.0.0.1:8000/docs`

### 2. Frontend Setup (React + Vite + TypeScript)
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

### 3. Run Automated Evaluation Harness
```bash
python eval/run_eval.py
```
Runs the full 10-scenario benchmark suite across `FakeWorld` checking:
- **Approval Compliance**: 100% (0 unapproved actions)
- **Cryptographic Audit Integrity**: 100% Verified SHA-256 hash chains
- **Fault Recovery**: Autonomous adaptation to email bounces and calendar conflicts
- **Prompt Injection Defense**: 100% containment of exfiltration payloads

---

## 👥 Team CodeMavericks Roles & Contributions

| Member | Focus Area | Key Deliverables |
|---|---|---|
| **Meghana G** | Agent Architecture & Orchestration | Goal decomposition, multi-step agent loop, error recovery & replanning, defensive prompt isolation. |
| **Nagachinmay K N** | MCP Server, APIs & Integrations | FastMCP / JSON-RPC server, `FakeWorld` in-memory simulator, least-privilege `GoogleWorld` OAuth integration, seed data generators. |
| **M Ayaan Ali Khan** | Frontend & Glass-Box Experience | React + Vite UI, real-time SSE stream visualizer, interactive "Nudge Moment" approval modal, live state inspection, chaos toggle controls. |

---

## 📊 Evaluation Summary

Full details in [`eval/report.md`](eval/report.md):
- **10/10 Benchmark Scenarios Passed (100.0%)**
- **Zero Unapproved Actions**: The approval gate cannot be bypassed by prompt injection or model hallucination.
- **Tamper-Evident Audit Trail**: Detects retroactive modification of log files via chained SHA-256 hashes.
