import csv
import random
import re

RATINGS = (1, 2, 3, 4, 5)
SAMPLE_SIZE = 350
SEED = 42
APPSTORE = "data/appstore_reviews.csv"
PLAYSTORE = "data/playstore_reviews.csv"
OUT = "data/reviews_all.csv"
FIELDS = ["platform", "rating", "title", "text", "date"]

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\b\d{10,}\b")
UPI_RE = re.compile(r"\b[\w.]+@[a-zA-Z]+\b")
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")


def redact(text):
    text = EMAIL_RE.sub("[email removed]", text)
    text = PHONE_RE.sub("[number removed]", text)
    text = UPI_RE.sub("[upi removed]", text)
    text = PAN_RE.sub("[pan removed]", text)
    return text


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def stratified_sample(rows, n, rng):
    buckets = {k: [r for r in rows if int(r["rating"]) == k] for k in RATINGS}
    counts = {k: len(b) for k, b in buckets.items()}
    total = sum(counts.values())

    ideal = [(k, counts[k] * n / total) for k in RATINGS]
    alloc = {k: int(v) for k, v in ideal}
    leftover = n - sum(alloc.values())
    for k, _ in sorted(ideal, key=lambda kv: kv[1] - int(kv[1]), reverse=True):
        if leftover == 0:
            break
        alloc[k] += 1
        leftover -= 1

    sampled = []
    for k in RATINGS:
        size = min(len(buckets[k]), alloc[k])
        sampled.extend(rng.sample(buckets[k], size))
    return sampled


def main():
    rng = random.Random(SEED)
    appstore = load(APPSTORE)
    playstore = load(PLAYSTORE)

    playstore_sample = stratified_sample(playstore, SAMPLE_SIZE, rng)
    merged = appstore + playstore_sample

    clean = []
    for r in merged:
        try:
            rating = int(r["rating"])
        except (TypeError, ValueError):
            continue
        if rating not in RATINGS or not (r["text"] or "").strip():
            continue
        clean.append(
            {
                "platform": r["platform"],
                "rating": str(rating),
                "title": redact(r["title"] or ""),
                "text": redact(r["text"]),
                "date": r["date"],
            }
        )

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(clean)

    dates = [r["date"] for r in clean]
    platforms = {}
    for r in clean:
        platforms[r["platform"]] = platforms.get(r["platform"], 0) + 1

    print(f"total rows: {len(clean)}")
    for p, c in sorted(platforms.items()):
        print(f"  {p}: {c}")
    print(f"date range: {min(dates)} to {max(dates)}")


if __name__ == "__main__":
    main()