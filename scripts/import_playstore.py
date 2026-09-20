import csv
import sys
from datetime import date, timedelta

from google_play_scraper import Sort, reviews

APP_ID = "com.nextbillion.groww"
COUNTRY = "in"
LANG = "en"
WINDOW_DAYS = 84
BATCH = 500
MAX_BATCHES = 100
OUT = "data/playstore_reviews.csv"

FIELDS = ["platform", "rating", "title", "text", "date"]


def fetch_all_reviews():
    collected = {}
    token = None
    for _ in range(MAX_BATCHES):
        batch, token = reviews(
            APP_ID,
            lang=LANG,
            country=COUNTRY,
            sort=Sort.NEWEST,
            count=BATCH,
            continuation_token=token,
        )
        if not batch:
            break
        for item in batch:
            collected[item["reviewId"]] = item
        oldest_in_batch = min(r["at"] for r in batch)
        if token is None or oldest_in_batch.date() < date.today() - timedelta(days=WINDOW_DAYS):
            break
    return list(collected.values())


def main():
    cutoff = date.today() - timedelta(days=WINDOW_DAYS)

    try:
        items = fetch_all_reviews()
    except Exception as e:
        print(f"error: failed to pull google play reviews: {e}", file=sys.stderr)
        sys.exit(1)

    if not items:
        print("error: google play returned no reviews", file=sys.stderr)
        sys.exit(1)

    kept = [
        {
            "platform": "playstore",
            "rating": item["score"],
            "title": "",
            "text": item["content"],
            "date": item["at"].date().isoformat(),
        }
        for item in items
        if cutoff <= item["at"].date() <= date.today()
    ]
    kept.sort(key=lambda r: r["date"], reverse=True)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)

    dates = [r["date"] for r in kept]
    print(f"fetched {len(kept)} of {len(items)} google play reviews within last {WINDOW_DAYS} days")
    if dates:
        print(f"date range: {min(dates)} to {max(dates)}")


if __name__ == "__main__":
    main()