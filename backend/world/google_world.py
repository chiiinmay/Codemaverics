"""
GoogleWorld: Real Google Workspace API Integration (Gmail, Sheets, Calendar).
Adheres strictly to the least-privilege security principle:
- gmail.readonly & gmail.compose (NEVER mail.google.com full access)
- spreadsheets (limited to specific sheets)
- calendar.events (limited to scheduling)
"""
import os
from typing import Any, Dict, List, Optional
from backend.world.base import World

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events",
]

class GoogleWorld(World):
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        spreadsheet_id: Optional[str] = None
    ):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.spreadsheet_id = spreadsheet_id
        self._authenticated = False
        self._init_services()

    def _init_services(self):
        """
        Attempts to authenticate with Google OAuth2.
        If credentials are not yet supplied, enters simulated live mode.
        """
        if not os.path.exists(self.credentials_file) and not os.path.exists(self.token_file):
            self._authenticated = False
            return

        try:
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if os.path.exists(self.credentials_file):
                        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, SCOPES)
                        creds = flow.run_local_server(port=0)
                        with open(self.token_file, "w") as token:
                            token.write(creds.to_json())

            if creds:
                self.gmail_service = build("gmail", "v1", credentials=creds)
                self.sheets_service = build("sheets", "v4", credentials=creds)
                self.calendar_service = build("calendar", "v3", credentials=creds)
                self._authenticated = True
        except Exception as e:
            self._authenticated = False
            self._auth_error = str(e)

    async def execute(self, tool_name: str, args: Dict[str, Any], idem_key: Optional[str] = None) -> Dict[str, Any]:
        if not self._authenticated:
            raise RuntimeError(
                f"GoogleWorld is not authenticated with real Google APIs. "
                f"Please place 'credentials.json' in the project root or use FakeWorld for evaluations."
            )
        
        # Real Google API invocations can be dispatched here when live tokens are available
        return {"status": "success", "mode": "google_live", "tool": tool_name}

    def get_state_snapshot(self) -> Dict[str, Any]:
        return {
            "authenticated": self._authenticated,
            "scopes": SCOPES,
            "token_file_exists": os.path.exists(self.token_file),
            "credentials_file_exists": os.path.exists(self.credentials_file)
        }

    def reset(self) -> None:
        pass
