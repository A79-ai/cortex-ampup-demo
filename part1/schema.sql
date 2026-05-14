-- Snowflake schema for the Sridhar demo (5–10 min, live, CLI).
--
-- Story: Ampup CRM × Snowflake's public-data Marketplace listing
-- (SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE), specifically the
-- COMPANY_EVENT_TRANSCRIPT_ATTRIBUTES table — 247K earnings-call
-- transcripts joinable to public companies in our pipeline.
--
-- The demo: coco joins CRM to recent earnings transcripts, reasons
-- over the unstructured text to extract sales-relevant signals
-- (data spend, AI strategy, hiring), then drafts AE briefings via
-- ampup MCP.
--
-- Why it lands for Sridhar:
--   - Marketplace = Snowflake's distribution story (one-click share)
--   - Earnings transcripts = Snowflake-scale unstructured data
--   - Coco/Cortex Code = Snowflake's agent product
--   - Ampup MCP = open-protocol action layer
--
-- Tables:
--   AMPUP_DEMO.AMPUP.accounts         — mirrored from ampup-staging
--   AMPUP_DEMO.AMPUP.opportunities    — mirrored, open deals only
--   AMPUP_DEMO.AMPUP.pipeline_with_earnings — the headline view
--
-- Cybersyn-derived dataset:
--   SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.COMPANY_INDEX
--   SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.COMPANY_EVENT_TRANSCRIPT_ATTRIBUTES

USE DATABASE AMPUP_DEMO;

CREATE SCHEMA IF NOT EXISTS AMPUP;
USE SCHEMA AMPUP;

CREATE OR REPLACE TABLE accounts (
    id              STRING NOT NULL PRIMARY KEY,
    name            STRING,
    name_normalized STRING,        -- lower(trim(name)), for join
    owner_id        STRING,
    owner_name      STRING,
    total_pipeline  NUMBER(18, 2),
    open_opps       NUMBER(10),
    synced_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE opportunities (
    id              STRING NOT NULL PRIMARY KEY,
    name            STRING,
    account_id      STRING,
    account_name    STRING,
    stage_label     STRING,
    amount          NUMBER(18, 2),
    close_date      DATE,
    owner_name      STRING,
    synced_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- ─────────────────────────────────────────────────────────────────
-- Manual ticker overrides for ampup-staging accounts.
--
-- We can't reliably name-match account names to COMPANY_INDEX
-- because COMPANY_INDEX has 2.9M companies including LLCs/funds with
-- similar names ("Uber" matches an insurance fund, not the rideshare).
-- So we map our 5 confirmed public-company prospects directly.
-- For real production this would be a CRM-side enrichment field.
-- ─────────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE account_ticker_overrides (
    account_name STRING NOT NULL PRIMARY KEY,
    ticker       STRING NOT NULL
);

INSERT INTO account_ticker_overrides VALUES
    ('Rivian',          'RIVN'),
    ('Intuit',          'INTU'),
    ('Uber',            'UBER'),
    ('VIAVI Solutions', 'VIAV'),
    ('Garmin Aviation', 'GRMN');

-- ─────────────────────────────────────────────────────────────────
-- The headline view. For each open opportunity whose account maps
-- to a public-company ticker, surface the most recent earnings
-- event with a transcript snippet. Coco selects this, then for
-- each row calls ampup MCP (propose_email_draft) to draft a Slack.
-- ─────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW pipeline_with_earnings AS
WITH latest_event AS (
    SELECT
        t.PRIMARY_TICKER,
        t.COMPANY_NAME      AS public_company_name,
        t.EVENT_TITLE,
        t.EVENT_TYPE,
        t.EVENT_TIMESTAMP,
        t.FISCAL_PERIOD,
        t.FISCAL_YEAR,
        t.TRANSCRIPT,
        ROW_NUMBER() OVER (
            PARTITION BY t.PRIMARY_TICKER
            ORDER BY t.EVENT_TIMESTAMP DESC
        ) AS rn
    FROM SNOWFLAKE_PUBLIC_DATA_FREE.PUBLIC_DATA_FREE.COMPANY_EVENT_TRANSCRIPT_ATTRIBUTES t
    WHERE t.PRIMARY_TICKER IN (SELECT ticker FROM account_ticker_overrides)
)
SELECT
    o.id                  AS opportunity_id,
    o.name                AS opportunity_name,
    o.account_name,
    o.amount              AS deal_amount,
    o.stage_label,
    o.owner_name,
    o.close_date,
    ov.ticker,
    le.public_company_name,
    le.EVENT_TITLE        AS latest_event,
    le.EVENT_TYPE         AS event_type,
    le.EVENT_TIMESTAMP    AS event_at,
    le.FISCAL_PERIOD || ' ' || le.FISCAL_YEAR AS fiscal_period,
    le.TRANSCRIPT         AS transcript_json
FROM opportunities o
JOIN account_ticker_overrides ov
    ON ov.account_name = o.account_name
LEFT JOIN latest_event le
    ON le.PRIMARY_TICKER = ov.ticker AND le.rn = 1
ORDER BY le.EVENT_TIMESTAMP DESC NULLS LAST;
