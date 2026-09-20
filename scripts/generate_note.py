import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
SOURCE = "data/theme_stats.json"
OUT = "output/weekly_note.md"
WORD_LIMIT = 250
RETRIES = 2

TITLE = "Groww — Weekly Review Pulse"

BASE_PROMPT = (
    "You are a customer insights analyst writing a one-page weekly note for "
    "the Groww product, support, and leadership teams.\n"
    "Write a markdown note titled exactly: \"{title}\".\n"
    "Use ONLY the facts below. Do not invent extra numbers.\n\n"
    "Facts:\n"
    "- Total reviews scanned: {total}, covering {start} to {end}."
    "{first_run}\n"
    "{themes}\n\n"
    "Format requirements:\n"
    "- Title line: \"{title}\"\n"
    "- One intro line stating total reviews scanned and the date range"
    "{first_run_clause}.\n"
    "- A \"Top themes\" section listing the top 3 themes, each with its "
    "theme name, count, and average rating.\n"
    "- Reproduce each quote VERBATIM as a direct quote. Never paraphrase, "
    "never fix grammar or spelling, keep original characters.\n"
    "- Give exactly 3 action ideas, one per theme, concrete and owned "
    "(propose a specific owner/team and one specific change), not vague "
    "like \"fix bugs\".\n"
    "Keep the whole note at or under {word_limit} words."
)


def count_words(text):
    return len(text.split())


def build_prompt(stats, mode="generate", current_note=None):
    top = stats["top_themes"]
    first_run = all(t["wow_change"] is None for t in top)
    first_run_clause = ", first run, no prior week to compare" if first_run else ""

    themes_block = "\n".join(
        f"- Theme {i + 1}: {t['theme']} | count {t['count']} | avg rating "
        f"{t['avg_rating']} | verified quote: \"{t['quote']}\""
        for i, t in enumerate(top)
    )

    prompt = BASE_PROMPT.format(
        title=TITLE,
        total=stats["total_reviews"],
        start=stats["date_range"]["start"],
        end=stats["date_range"]["end"],
        first_run=(" (first run — no prior week to compare)" if first_run else ""),
        first_run_clause=first_run_clause,
        themes=themes_block,
        word_limit=WORD_LIMIT,
    )

    if mode == "tighten":
        prompt += (
            "\n\nThe previous draft is over the word limit. Rewrite it to "
            "be at or under {limit} words while keeping every quote "
            "verbatim.\n\nPrevious draft:\n{note}".format(
                limit=WORD_LIMIT,
                note=current_note,
            )
        )
    return prompt


def call_model(prompt):
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    last_error = None
    for _ in range(1 + RETRIES):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                temperature=0.4,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            time.sleep(1.0)
    raise RuntimeError(f"model call failed after retries: {last_error}")


def append_missing_quotes(note, quotes):
    missing = [q for q in quotes if q not in note]
    for q in missing:
        note = note.rstrip() + f"\n\n> {q}"
    return note


def verify_and_fix(note, quotes, generate):
    missing = [q for q in quotes if q not in note]
    if not missing:
        return note, True
    retried = generate()
    for q in quotes:
        if q not in retried:
            retried = retried.rstrip() + f"\n\n> {q}"
    return retried, all(q in retried for q in quotes)


def load_stats():
    with open(SOURCE) as f:
        return json.load(f)


def main():
    if not API_KEY:
        print("error: GROQ_API_KEY not set (set it in .env or the environment)", file=sys.stderr)
        sys.exit(1)

    stats = load_stats()
    top = stats["top_themes"]
    if len(top) < 3:
        print(f"error: expected 3 top themes in {SOURCE}, found {len(top)}", file=sys.stderr)
        sys.exit(1)
    quotes = [t["quote"] for t in top]

    generate = lambda: call_model(build_prompt(stats, mode="generate"))
    tighten = lambda: call_model(build_prompt(stats, mode="tighten", current_note=note))

    note = generate()
    note, verified = verify_and_fix(note, quotes, generate)

    if count_words(note) > WORD_LIMIT:
        note = tighten()
        note, verified = verify_and_fix(note, quotes, generate)
        if count_words(note) > WORD_LIMIT:
            words = note.split()
            note = " ".join(words[:WORD_LIMIT])
            note = append_missing_quotes(note, quotes)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(note + "\n")

    print(f"word count: {count_words(note)} (limit {WORD_LIMIT})")
    for q in quotes:
        print(f"quote exact match: {q in note} -> {q!r}")


if __name__ == "__main__":
    main()