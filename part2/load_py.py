"""Push the synthetic adoption table to Snowflake via the Python connector.

Uses the [coco] block in ~/.snowflake/connections.toml.
"""

from __future__ import annotations

import csv
import tomllib
from pathlib import Path

import snowflake.connector

HERE = Path(__file__).parent
CSV_PATH = HERE / "account_feature_adoption_daily.csv"


def load_conn_args() -> dict[str, str]:
    cfg = tomllib.loads(Path.home().joinpath(".snowflake/connections.toml").read_text())
    block = cfg["coco"]
    args = {
        "account": block["account"],
        "user": block["user"],
        "warehouse": block["warehouse"],
        "role": block["role"],
    }
    auth = block.get("authenticator", "").upper()
    if auth == "PROGRAMMATIC_ACCESS_TOKEN":
        args["password"] = block["token"]
    elif "password" in block:
        args["password"] = block["password"]
    return args


DDL = """
CREATE DATABASE IF NOT EXISTS REVELA_DEMO;
CREATE SCHEMA IF NOT EXISTS REVELA_DEMO.PRODUCT_ANALYTICS;

CREATE OR REPLACE TABLE REVELA_DEMO.PRODUCT_ANALYTICS.ACCOUNT_FEATURE_ADOPTION_DAILY (
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
"""

VIEW_SQL = """
CREATE OR REPLACE VIEW REVELA_DEMO.PRODUCT_ANALYTICS.V_ACCOUNT_ADOPTION_30D AS
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
    FROM REVELA_DEMO.PRODUCT_ANALYTICS.ACCOUNT_FEATURE_ADOPTION_DAILY
    GROUP BY account_id, account_name
)
SELECT
    account_id,
    account_name,
    ROUND(avg_users_last_30d, 1)  AS avg_active_users_last_30d,
    ROUND(avg_users_prior_30d, 1) AS avg_active_users_prior_30d,
    ROUND((avg_users_last_30d - avg_users_prior_30d)
          / NULLIF(avg_users_prior_30d, 0) * 100, 1) AS pct_change_30d,
    ROUND(avg_health_last_30d, 0) AS health_score_last_30d
FROM windowed
ORDER BY pct_change_30d ASC;
"""


def main() -> None:
    rows: list[tuple] = []
    with CSV_PATH.open() as f:
        reader = csv.reader(f)
        next(reader)  # header
        for r in reader:
            rows.append(
                (r[0], r[1], r[2], int(r[3]), int(r[4]),
                 int(r[5]), int(r[6]), int(r[7]), int(r[8]))
            )
    print(f"loaded {len(rows)} rows from CSV")

    with snowflake.connector.connect(**load_conn_args()) as conn:
        cur = conn.cursor()
        for stmt in [s.strip() for s in DDL.split(";") if s.strip()]:
            cur.execute(stmt)
        cur.executemany(
            "INSERT INTO REVELA_DEMO.PRODUCT_ANALYTICS.ACCOUNT_FEATURE_ADOPTION_DAILY "
            "(account_id, account_name, event_date, active_users, sessions, "
            " feature_a_uses, feature_b_uses, feature_c_uses, evaluation_health_score) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
        print(f"inserted {cur.rowcount} rows")
        cur.execute(VIEW_SQL)
        cur.execute(
            "SELECT account_name, pct_change_30d "
            "FROM REVELA_DEMO.PRODUCT_ANALYTICS.V_ACCOUNT_ADOPTION_30D "
            "WHERE pct_change_30d < -30 ORDER BY pct_change_30d ASC"
        )
        print("\naccounts with >30% adoption drop:")
        for name, pct in cur.fetchall():
            print(f"  {name:25s} {pct:+.1f}%")


if __name__ == "__main__":
    main()
