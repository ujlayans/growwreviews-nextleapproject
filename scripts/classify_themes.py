import csv
import json
import os
import re
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
BATCH_SIZE = 25
RETRIES = 2
BATCH_DELAY = 0.5

THEME_NAMES = {
    "App Stability & Outages",
    "Order Execution Failures",
    "Withdrawals & Fund Transfers",
    "Customer Support",
    "Onboarding & KYC",
}
ALLOWED_THEMES = THEME_NAMES | {"Unclassified"}

SOURCE = "data/reviews_all.csv"
OUT = "data/reviews_classified.csv"
FIELDS = ["platform", "rating", "title", "text", "date", "theme"]

SYSTEM_PROMPT = (
    "You are classifying mobile app reviews for Groww, an Indian stock "
    "investing app. Classify each review into EXACTLY ONE theme:\n"
    '1. "App Stability & Outages" — crashes, downtime during market hours, '
    "lag, login failures\n"
    '2. "Order Execution Failures" — failed buy/sell, exit-order failures, '
    "investment not executed\n"
    '3. "Withdrawals & Fund Transfers" — delayed payouts, money stuck\n'
    '4. "Customer Support" — unresponsive, unresolved tickets, no '
    "compensation offered\n"
    '5. "Onboarding & KYC" — signup friction, account freezes / re-KYC '
    "delays\n"
    '6. "Unclassified" — if none of the above fit\n'
    "Respond ONLY with a JSON array of objects in this exact format: "
    '[{"id": <number>, "theme": "<exact theme name>"}]. '
    "Use exactly the theme names listed above, nothing else."
)


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_listing(batch):
    lines = []
    for i, r in enumerate(batch):
        line = f"{i + 1}. rating: {r['rating']} | text: {r['text']}"
        if r.get("title"):
            line += f" | title: {r['title']}"
        lines.append(line)
    return "\n".join(lines)


def parse_result(content, batch):
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", content).strip()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError("no JSON array found in model output")
        data = json.loads(match.group(0))
    if not isinstance(data, list):
        raise ValueError("expected a JSON array, got " + type(data).__name__)

    by_id = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            idx = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        theme = item.get("theme")
        by_id[idx] = theme if theme in ALLOWED_THEMES else "Unclassified"

    result = []
    for i, r in enumerate(batch):
        theme = by_id.get(i + 1)
        result.append((r, theme if theme else "Unclassified"))
    return result


def classify_batch(client, batch, calls):
    payload = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Reviews:\n" + build_listing(batch)},
    ]
    for attempt in range(1 + RETRIES):
        calls[0] += 1
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0,
                messages=payload,
            )
            content = resp.choices[0].message.content
            return parse_result(content, batch)
        except Exception as e:
            if attempt >= RETRIES:
                print(f"warning: batch failed after retries ({e}), marking as Unclassified", file=sys.stderr)
                break
            time.sleep(1.0 * (attempt + 1))
    return [(r, "Unclassified") for r in batch]


def main():
    if not API_KEY:
        print("error: GROQ_API_KEY not set (set it in .env or the environment)", file=sys.stderr)
        sys.exit(1)

    rows = load_rows(SOURCE)
    if not rows:
        print("error: no rows in " + SOURCE, file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    start = time.time()
    calls = [0]
    classified = []
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        classified.extend(classify_batch(client, batch, calls))
        time.sleep(BATCH_DELAY)
    elapsed = time.time() - start

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for r, theme in classified:
            writer.writerow({**r, "theme": theme})

    counts = {}
    for _, theme in classified:
        counts[theme] = counts.get(theme, 0) + 1

    batches = (len(rows) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"batches run: {batches} ({calls[0]} API calls total, incl. retries)")
    print(f"classified {len(classified)} reviews in {elapsed:.1f}s")
    for theme in sorted(counts, key=lambda t: -counts[t]):
        print(f"  {theme}: {counts[theme]}")


if __name__ == "__main__":
    main()