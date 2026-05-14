-- One-time Snowflake setup for the cross-system demo.
-- Run with: snow sql -c coco -f snowflake_setup.sql
-- Or paste into a Snowsight worksheet.

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE COMPUTE_WH;

CREATE DATABASE IF NOT EXISTS REVELA_DEMO;
CREATE SCHEMA   IF NOT EXISTS REVELA_DEMO.PRODUCT_ANALYTICS;
USE SCHEMA REVELA_DEMO.PRODUCT_ANALYTICS;

CREATE OR REPLACE TABLE ACCOUNT_FEATURE_ADOPTION_DAILY (
    account_id              STRING       NOT NULL,
    account_name            STRING       NOT NULL,
    event_date              DATE         NOT NULL,
    active_users            NUMBER(10,0) NOT NULL,
    sessions                NUMBER(10,0) NOT NULL,
    feature_a_uses          NUMBER(10,0) NOT NULL,
    feature_b_uses          NUMBER(10,0) NOT NULL,
    feature_c_uses          NUMBER(10,0) NOT NULL,
    evaluation_health_score NUMBER(3,0)  NOT NULL
);

CREATE OR REPLACE STAGE REVELA_DEMO.PRODUCT_ANALYTICS.LOAD_STAGE
    FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1);

-- PUT runs from the snow CLI; in Snowsight upload via the UI instead.
-- PUT file:///.../account_feature_adoption_daily.csv @LOAD_STAGE OVERWRITE = TRUE;

COPY INTO ACCOUNT_FEATURE_ADOPTION_DAILY
  FROM @LOAD_STAGE/account_feature_adoption_daily.csv
  FILE_FORMAT = (TYPE = CSV FIELD_OPTIONALLY_ENCLOSED_BY = '"' SKIP_HEADER = 1)
  ON_ERROR = ABORT_STATEMENT;

-- Derived view: 30-day adoption delta per account. This is what the agent
-- (and Cortex Analyst) will query for the killer demo question.
CREATE OR REPLACE VIEW V_ACCOUNT_ADOPTION_30D AS
WITH windowed AS (
    SELECT
        account_id,
        account_name,
        AVG(CASE WHEN event_date >= DATEADD(day, -30, CURRENT_DATE())
                 THEN active_users END) AS avg_users_last_30d,
        AVG(CASE WHEN event_date <  DATEADD(day, -30, CURRENT_DATE())
                  AND event_date >= DATEADD(day, -60, CURRENT_DATE())
                 THEN active_users END) AS avg_users_prior_30d,
        AVG(CASE WHEN event_date >= DATEADD(day, -30, CURRENT_DATE())
                 THEN evaluation_health_score END) AS avg_health_last_30d
    FROM ACCOUNT_FEATURE_ADOPTION_DAILY
    GROUP BY account_id, account_name
)
SELECT
    account_id,
    account_name,
    ROUND(avg_users_last_30d, 1)  AS avg_active_users_last_30d,
    ROUND(avg_users_prior_30d, 1) AS avg_active_users_prior_30d,
    ROUND((avg_users_last_30d - avg_users_prior_30d) / NULLIF(avg_users_prior_30d, 0) * 100, 1)
        AS pct_change_30d,
    ROUND(avg_health_last_30d, 0) AS health_score_last_30d
FROM windowed
ORDER BY pct_change_30d ASC;

-- Sanity check.
SELECT * FROM V_ACCOUNT_ADOPTION_30D;
