#!/usr/bin/env bash
# Single-command setup for the Sridhar coco demo.
#
# What this does:
#   1. Verifies the 'coco' connection in ~/.snowflake/connections.toml
#   2. Installs Cybersyn share via SQL (falls back to manual step if blocked)
#   3. Creates AMPUP_DEMO database + AMPUP schema
#   4. Pulls accounts + opportunities from ampup-staging
#   5. Loads them into Snowflake
#   6. Reports Cybersyn join quality
#
# Prereqs:
#   - Snowflake trial account (https://signup.snowflake.com)
#   - ~/.snowflake/connections.toml with a [connections.coco] block
#     (see connections.toml.template)
#   - uv installed (https://docs.astral.sh/uv/)

set -euo pipefail

cd "$(dirname "$0")"

echo "── Step 1/5: verify connection 'coco' ──────────────────────────"
if [[ ! -f "$HOME/.snowflake/connections.toml" ]]; then
    echo "❌  ~/.snowflake/connections.toml not found."
    echo "    cp $(pwd)/connections.toml.template ~/.snowflake/connections.toml"
    echo "    then edit the 3 REPLACE_ME fields."
    exit 1
fi
if ! grep -q "^\[connections.coco\]" "$HOME/.snowflake/connections.toml"; then
    echo "❌  No [connections.coco] block in ~/.snowflake/connections.toml"
    exit 1
fi
if grep -q "REPLACE_ME" "$HOME/.snowflake/connections.toml"; then
    echo "❌  ~/.snowflake/connections.toml still has REPLACE_ME placeholders."
    exit 1
fi

# Use uv-managed venv so we don't pollute the system Python.
echo "── Step 2/5: ensure Python deps (uv) ───────────────────────────"
uv pip install --quiet snowflake-connector-python httpx

echo "── Step 3/5: test connection ───────────────────────────────────"
uv run python <<'PY'
import snowflake.connector
c = snowflake.connector.connect(connection_name="coco")
row = c.cursor().execute(
    "SELECT current_account(), current_user(), current_warehouse(), current_role()"
).fetchone()
print(f"  ✅ connected to account={row[0]} user={row[1]} wh={row[2]} role={row[3]}")
PY

echo "── Step 4/5: install Cybersyn share via SQL (best-effort) ──────"
uv run python <<'PY'
import snowflake.connector
c = snowflake.connector.connect(connection_name="coco")
cur = c.cursor()
# Cybersyn listings shifted to "Public" provider in 2024-2025; the exact
# share name varies. Try the well-known identifiers in priority order.
candidates = [
    # (database_name_to_create, share_identifier)
    ("CYBERSYN", "CYBERSYN_INC.CYBERSYN__PUBLIC_COMPANY_FACTS"),
    ("CYBERSYN", "CYBERSYN.CYBERSYN__PUBLIC_COMPANY_FACTS"),
    ("CYBERSYN", "CYBERSYN_FINANCIAL_DATA_ATLAS.CYBERSYN_FINANCIAL_DATA_ATLAS"),
]
installed = False
for db, share in candidates:
    try:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db} FROM SHARE {share}")
        print(f"  ✅ installed share {share} → {db}")
        installed = True
        break
    except snowflake.connector.errors.ProgrammingError as e:
        msg = str(e).splitlines()[0][:200]
        print(f"  ⏭  {share}: {msg}")
if not installed:
    print()
    print("  ⚠️  Could not auto-install Cybersyn share. Manual step:")
    print("     1. Open Snowsight → Data Products → Marketplace")
    print("     2. Search 'Cybersyn Public Company Facts' (or 'Financial & Economic Essentials')")
    print("     3. Click 'Get' → accept terms → database name 'CYBERSYN'")
    print()
    print("     Then re-run this script.")
    raise SystemExit(2)
PY

echo "── Step 5/5: hydrate ampup data + run the join ─────────────────"
uv run python hydrate.py --create

echo ""
echo "✅  Setup complete."
echo ""
echo "Next:"
echo "  ~/.local/bin/cortex -c coco"
echo "  # then paste the prompt from demo_prompts.md"
