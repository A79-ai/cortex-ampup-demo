"""Seed the credits-surge upsell demo into an AmpUp staging org.

Creates three accounts, one meeting per account, and a meeting analysis for
each. The analyses are crafted to match three upsell archetypes:

  - Telemetra Labs    budget-sensitive   -> credit-commit pitch
  - Helios Motors     expansion-ready    -> enterprise + reserved capacity
  - Brightfield Media procurement-friend -> annual commit + true-up

Usage:
  export AMPUP_API_KEY=sk-a79-...
  export AMPUP_BASE=https://app.staging.a79dev.com   # or your own host
  python3 seed_webinardemo.py

Idempotency:
  Accounts are looked up by name first. If one already exists, the script
  reuses the existing record instead of creating a duplicate. Meetings are
  created fresh on each run; rerun if you need a clean reset (delete the old
  meetings via the UI first).
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

BASE = os.environ.get("AMPUP_BASE", "https://app.staging.a79dev.com").rstrip("/")
KEY = os.environ.get("AMPUP_API_KEY")
if not KEY:
    sys.exit("AMPUP_API_KEY not set")

API = f"{BASE}/sales-agents/api/v1"
HDRS = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}


@dataclass
class Seed:
    name: str
    industry: str
    archetype: str
    meeting_name: str
    meeting_days_ago: int
    transcript_summary: str
    objections: list[dict]
    next_step_signals: list[str]
    upsell_recommendation: str


SEEDS = [
    Seed(
        name="Telemetra Labs",
        industry="Developer Tools / AI Observability",
        archetype="budget-sensitive",
        meeting_name="Telemetra Labs - Q3 planning review",
        meeting_days_ago=22,
        transcript_summary=(
            "VP Eng raised Q3 margin concerns. Current overage costs are "
            "unpredictable - last month was 2.3x baseline because of the "
            "production rollout. Asked specifically: 'is there a way to "
            "lock in cost? our CFO is asking why our infra line is moving "
            "around so much.' Open to a commit-based plan if it carries a "
            "discount over on-demand. No competitor mentioned. Champion "
            "engaged, wants something to share with finance this week."
        ),
        objections=[
            {
                "kind": "pricing_predictability",
                "excerpt": "current overage costs are unpredictable, our CFO is asking why our infra line is moving around so much",
            },
            {
                "kind": "budget_pressure",
                "excerpt": "last month was 2.3x baseline because of the production rollout",
            },
        ],
        next_step_signals=[
            "Champion explicitly asked for commit-based pricing options",
            "Wants something to share with finance this week",
        ],
        upsell_recommendation=(
            "Pitch credit-commit plan. Offer 20% discount on committed "
            "spend at projected Q3 volume. Frame as predictability + savings, "
            "not as a contract lock-in. Send pricing one-pager today."
        ),
    ),
    Seed(
        name="Helios Motors",
        industry="Automotive / Autonomous Driving AI",
        archetype="expansion-ready",
        meeting_name="Helios Motors - 2026 roadmap and infra plan",
        meeting_days_ago=12,
        transcript_summary=(
            "Atlas-1 silicon launches late 2026. Head of ML Infra walked "
            "through capacity needs: Gen 3 training pipelines will need "
            "around 10x current compute by Q4 next year. They are already "
            "running near peak on the current plan. Engineering wants "
            "reserved capacity guarantees, plus a named TAM for the "
            "rollout. Budget signal: AI/autonomy is core capital allocation "
            "for the next 18 months, no spending ceiling discussed. Champion "
            "is the VP of ML Platform; willing to introduce CFO."
        ),
        objections=[
            {
                "kind": "capacity_guarantee",
                "excerpt": "Gen 3 training pipelines will need around 10x current compute by Q4 next year, we are already running near peak",
            },
        ],
        next_step_signals=[
            "Asked for reserved-capacity guarantees",
            "Asked for a named technical account manager",
            "Champion offered to introduce CFO",
        ],
        upsell_recommendation=(
            "Pitch enterprise plan with reserved capacity. Negotiate "
            "multi-year commit aligned to the Atlas-1 ramp. Bring named TAM "
            "to the CFO intro call. This is the strongest expansion signal "
            "in the pipeline this quarter."
        ),
    ),
    Seed(
        name="Brightfield Media",
        industry="Media / Streaming",
        archetype="procurement-friendly",
        meeting_name="Brightfield Media - POC review and FY budget",
        meeting_days_ago=29,
        transcript_summary=(
            "Content-personalization pipeline went live last month, usage "
            "jumped 2.8x. CFO joined the back half of the call. Direct quote: "
            "'I need predictable annual billing for board reporting; the "
            "current month-by-month variability is causing forecasting "
            "problems.' Head of RevOps (champion) backed up the request. "
            "They want an annual commitment with a true-up mechanism for "
            "overages so the line item is predictable in their FY26 plan. "
            "No price sensitivity raised. Procurement is the gating concern, "
            "not cost."
        ),
        objections=[
            {
                "kind": "billing_predictability",
                "excerpt": "I need predictable annual billing for board reporting, the current month-by-month variability is causing forecasting problems",
            },
        ],
        next_step_signals=[
            "Explicitly asked for annual billing structure",
            "Champion and CFO aligned on the same request",
            "FY26 planning cycle is the deadline",
        ],
        upsell_recommendation=(
            "Pitch annual credit-commit with quarterly true-up. Frame the "
            "annual line as 'predictable FY26 budget line for the board.' "
            "Position the quarterly true-up as a safety valve, not a "
            "loophole. Get a redlined order form to procurement before "
            "month-end so it lands in their FY planning window."
        ),
    ),
]


def get_or_create_account(seed: Seed) -> str:
    r = requests.get(
        f"{API}/accounts",
        headers=HDRS,
        params={"limit": 20, "search": seed.name},
        timeout=15,
    )
    r.raise_for_status()
    items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    for a in items:
        if a.get("name", "").lower() == seed.name.lower():
            return a["id"]

    r = requests.post(
        f"{API}/accounts",
        headers=HDRS,
        json={"name": seed.name, "industry": seed.industry},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def create_meeting(seed: Seed, account_id: str) -> str:
    scheduled_at = (datetime.now(timezone.utc) - timedelta(days=seed.meeting_days_ago)).isoformat()
    r = requests.post(
        f"{API}/meetings",
        headers=HDRS,
        json={
            "name": seed.meeting_name,
            "account_id": account_id,
            "scheduled_at": scheduled_at,
            "status": "analyzed",
            "source": "seed_script",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def attach_analysis(seed: Seed, meeting_id: str) -> None:
    payload = {
        "summary": seed.transcript_summary,
        "archetype": seed.archetype,
        "objections": seed.objections,
        "next_step_signals": seed.next_step_signals,
        "upsell_recommendation": seed.upsell_recommendation,
    }
    r = requests.post(
        f"{API}/meetings/{meeting_id}/analysis",
        headers=HDRS,
        json=payload,
        timeout=30,
    )
    r.raise_for_status()


def main() -> None:
    print(f"seeding into {BASE}")
    for seed in SEEDS:
        print(f"\n[{seed.archetype}] {seed.name}")
        acct_id = get_or_create_account(seed)
        print(f"  account_id: {acct_id}")
        meeting_id = create_meeting(seed, acct_id)
        print(f"  meeting_id: {meeting_id}")
        try:
            attach_analysis(seed, meeting_id)
            print("  analysis attached")
        except requests.HTTPError as e:
            print(f"  analysis endpoint unavailable ({e.response.status_code})")
            print("  payload prepared for manual attach:")
            print(json.dumps(payload_for(seed), indent=2))
        time.sleep(0.5)
    print("\ndone.")


def payload_for(seed: Seed) -> dict:
    return {
        "summary": seed.transcript_summary,
        "archetype": seed.archetype,
        "objections": seed.objections,
        "next_step_signals": seed.next_step_signals,
        "upsell_recommendation": seed.upsell_recommendation,
    }


if __name__ == "__main__":
    main()
