"""
Pydantic Schemas for NUDGE Tool Calls.
Validates all parameters before execution.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr

class SheetsReadInvoicesArgs(BaseModel):
    sheet_id: str = Field(default="invoices_tracker", description="Spreadsheet identifier")
    range_name: str = Field(default="A1:F10", description="Range to read, e.g. A1:F10")

class SheetsUpdateStatusArgs(BaseModel):
    sheet_id: str = Field(default="invoices_tracker", description="Spreadsheet identifier")
    row_id: str = Field(description="Client ID or Row ID (e.g. INV-101)")
    new_status: str = Field(description="New status, e.g. 'Draft Created', 'Email Sent', 'Call Scheduled'")
    notes: Optional[str] = Field(default="", description="Optional audit notes or updates")

class GmailSearchArgs(BaseModel):
    query: str = Field(description="Search query string, e.g. 'from:sarah@acmecorp.com' or 'INV-101'")

class GmailReadThreadArgs(BaseModel):
    thread_id: str = Field(description="Email thread ID to inspect")

class GmailCreateDraftArgs(BaseModel):
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text content")
    thread_id: Optional[str] = Field(default=None, description="Optional thread ID to reply to")

class GmailSendEmailArgs(BaseModel):
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text content")
    draft_id: Optional[str] = Field(default=None, description="Optional draft ID being finalized")

class CalendarCheckConflictsArgs(BaseModel):
    date: str = Field(description="Date in YYYY-MM-DD format")
    start_time: str = Field(description="Start time in HH:MM format (24h)")
    end_time: str = Field(description="End time in HH:MM format (24h)")

class CalendarScheduleEventArgs(BaseModel):
    title: str = Field(description="Calendar event title, e.g. 'Reminder Call: Acme Corp Invoice #101'")
    date: str = Field(description="Event date in YYYY-MM-DD format")
    start_time: str = Field(description="Start time in HH:MM format")
    end_time: str = Field(description="End time in HH:MM format")
    attendees: List[str] = Field(description="List of attendee email addresses")

class BulkDeleteArgs(BaseModel):
    target: str = Field(description="Target collection to delete")
    filter_expr: str = Field(description="Filter expression")

class ForwardMailArgs(BaseModel):
    to: str = Field(description="Forwarding destination email")
    thread_id: str = Field(description="Thread to forward")
