"""Generate synthetic product-adoption telemetry for the Revela 15 accounts.

Output: account_feature_adoption_daily.csv
- 60 days of daily rows per account
- Patterns aligned with each account's deal status from the Revela CSV:
    healthy   -> Stackflow, Vantage, Brightfield, Summit, Redstone
    stalling  -> Meridian, Axiom (in-negotiation but legal pause)
    declining -> Orbit, Cascade, Denova, Northgate
    customer  -> TechNova, Luminary (stable post-sale)
    trail_off -> Fenix, Peregrine (lost; usage fell off in last weeks)

The killer demo question — 'accounts whose adoption dropped >30% in last 30
days' — should return the declining + trail_off groups, which is also where
deal commentary in transcripts shows the most signal.
"""

import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

ACCOUNTS = [
    ("14829371001", "Meridian Health", "stalling"),
    ("14829371002", "Stackflow", "healthy"),
    ("14829371003", "Denova Retail", "declining"),
    ("14829371004", "Vantage Logistics", "healthy"),
    ("14829371005", "Fenix Corp", "trail_off"),
    ("14829371006", "Orbit SaaS", "declining"),
    ("14829371007", "TechNova Systems", "customer"),
    ("14829371008", "Brightfield Media", "healthy"),
    ("14829371009", "Cascade Energy", "declining"),
    ("14829371010", "Luminary Brands", "customer"),
    ("14829371011", "Redstone Capital", "healthy"),
    ("14829371012", "Axiom Healthcare", "stalling"),
    ("14829371013", "Northgate Systems", "declining"),
    ("14829371014", "Peregrine Tech", "trail_off"),
    ("14829371015", "Summit Analytics", "healthy"),
]

DAYS = 60
END = date(2026, 5, 12)
START = END - timedelta(days=DAYS - 1)


def base_for(pattern: str, account_size_seed: int) -> float:
    """Day-0 active-user baseline; larger accounts = higher base."""
    base = 40 + (account_size_seed % 7) * 12
    return base


def factor_for(pattern: str, day_idx: int) -> float:
    """Multiplier on the baseline for a given day_idx (0..DAYS-1)."""
    t = day_idx / (DAYS - 1)  # 0..1
    noise = 1 + random.uniform(-0.08, 0.08)
    if pattern == "healthy":
        return (0.85 + 0.30 * t) * noise
    if pattern == "customer":
        return (1.0 + 0.05 * math.sin(day_idx / 7)) * noise
    if pattern == "stalling":
        if t < 0.5:
            return (0.95 + 0.20 * t) * noise
        return (1.05 - 0.55 * (t - 0.5)) * noise
    if pattern == "declining":
        if t < 0.5:
            return (1.0 - 0.05 * t) * noise
        return (0.975 - 1.45 * (t - 0.5)) * noise
    if pattern == "trail_off":
        if t < 0.5:
            return (1.0 - 0.10 * t) * noise
        return max(0.05, (0.95 - 1.70 * (t - 0.5))) * noise
    return noise


def health_score(factor: float) -> int:
    return max(5, min(99, int(round(factor * 70))))


def main() -> None:
    out_path = Path(__file__).with_name("account_feature_adoption_daily.csv")
    rows: list[list[str | int]] = []
    for acct_id, name, pattern in ACCOUNTS:
        base = base_for(pattern, int(acct_id[-3:]))
        for day_idx in range(DAYS):
            d = START + timedelta(days=day_idx)
            factor = factor_for(pattern, day_idx)
            active_users = max(0, int(round(base * factor)))
            sessions = max(0, int(round(active_users * (2.4 + random.uniform(-0.3, 0.3)))))
            feature_a = max(0, int(round(sessions * 0.55 * random.uniform(0.9, 1.1))))
            feature_b = max(0, int(round(sessions * 0.30 * random.uniform(0.85, 1.15))))
            feature_c = max(0, int(round(sessions * 0.15 * random.uniform(0.7, 1.3))))
            rows.append(
                [
                    acct_id,
                    name,
                    d.isoformat(),
                    active_users,
                    sessions,
                    feature_a,
                    feature_b,
                    feature_c,
                    health_score(factor),
                ]
            )

    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "ACCOUNT_ID",
                "ACCOUNT_NAME",
                "EVENT_DATE",
                "ACTIVE_USERS",
                "SESSIONS",
                "FEATURE_A_USES",
                "FEATURE_B_USES",
                "FEATURE_C_USES",
                "EVALUATION_HEALTH_SCORE",
            ]
        )
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out_path}")

    # Quick sanity print: 30-day adoption delta per account.
    print("\n30-day adoption delta (last 30 vs prior 30, by account):")
    by_acct: dict[str, list[int]] = {}
    for r in rows:
        by_acct.setdefault(str(r[1]), []).append(int(r[3]))
    for name, users in by_acct.items():
        prior, recent = users[:30], users[30:]
        avg_prior = sum(prior) / len(prior)
        avg_recent = sum(recent) / len(recent)
        delta = (avg_recent - avg_prior) / avg_prior * 100
        print(f"  {name:20s} {avg_prior:6.1f} -> {avg_recent:6.1f}  ({delta:+.1f}%)")


if __name__ == "__main__":
    main()
