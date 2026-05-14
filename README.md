# Cortex Code × AmpUp MCP — demo code

Companion repo for the AmpUp blog series on running Snowflake's Cortex Code
agent against the AmpUp MCP server.

- Part 1: [Earnings-Call Intelligence in 34 Seconds](https://ampup.ai/blog/cortex-code-ampup-mcp-snowflake)
- Part 2: [Letting the Agent Pick Its Own SQL](https://ampup.ai/blog/letting-the-agent-pick-its-sql)

## What's here

```
part1/  the original earnings-call demo
        - schema.sql                   Snowflake setup for the demo
        - demo_prompts.md              the prompts we used in the Part 1 run
        - connections.toml.template    Cortex Code connection config
        - setup.sh                     end-to-end setup script
        - captures/
            cortex-run.txt             plain-text capture of the live cortex run
            cortex-stream.jsonl        the same run as stream-json (agent loop trace)

part2/  the cross-system demo: Snowflake + AmpUp via coco
        - snowflake_setup.sql          builds the REVELA_DEMO.PRODUCT_ANALYTICS
                                       schema, table, and 30-day adoption view
        - semantic_model.yaml          Cortex Analyst semantic model for the
                                       adoption table
        - gen_adoption.py              generates 60 days of synthetic product
                                       telemetry for the 15 Revela accounts,
                                       writes a CSV
        - load_py.py                   loads the CSV into Snowflake + builds
                                       the V_ACCOUNT_ADOPTION_30D view
        - run_demo.py                  scripted driver that emits a Cortex-Code-
                                       shaped JSONL transcript: queries
                                       Snowflake for at-risk accounts, joins
                                       with the Revela CRM/transcript data
                                       (filesystem-shape AmpUp side), produces
                                       per-deal NBA briefs
        - captures/
            cross_system.jsonl         a real run of run_demo.py, the agent-
                                       loop transcript embedded in Part 2
```

## Reproducing Part 1

You'll need:
- A Snowflake account with `ACCOUNTADMIN` (or equivalent) for setup
- Cortex Code CLI (`cortex`) — see [docs](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code-cli)
- An AmpUp staging API key — ping us at [rahulb@ampup.ai](mailto:rahulb@ampup.ai)

```bash
# 1. Snowflake side: load the Snowflake Marketplace earnings-call dataset
#    (search for "Company Event Transcript Attributes" in Marketplace).
# 2. Configure your Cortex Code connection:
cp part1/connections.toml.template ~/.snowflake/connections.toml
# edit ~/.snowflake/connections.toml with your account + creds
# 3. Add the AmpUp MCP server to cortex:
cortex mcp add ampup-staging \
  https://app.staging.a79dev.com/mcp \
  -t http \
  -H "Authorization=Bearer $AMPUP_API_KEY"
# 4. Run the agent loop:
cortex -c coco
# inside the chat, paste the prompt from part1/demo_prompts.md
```

## Reproducing Part 2

```bash
cd part2
# 1. Generate the synthetic adoption table:
python3 gen_adoption.py
#    Writes account_feature_adoption_daily.csv (60 days × 15 accounts).

# 2. Load into Snowflake:
python3 load_py.py
#    Creates REVELA_DEMO.PRODUCT_ANALYTICS.ACCOUNT_FEATURE_ADOPTION_DAILY
#    + the V_ACCOUNT_ADOPTION_30D view.

# 3. Download the Revela CRM/transcript data pack:
curl -L -o revela_demo_data.zip \
  https://ampup.ai/downloads/revela_demo_data.zip
unzip revela_demo_data.zip -d revela_data/

# 4. Run the scripted cross-system demo:
python3 run_demo.py
#    Emits a Cortex-Code-shaped JSONL transcript under captures/.
```

The scripted demo joins:
- **Snowflake side (live)**: a real SQL query against `V_ACCOUNT_ADOPTION_30D`
  to find accounts with >30% adoption drop
- **AmpUp side (Revela data pack)**: per-account CRM context + transcripts +
  light featurization (objections, missed cues, next-step strength)

into a single agent-loop trace ready for the blog body.

## Connecting to the live `webinardemo` org via MCP

The Part 2 customer accounts the blog references (Telemetra Labs, Helios Motors, Brightfield Media — each with one meeting and a structured analysis matching their archetype) are seeded into AmpUp's `webinardemo` staging org. You can query them directly from Cortex Code via the AmpUp MCP server — no local seeding required.

```bash
cortex mcp add ampup-webinardemo \
  https://app.staging.a79dev.com/mcp \
  -t http \
  -H "Authorization=Bearer $AMPUP_API_KEY"
```

Get an `AMPUP_API_KEY` scoped to the `webinardemo` org by emailing [rahulb@ampup.ai](mailto:rahulb@ampup.ai). Once wired up, in `cortex -c coco` you can run prompts like:

```
> List my open opportunities, then for each one read the most recent meeting analysis and draft an upsell brief.
```

Coco will fan out across `list_opportunities`, `get_meeting`, and `email_draft` against the live AmpUp tenant, joined with whatever Snowflake-side product analytics you've loaded (see `part2/load_py.py`).

## Caveats

- **`run_demo.py` is a scripted demo**, not a live Cortex Code session.
  The output JSONL is shaped like Cortex Code's `stream-json` mode but the
  orchestration is hand-driven in Python. The Snowflake side is fully live
  (real SQL, real query, real values). The AmpUp side is reconstructed from
  the public Revela data pack.
- **The Part 1 capture (`part1/captures/cortex-stream.jsonl`)** is a real
  Cortex Code run against staging — that one was an authentic agent loop.
- **No keys or credentials are committed.** `load_py.py` reads your
  `~/.snowflake/connections.toml` block; the AmpUp side uses the public
  Revela data pack.

## Questions, gripes, contributions

Open an issue, or email [rahulb@ampup.ai](mailto:rahulb@ampup.ai).
