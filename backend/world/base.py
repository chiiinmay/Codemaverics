"""
Base Environment Interface for NUDGE Worlds (FakeWorld and GoogleWorld).
Ensures the Agent loop code is 100% agnostic to whether it is running
against real Google Workspace APIs or an in-memory test simulator.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class World(ABC):
    @abstractmethod
    async def execute(self, tool_name: str, args: Dict[str, Any], idem_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a validated tool request within the world.
        """
        pass

    @abstractmethod
    def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Returns a snapshot of the current state of Invoices, Gmail Inbox, and Calendar.
        Used by the UI glass-box state viewer and eval harness assertions.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """
        Resets the world to standard seed state.
        """
        pass
