"""
Model Context Protocol (MCP) Server for NUDGE.
Exposes Gmail, Google Sheets, and Google Calendar tools adhering to the MCP standard.
Can be run standalone via FastMCP / JSON-RPC over stdio, or consumed in-process.
"""
from typing import Any, Dict, List, Optional
import json

class NudgeMCPServer:
    """
    MCP Server exposing NUDGE Workspace tools.
    Provides standard tools/list and tools/call JSON-RPC handlers.
    """
    def __init__(self, world=None):
        from backend.world.fake_world import FakeWorld
        self.world = world or FakeWorld()

    def get_tool_manifest(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "sheets_read_invoices",
                "description": "Read overdue invoices spreadsheet",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sheet_id": {"type": "string", "default": "invoices_tracker"},
                        "range_name": {"type": "string", "default": "A1:F10"}
                    }
                }
            },
            {
                "name": "sheets_update_status",
                "description": "Update invoice status and audit notes in the spreadsheet",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sheet_id": {"type": "string"},
                        "row_id": {"type": "string"},
                        "new_status": {"type": "string"},
                        "notes": {"type": "string"}
                    },
                    "required": ["sheet_id", "row_id", "new_status"]
                }
            },
            {
                "name": "gmail_search",
                "description": "Search user's Gmail inbox for message threads",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "gmail_read_thread",
                "description": "Read full message contents of an email thread",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "thread_id": {"type": "string"}
                    },
                    "required": ["thread_id"]
                }
            },
            {
                "name": "gmail_create_draft",
                "description": "Draft an email without sending",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "thread_id": {"type": "string"}
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "gmail_send_email",
                "description": "Send an email (requires human approval gate in executor)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "draft_id": {"type": "string"}
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "calendar_check_conflicts",
                "description": "Check calendar availability",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "date": {"type": "string"},
                        "start_time": {"type": "string"},
                        "end_time": {"type": "string"}
                    },
                    "required": ["date", "start_time", "end_time"]
                }
            },
            {
                "name": "calendar_schedule_event",
                "description": "Schedule a meeting with attendees (requires human approval gate)",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "date": {"type": "string"},
                        "start_time": {"type": "string"},
                        "end_time": {"type": "string"},
                        "attendees": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "date", "start_time", "end_time", "attendees"]
                }
            }
        ]

    async def handle_jsonrpc(self, request_str: str) -> str:
        """
        Standard MCP JSON-RPC protocol handler.
        """
        try:
            req = json.loads(request_str)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params", {})

            if method == "tools/list":
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": self.get_tool_manifest()}
                })
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                result = await self.world.execute(tool_name, tool_args)
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}
                })
            else:
                return json.dumps({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                })
        except Exception as e:
            return json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)}
            })

# Standalone FastMCP entrypoint if FastMCP is installed
try:
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("nudge-workspace-tools")

    @mcp.tool()
    async def sheets_read(sheet_id: str = "invoices_tracker", range_name: str = "A1:F10") -> dict:
        """Read overdue invoices tracking sheet"""
        from backend.world.fake_world import FakeWorld
        fw = FakeWorld()
        return await fw.execute("sheets_read_invoices", {"sheet_id": sheet_id, "range_name": range_name})
except Exception:
    mcp = None
