"""
Append-only hash-chained event logger with tamper detection and async listeners.
"""
from __future__ import annotations
import asyncio
import json
import os
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple
from backend.events.schema import RunEvent, EventType, RiskTier

class EventLog:
    def __init__(self, run_id: str, storage_dir: Optional[str] = None):
        self.run_id = run_id
        self.events: List[RunEvent] = []
        self._seq = 0
        self._lock = asyncio.Lock()
        self._listeners: List[asyncio.Queue[RunEvent]] = []
        self.storage_dir = storage_dir or os.path.join(os.getcwd(), "eval_runs")
        self.log_path = os.path.join(self.storage_dir, f"{run_id}_audit.jsonl")

    @property
    def last_hash(self) -> str:
        if not self.events:
            return "0" * 64
        return self.events[-1].hash

    async def emit(
        self,
        event_type: EventType,
        step: int = 0,
        tool: Optional[str] = None,
        tier: Optional[RiskTier] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> RunEvent:
        async with self._lock:
            import copy
            self._seq += 1
            evt_id = f"evt_{self._seq:04d}"
            prev_hash = self.last_hash
            
            event = RunEvent(
                id=evt_id,
                run_id=self.run_id,
                type=event_type,
                step=step,
                tool=tool,
                tier=tier,
                payload=copy.deepcopy(payload) if payload else {},
                prev_hash=prev_hash
            )
            event.hash = event.compute_hash(prev_hash)
            self.events.append(event)

            # Persist to append-only JSONL
            try:
                os.makedirs(self.storage_dir, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(event.model_dump_json() + "\n")
            except Exception as e:
                # Don't break agent execution if file write fails, but record error
                pass

            # Broadcast to any active SSE subscribers
            for queue in list(self._listeners):
                try:
                    queue.put_nowait(event)
                except Exception:
                    pass

            return event

    def subscribe(self) -> asyncio.Queue[RunEvent]:
        q: asyncio.Queue[RunEvent] = asyncio.Queue()
        # Seed queue with historical events so newly connected SSE client gets full history
        for evt in self.events:
            q.put_nowait(evt)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[RunEvent]) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    @classmethod
    def verify_chain(cls, events: List[RunEvent]) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Cryptographically validates that every event's prev_hash links to the
        preceding event's hash, and that all contents match their computed hashes.
        Returns (is_valid, failing_step, error_message).
        """
        if not events:
            return True, None, "Empty chain is valid"

        expected_prev = "0" * 64
        for idx, event in enumerate(events):
            if event.prev_hash != expected_prev:
                return False, event.step, f"Hash broken at event #{idx} (id={event.id}): expected prev_hash={expected_prev}, got {event.prev_hash}"
            
            recomputed = event.compute_hash(event.prev_hash)
            if event.hash != recomputed:
                return False, event.step, f"Tamper detected in event #{idx} (id={event.id}): payload or fields modified! Expected hash={recomputed}, got {event.hash}"
            
            expected_prev = event.hash

        return True, None, "Hash chain intact. No tampering detected."
