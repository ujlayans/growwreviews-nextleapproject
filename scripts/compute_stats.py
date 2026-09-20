import csv
import json
import os
from datetime import date

SOURCE = "data/reviews_classified.csv"
OUT = "data/theme_stats.json"
HISTORY = "output/history.json"

THEMES = [
    "App Stability & Outages",
    "Order Execution Failures",
    "Withdrawals & Fund Transfers",
    "Customer Support",
    "Onboarding & KYC",
]

KEYWORDS = {
    "App Stability & Outages": [
        "crash", "crashes", "lag", "slow", "freeze", "hangs", "hang",
        "login", "sign in", "logout", "outage", "downtime", "stuck",
        "error", "not opening", "screen gone", "restart", "force close",
    ],
    "Order Execution Failures": [
        "buy", "sell", "order", "executed", "execute", "fail", "failed",
        "not executed", "position", "silver", "placed", "rejected",
        "not processed", "quantity", "stoploss", "stop loss",
    ],
    "Withdrawals & Fund Transfers": [
        "withdraw", "withdrawal", "payout", "money stuck", "translate",
        "transfer", "credited", "not credited", "refund", "settlement",
        "bank", "amount received", "deposit", "withdrawing",
    ],
    "Customer Support": [
        "support", "customer care", "ticket", "response", "reply",
        "unresponsive", "no response", "no reply", "compensation",
        "helpline", "service", "agent", "call", "email", "complaint",
        "chat", "unresolved",
    ],
    "Onboarding & KYC": [
        "kyc", "pan", "aadhaar", "aadhar", "verification", "signup",
        "sign up", "open account", "account", "freeze", "blocked",
        "re-kyc", "onboarding", "otp", "upgrade", "pending verification",
    ],
}


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mean(values):
    return round(sum(values) / len(values), 2)


def pick_quote(reviews, keywords):
    def has_keyword(r):
        text = r["text"].lower()
        return any(k in text for k in keywords)

    matched = [r for r in reviews if has_keyword(r)]
    pool = matched or reviews

    def key(r):
        words = len(r["text"].split())
        short = 0 if words < 25 else 1
        return (short, words)

    best = min(pool, key=key)
    text = best["text"]
    lowers = text.lower()
    positions = [lowers.find(k) for k in KEYWORDS[best["theme"]] if lowers.find(k) != -1]
    quote = text.strip()
    if positions:
        match = characters_from_positions(text, positions)
        if match:
            quote = match
    assert quote in text, "quote is not an exact substring of the review"
    return quote


def characters_from_positions(text, positions):
    pos = min(positions)
    start = text.rfind(".", 0, pos) + 1
    start = max(start, text.rfind("?", 0, pos) + 1, text.rfind("!", 0, pos) + 1)
    end = len(text)
    for sep in (".", "?", "!"):
        idx = text.find(sep, pos)
        if idx != -1:
            end = min(end, idx + 1)
    return text[start:end].strip()


def compute_stats(rows):
    total = len(rows)
    unclassified = sum(1 for r in rows if r["theme"] == "Unclassified")
    dates = [r["date"] for r in rows]

    stats = {}
    for theme in THEMES:
        group = [r for r in rows if r["theme"] == theme]
        if not group:
            continue
        ratings = [int(r["rating"]) for r in group]
        avg_rating = mean(ratings)
        severity = round(6 - avg_rating, 2)
        priority_score = round(len(group) * severity, 2)
        stats[theme] = {
            "theme": theme,
            "count": len(group),
            "avg_rating": avg_rating,
            "severity": severity,
            "priority_score": priority_score,
            "wow_change": None,
            "quote": pick_quote(group, KEYWORDS[theme]),
        }
    return stats, total, unclassified, dates


def load_history():
    if not os.path.exists(HISTORY):
        return None, "first run -- no prior week to compare"
    with open(HISTORY) as f:
        data = json.load(f)
    return data.get("counts", {}), None


def apply_wow(stats, last_counts):
    for theme in stats:
        if last_counts is not None:
            stats[theme]["wow_change"] = stats[theme]["count"] - last_counts.get(theme, 0)


def write_history(stats, today):
    with open(HISTORY, "w") as f:
        json.dump(
            {"generated_at": today, "counts": {t: s["count"] for t, s in stats.items()}},
            f,
            indent=2,
        )


def main():
    rows = load_rows(SOURCE)
    stats, total, unclassified, dates = compute_stats(rows)
    last_counts, note = load_history()
    apply_wow(stats, last_counts)
    write_history(stats, date.today().isoformat())

    ranked = sorted(stats.values(), key=lambda s: s["priority_score"], reverse=True)[:3]
    top_themes = [
        {
            "theme": s["theme"],
            "count": s["count"],
            "avg_rating": s["avg_rating"],
            "wow_change": s["wow_change"],
            "quote": s["quote"],
        }
        for s in ranked
    ]

    result = {
        "generated_at": date.today().isoformat(),
        "total_reviews": total,
        "unclassified_count": unclassified,
        "date_range": {"start": min(dates), "end": max(dates)},
        "top_themes": top_themes,
    }

    with open(OUT, "w") as f:
        json.dump(result, f, indent=2)

    print(f"generated_at: {result['generated_at']}")
    print(f"total_reviews: {total} | unclassified: {unclassified}")
    print(f"date_range: {result['date_range']['start']} to {result['date_range']['end']}")
    if note:
        print(f"note: {note}")
    print(f"top {len(top_themes)} themes by priority score:")
    for t in top_themes:
        wow = "n/a (first run)" if t["wow_change"] is None else f"{t['wow_change']:+d}"
        print(f"  {t['theme']!r}: count={t['count']}, avg_rating={t['avg_rating']}, wow={wow}")
        print(f"      quote: {t['quote']}")


if __name__ == "__main__":
    main()