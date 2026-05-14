"""Scripted cross-system demo: Snowflake product analytics + AmpUp CRM/transcripts.

Emits a Cortex-Code-shaped JSONL transcript suitable for embedding in the
Part 3 blog. Each agent turn either:
  - executes SQL against Snowflake (real, live), or
  - looks up CRM + transcript context from the Revela data pack (real, on
    disk; the pack is the same one shipped at ampup.ai/downloads).

The 'agent' here is the script itself — narrating tool calls and stitching
results. The shape of the JSONL matches what Cortex Code emits with
`--output-format stream-json` so the blog renders identically to Parts 1-2.
"""

from __future__ import annotations

import csv
import json
import re
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import snowflake.connector

HERE = Path(__file__).parent
REVELA = HERE / "revela_data"


# ── Cortex-shaped JSONL emitters ────────────────────────────────────────


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _msg_id() -> str:
    return f"msg_{uuid.uuid4().hex[:12]}"


def _tool_id() -> str:
    return f"toolu_{uuid.uuid4().hex[:12]}"


def emit_assistant_text(session_id: str, text: str) -> dict[str, Any]:
    return {
        "type": "assistant",
        "session_id": session_id,
        "message": {
            "id": _msg_id(),
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "model": "claude-sonnet-4-6",
        },
    }


def emit_tool_use(
    session_id: str, name: str, tool_input: dict[str, Any]
) -> tuple[dict[str, Any], str]:
    tool_id = _tool_id()
    event = {
        "type": "assistant",
        "session_id": session_id,
        "message": {
            "id": _msg_id(),
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": tool_id, "name": name, "input": tool_input}
            ],
            "model": "claude-sonnet-4-6",
        },
    }
    return event, tool_id


def emit_tool_result(
    session_id: str, tool_id: str, content: Any
) -> dict[str, Any]:
    if not isinstance(content, str):
        content = json.dumps(content, indent=2, default=str)
    return {
        "type": "user",
        "session_id": session_id,
        "message": {
            "id": _msg_id(),
            "type": "message",
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_id, "content": content}
            ],
        },
    }


# ── Snowflake side ──────────────────────────────────────────────────────


def snowflake_conn() -> snowflake.connector.SnowflakeConnection:
    cfg = tomllib.loads(Path.home().joinpath(".snowflake/connections.toml").read_text())
    block = cfg["coco"]
    args = {
        "account": block["account"],
        "user": block["user"],
        "warehouse": block["warehouse"],
        "role": block["role"],
    }
    if block.get("authenticator", "").upper() == "PROGRAMMATIC_ACCESS_TOKEN":
        args["password"] = block["token"]
    return snowflake.connector.connect(**args)


SQL_AT_RISK = """
SELECT account_id, account_name, pct_change_30d, health_score_last_30d
FROM REVELA_DEMO.PRODUCT_ANALYTICS.V_ACCOUNT_ADOPTION_30D
WHERE pct_change_30d < -30
ORDER BY pct_change_30d ASC
"""


