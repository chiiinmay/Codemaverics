"""
Google Workspace & Synthetic World Seed Script.
Seeds test data for Invoices spreadsheet, Gmail threads, and Calendar events.
Can be executed against FakeWorld or live Google APIs (with credentials.json).
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.world.fake_world import FakeWorld

def seed():
    parser = argparse.ArgumentParser(description="Seed NUDGE Environment Data")
    parser.add_argument("--mode", choices=["fake", "google"], default="fake", help="Target environment")
    args = parser.parse_args()

    print(f"[*] Initializing seed data in mode: {args.mode}...")

    if args.mode == "fake":
        world = FakeWorld()
        state = world.get_state_snapshot()
        print(f"[+] FakeWorld seeded successfully:")
        print(f"    - Overdue Invoices: {len(state['invoices'])}")
        for inv in state['invoices']:
            print(f"      • {inv['row_id']}: {inv['client']} ({inv['email']}) - {inv['amount']} [{inv['status']}]")
        print(f"    - Gmail Threads: {len(state['thread_summaries'])}")
        print(f"    - Pre-existing Calendar Events: {len(state['calendar_events'])}")
    else:
        print("[*] Checking Google credentials.json...")
        if not os.path.exists("credentials.json"):
            print("[-] credentials.json not found in project root. Place your OAuth client secrets file to seed live Google Workspace.")
            return
        from backend.world.google_world import GoogleWorld
        gw = GoogleWorld()
        print(f"[+] Connected to Google API: {gw.get_state_snapshot()}")

if __name__ == "__main__":
    seed()
