# Groww Weekly Review Pulse

An automated weekly review-intelligence pipeline for Groww. It pulls the
latest App Store and Play Store reviews from public sources (no login),
redacts PII, classifies every review into one fixed theme via an LLM,
computes stats with week-over-week deltas, and drafts a one-page note plus a
ready-to-open email.

## Pipeline

```
Import -> PII Redact -> Classify -> Compute Stats -> Generate Note -> Draft Email
```

## Theme legend

| Theme | Covers |
| --- | --- |
| App Stability & Outages | Crashes, downtime during market hours, lag, login failures |
| Order Execution Failures | Failed buy/sell, exit-order failures, investment not executed |
| Withdrawals & Fund Transfers | Delayed payouts, money stuck |
| Customer Support | Unresponsive, unresolved tickets, no compensation offered |
| Onboarding & KYC | Signup friction, account freezes / re-KYC delays |

Reviews that fit none of the above are labeled `Unclassified` and ignored for
theme stats.

## How to re-run for a new week

1. Set up the environment (one time):

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install google-play-scraper python-dotenv openai
   cp .env.example .env
   ```

2. Put your real key in `.env`:

   ```
   GROQ_API_KEY=<your_key_here>
   ```

3. Run each script in `scripts/`, in order:

   ```bash
   .venv/bin/python scripts/import_appstore.py      # -> data/appstore_reviews.csv
   .venv/bin/python scripts/import_playstore.py     # -> data/playstore_reviews.csv
   .venv/bin/python scripts/merge_and_scrub.py      # -> data/reviews_all.csv
   .venv/bin/python scripts/classify_themes.py      # -> data/reviews_classified.csv
   .venv/bin/python scripts/compute_stats.py        # -> data/theme_stats.json (writes output/history.json)
   .venv/bin/python scripts/generate_note.py        # -> output/weekly_note.md
   .venv/bin/python scripts/draft_email.py --to you@example.com  # -> output/email_draft.txt / .eml
   ```

   The email draft is never sent — it is written as local files only.

## Known limitations

- **App Store coverage is capped.** Apple's public iTunes RSS feed returns at
  most ~400 reviews per app (8 pages x 50). For high-volume apps this may not
  reach back the full 8-12 week window.
- **Play Store is sampled, not exhaustive.** To keep classification fast and
  cheap, only a fixed random sample (350 reviews, stratified by 1-5 star
  rating, seed 42) of the available Play Store pool is used.
- **Theme count is fixed at 5.** There is deliberately no 6th theme; anything
  that doesn't fit is `Unclassified`.

## Data and output

### data/
| File | Contents |
| --- | --- |
| `appstore_reviews.csv` | Raw iOS reviews (platform, rating, title, text, date) |
| `playstore_reviews.csv` | Raw Play Store reviews from the last 84 days (same schema) |
| `reviews_all.csv` | Merged + PII-redacted dataset (all iOS, 350 Play sample) |
| `reviews_classified.csv` | `reviews_all.csv` + a `theme` column per review |
| `theme_stats.json` | Top-3 themes with counts, avg ratings, WoW change, verbatim quotes |

### output/
| File | Contents |
| --- | --- |
| `history.json` | Last run's per-theme counts + date (for week-over-week deltas) |
| `weekly_note.md` | The generated one-page note (top 3 themes, 3 quotes, 3 actions) |
| `email_draft.txt` | Plain-text email draft |
| `email_draft.eml` | Double-clickable email draft for Mail/Outlook |