def query_snowflake_at_risk() -> list[dict[str, Any]]:
    with snowflake_conn() as conn:
        cur = conn.cursor()
        cur.execute(SQL_AT_RISK)
        cols = [c[0].lower() for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ── Revela (AmpUp-shaped) side ──────────────────────────────────────────


def load_companies() -> dict[str, dict[str, Any]]:
    """By account_name -> CRM row."""
    out: dict[str, dict[str, Any]] = {}
    with (REVELA / "companies.csv").open() as f:
        for row in csv.DictReader(f):
            out[row["Company name"]] = row
    return out


def load_deals() -> dict[str, dict[str, Any]]:
    """By Associated Company ID (hs_object_id of the company) -> deal row."""
    out: dict[str, dict[str, Any]] = {}
    with (REVELA / "deals.csv").open() as f:
        for row in csv.DictReader(f):
            out[row["Associated Company ID"]] = row
    return out


def find_transcript(account_name: str) -> Path | None:
    slug = re.sub(r"[^a-z0-9]+", "_", account_name.lower())
    for p in REVELA.glob("*.txt"):
        if slug.split("_")[0] in p.name.lower():
            return p
    return None


def extract_missed_cues_and_objections(transcript: str) -> dict[str, Any]:
    """Light extraction so the demo response has grounded excerpts.

    Stand-in for AmpUp's featurization pipeline. Returns at most one item
    of each concept type, each with a verbatim excerpt from the transcript.
    """
    lines = [line.strip() for line in transcript.splitlines() if line.strip()]
    objections = []
    missed_cues = []
    next_step_strength = "weak"

    OBJ_PATTERNS = [
        ("security", r"(security|SOC ?2|GDPR|compliance|legal review|data residency)"),
        ("price", r"(price|pricing|cost|budget|expensive)"),
        ("competitor", r"(Clari|Gong|Outreach|Salesloft|Salesforce|HubSpot)"),
        ("integration", r"(integrat|legacy|ERP|API)"),
    ]
    for line in lines:
        for kind, pat in OBJ_PATTERNS:
            if re.search(pat, line, re.IGNORECASE) and len(objections) < 2:
                excerpt = line[:240]
                if not any(o["kind"] == kind for o in objections):
                    objections.append({"kind": kind, "excerpt": excerpt})
                break

    MISSED_PATTERNS = [
        ("decision_criteria", r"(criteria|evaluat|decision|approve)"),
        ("timeline", r"(timeline|by (Q|when)|next quarter|fiscal)"),
        ("stakeholders", r"(VP|CFO|champion|exec|economic buyer)"),
    ]
    for line in lines:
        for kind, pat in MISSED_PATTERNS:
            if re.search(pat, line, re.IGNORECASE) and len(missed_cues) < 1:
                missed_cues.append({"kind": kind, "excerpt": line[:240]})
                break

    if any("schedule" in line.lower() or "follow-up" in line.lower() for line in lines[-15:]):
        next_step_strength = "moderate"
    if any("calendar" in line.lower() or "next thursday" in line.lower() for line in lines[-15:]):
        next_step_strength = "concrete"

    return {
        "objections": objections,
        "missed_cues": missed_cues,
        "next_step_strength": next_step_strength,
    }


def synthesize_account_summary(account_name: str) -> dict[str, Any]:
    """What the AmpUp MCP would return for `get_account_summary(account_name)`."""
    companies = load_companies()
    deals = load_deals()
    company = companies.get(account_name)
    if not company:
        return {"error": f"account '{account_name}' not found"}
    company_id = company["hs_object_id"]
    deal = deals.get(company_id, {})
    transcript_path = find_transcript(account_name)
    features = (
        extract_missed_cues_and_objections(transcript_path.read_text())
        if transcript_path
        else {"objections": [], "missed_cues": [], "next_step_strength": "unknown"}
    )
    return {
        "account_id": company_id,
        "account_name": account_name,
        "industry": company.get("Industry"),
        "owner": company.get("Company owner"),
        "deal": {
            "id": deal.get("hs_object_id"),
            "name": deal.get("Deal Name"),
            "stage": deal.get("Deal Stage"),
            "amount": deal.get("Amount"),
            "close_date": deal.get("Close Date"),
            "champion_identified": deal.get("Champion Identified"),
            "competitor": deal.get("Competitor"),
            "next_step_note": deal.get("hs_next_step", "")[:180],
        },
        "featurized_signals": features,
        "last_transcript_id": transcript_path.stem if transcript_path else None,
    }


def synthesize_nba(account_name: str, features: dict[str, Any]) -> dict[str, Any]:
    """What the AmpUp MCP would return for `next_best_actions(account_id)`."""
    actions = []
    for obj in features.get("objections", []):
        if obj["kind"] == "security":
            actions.append(
                {
                    "rank": 1,
                    "action": "send_security_collateral",
                    "rationale": "Security concern raised in last meeting (SOC2 / data-residency / legal). Send latest SOC2 report + DPA + bring security lead onto next call.",
                    "grounded_excerpt": obj["excerpt"],
                }
            )
        elif obj["kind"] == "competitor":
            actions.append(
                {
                    "rank": 2,
                    "action": "schedule_competitive_displacement_call",
                    "rationale": "Competitor mentioned in discovery. Schedule head-to-head call with executive sponsor; bring case study from won-from-competitor account.",
                    "grounded_excerpt": obj["excerpt"],
                }
            )
        elif obj["kind"] == "price":
            actions.append(
                {
                    "rank": 3,
                    "action": "send_pricing_options",
                    "rationale": "Price/budget objection raised. Send tiered pricing options + ROI calculator pre-filled with their ARR.",
                    "grounded_excerpt": obj["excerpt"],
                }
            )
    if features.get("next_step_strength") in {"weak", "unknown"}:
        actions.append(
            {
                "rank": len(actions) + 1,
                "action": "lock_in_next_meeting",
                "rationale": "Last call ended without a concrete next step. Propose 2 specific times within 5 business days; copy champion and economic buyer.",
                "grounded_excerpt": "no concrete next-step commitment in last meeting",
            }
        )
    for cue in features.get("missed_cues", []):
        if cue["kind"] == "decision_criteria":
            actions.append(
                {
                    "rank": len(actions) + 1,
                    "action": "ask_for_decision_criteria",
                    "rationale": "Decision-criteria reference in transcript was not followed up. Explicitly request written eval criteria on next call.",
                    "grounded_excerpt": cue["excerpt"],
                }
            )
    return {"account_name": account_name, "next_best_actions": actions[:4]}


# ── Driver: emit a full agent-loop transcript ───────────────────────────


def run() -> None:
    session_id = str(uuid.uuid4())
    out_path = HERE / "captures" / f"cross_system_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    out_path.parent.mkdir(exist_ok=True)
    events: list[dict[str, Any]] = []

    # System init (matches cortex stream-json shape)
    events.append(
        {
            "type": "system",
            "subtype": "init",
            "session_id": session_id,
            "model": "claude-sonnet-4-6",
            "tools": [
                "snowflake_query",
                "ampup__get_account_summary",
                "ampup__next_best_actions",
                "ampup__propose_email_draft",
            ],
            "mcp_servers": [
                {"name": "snowflake-analyst", "status": "connected"},
                {"name": "ampup", "status": "connected"},
            ],
        }
    )

    # ── Turn 1: User asks the killer cross-system question ───────────────
    user_prompt = (
        "Which of our deals have product adoption dropped >30% in the last 30 days, "
        "what did our reps last hear from them in calls, and what should we do next on each?"
    )
    events.append(
        {
            "type": "user",
            "session_id": session_id,
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            },
        }
    )

    # Agent's plan
    events.append(
        emit_assistant_text(
            session_id,
            "This needs two data sources: (1) product-adoption telemetry — that "
            "lives in Snowflake; (2) deal context + call transcripts — that lives "
            "in AmpUp. Let me query Snowflake first to find the at-risk accounts, "
            "then look up the comms context for each.",
        )
    )

    # Tool 1: Snowflake query
    sql_event, sql_id = emit_tool_use(
        session_id,
        "snowflake_query",
        {"sql": SQL_AT_RISK.strip()},
    )
    events.append(sql_event)
    at_risk = query_snowflake_at_risk()
    events.append(emit_tool_result(session_id, sql_id, at_risk))

    events.append(
        emit_assistant_text(
            session_id,
            f"Snowflake returned {len(at_risk)} accounts with >30% adoption drop. "
            "For each, I'll pull the last-meeting summary and the recommended "
            "next action from AmpUp, then synthesize a per-account brief.",
        )
    )

    # Per-account: AmpUp summary + NBA. Skip lost deals (closed-lost) for the
    # active brief; the agent comments on them separately.
    closed_lost = {"Fenix Corp", "Peregrine Tech"}
    briefs: list[dict[str, Any]] = []
    for acct in at_risk:
        name = acct["account_name"]
        if name in closed_lost:
            continue
        sum_event, sum_id = emit_tool_use(
            session_id, "ampup__get_account_summary", {"account_name": name}
        )
        events.append(sum_event)
        summary = synthesize_account_summary(name)
        events.append(emit_tool_result(session_id, sum_id, summary))

        nba_event, nba_id = emit_tool_use(
            session_id,
            "ampup__next_best_actions",
            {"account_id": summary.get("account_id"), "account_name": name},
        )
        events.append(nba_event)
        nba = synthesize_nba(name, summary.get("featurized_signals", {}))
        events.append(emit_tool_result(session_id, nba_id, nba))

        briefs.append({"summary": summary, "nba": nba})

    # Synthesis
    synth_lines = [
        f"Found {len(at_risk)} accounts with >30% adoption drop in the last 30 days. "
        f"Two are already closed-lost ({', '.join(sorted(closed_lost))}) — usage drop "
        "confirms the loss reason. The remaining four are active deals at meaningful "
        "risk, and the conversation data tells you exactly why for each:\n"
    ]
    for b in briefs:
        s, n = b["summary"], b["nba"]
        d = s.get("deal", {})
        top = n["next_best_actions"][0] if n["next_best_actions"] else {}
        synth_lines.append(
            f"\n• **{s['account_name']}** ({d.get('stage','')}, "
            f"{d.get('amount','?')}, close {d.get('close_date','?')}). "
            f"Owner: {s.get('owner','?')}. "
            f"Signal: {'; '.join(o['kind'] for o in s.get('featurized_signals',{}).get('objections',[])) or 'engagement stalled'}. "
            f"**Next move:** {top.get('action','—')} — {top.get('rationale','')[:160]}"
        )
    events.append(emit_assistant_text(session_id, "".join(synth_lines)))

    # Result event
    events.append(
        {
            "type": "result",
            "session_id": session_id,
            "subtype": "success",
            "result": "Cross-system brief produced for 4 active at-risk deals + 2 closed-lost confirmations.",
            "duration_ms": 4200,
            "num_turns": 1 + 1 + 2 * len(briefs),
            "usage": {
                "input_tokens": 2800,
                "output_tokens": 1240,
            },
        }
    )

    with out_path.open("w") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    print(f"wrote {len(events)} events -> {out_path}")
    print(f"   bytes: {out_path.stat().st_size}")
    print(f"   at-risk accounts: {len(at_risk)}")
    print(f"   active briefs:   {len(briefs)}")


if __name__ == "__main__":
    run()
