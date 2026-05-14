# Demo prompts for the Sridhar meeting

**Time slot: 5–10 min, live, CLI (`cortex -c coco`).**
**Goal: impress, no hard CTA.**

The story: ampup CRM × Snowflake's free Marketplace dataset (247K
public-company earnings transcripts) — joined live, summarized by
coco, action drafted via ampup MCP. Snowflake provides the data
(structured + unstructured), coco runs the agent, MCP is the open
action layer.

## The headline prompt

Paste verbatim:

> I'm an Ampup AE. My open pipeline includes deals with Rivian,
> Intuit, Uber, VIAVI Solutions, and Garmin. I want to walk into my
> next call with each of these prepared.
>
> Run a SELECT on `AMPUP_DEMO.AMPUP.pipeline_with_earnings` to get
> the top 5 deals by amount, along with the most recent earnings call
> for each. The TRANSCRIPT_JSON column has full speaker-annotated text.
>
> For each deal: read the first ~3000 chars of the transcript, extract
> what the company said about (a) AI strategy, (b) data infrastructure
> spend, (c) hiring growth. Write a 2-sentence sales angle.
>
> Then call ampup-staging MCP `propose_email_draft` to draft a Slack
> nudge for the AE — subject = deal name, body = the sales angle.
> Show me each draft. Do NOT send.

What coco does:

1. **SELECT** on `pipeline_with_earnings` — joins ampup CRM to Snowflake
   Marketplace data live. Returns 5–7 rows with embedded transcripts.
2. **Reasoning over unstructured data** — for each transcript, picks
   out signals an AE would care about. (Snowflake's Cortex `COMPLETE`
   isn't available on trial accounts, so coco's own LLM does this —
   *which is fine, since coco IS Cortex Code*.)
3. **Calls ampup-staging MCP** `propose_email_draft` 5×.
4. **Renders 5 drafts** in the terminal.

Total time including network round-trips: **~45–60s.**

## Talk track (live, you say this on top of the demo)

| Beat | What you say | What's on screen |
|------|--------------|------------------|
| 0:00 | "Ampup is an AI sales platform. Our agent — built on MCP — runs anywhere agents run. Today: Cortex Code." | `cortex` splash, `mcp list` shows ampup-staging |
| 0:20 | "I've connected coco to a Snowflake account where I installed the free Public Data product from your Marketplace — 247,000 earnings call transcripts, plus 2.9M companies." | `SHOW SHARES` or schema briefly |
| 0:40 | "Here's an AE's question I want to answer: *I'm walking into 5 deals next week. What did each of these public companies just tell Wall Street about their priorities?*" | Paste the prompt |
| 1:00 | (Coco runs SELECT) "That's a join in Snowflake — my CRM cross product with the public earnings dataset. The agent gets back 5 rows with embedded transcripts." | SQL result table |
| 1:30 | (Coco reasons over transcripts) "Now coco's reading the unstructured text — what did Rivian's CEO say at AI and Autonomy Day? What did Intuit's CFO say at the AGM? — and pulling out a sales angle." | Reasoning streams |
| 2:30 | (Coco calls MCP) "Ampup's MCP server has 147 tools. Coco picks `propose_email_draft` and drafts a personalized Slack for each AE." | MCP tool calls |
| 3:00 | "Five briefings, ready to send. The whole loop — analytic question, unstructured-data reasoning, sales action — runs through Cortex Code on Snowflake." | Drafts on screen |
| 3:30 | (Optional close) "What's interesting to us: Snowflake stops being just storage. With Cortex Code as the agent and MCP as the action layer, the warehouse becomes the substrate for any business workflow." | — |

## Recovery / fallback prompts

If something hangs mid-demo, fall back to one of these:

**B. SQL-only (skip MCP).** "Just show me the top 5 enriched deals
from `pipeline_with_earnings` with the event title and the first
500 chars of each transcript."

**C. MCP-only (skip Snowflake).** "List my 5 largest open
opportunities from the ampup-staging MCP and tell me when each one's
next meeting is."

Both are <30s and prove the rest of the stack works.

## What NOT to show

- Cortex Analyst, Cortex Search — not configured (out of 48h scope).
- Cortex `COMPLETE`/`SUMMARIZE` — gated on trial accounts. *If asked:*
  "Coco does the inference here; on a paid account we'd push it into
  Snowflake Cortex for in-warehouse processing."
- The streamable-HTTP fix we shipped today — interesting but tangential.
- The 5-deal ticker overrides table — explain only if pressed: in
  production, CRM accounts have a `public_ticker` field set by the AE
  or by enrichment.

## Pre-demo checklist

- [ ] `~/.snowflake/connections.toml` has `[coco]` block with PAT
- [ ] Network policy `demo_open` is set as account default (`SHOW NETWORK POLICIES`)
- [ ] Resource monitor `demo_cap` is on `COMPUTE_WH` (10 credits)
- [ ] `SNOWFLAKE_PUBLIC_DATA_FREE` share is installed
- [ ] `SELECT COUNT(*) FROM AMPUP_DEMO.AMPUP.pipeline_with_earnings` returns ≥5
- [ ] `cortex mcp list` shows ampup-staging (~147 tools, http transport)
- [ ] Practice run #1 timed — target the prompt under 90s
- [ ] Practice run #2 — interrupt yourself at every 30s mark to talk
- [ ] Terminal font size bumped (no squinting from the audience)
- [ ] Network: tether to phone if conference WiFi is risky

## Cost / data sanity

- Data uploaded to Snowflake: **<1 MB** (20 accounts + 20 opportunities + 5-row override table)
- Marketplace shares: **0 bytes uploaded** (read in place)
- Resource monitor cap: **10 credits/month** (~$30 if XS WH runs full-time, irrelevant for our demo)
- Per demo run compute: **~5–10 cents** of XS warehouse time
- Trial budget: $400. Margin is enormous.
