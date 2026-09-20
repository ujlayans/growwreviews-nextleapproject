# Groww Weekly Review Pulse

An automated weekly review-intelligence pipeline for Groww. Each week it pulls
the latest public App Store and Play Store reviews (no login required),
redacts PII, classifies every review into one of five fixed themes via an LLM,
computes stats with week-over-week deltas, generates a one-page note, and
drafts a ready-to-send email.

**Live prototype (GitHub Pages):** https://ujlayans.github.io/growwreviews-nextleapproject/

## Pipeline

```
Import -> PII Redact -> Classify -> Compute Stats -> Generate Note -> Draft Email
```

| # | Stage | Script | Output |
| --- | --- | --- | --- |
| 1 | Import | `scripts/import_appstore.py`, `scripts/import_playstore.py` | `data/appstore_reviews.csv`, `data/playstore_reviews.csv` |
| 2 | PII Redact + Merge | `scripts/merge_and_scrub.py` | `data/reviews_all.csv` |
| 3 | Classify | `scripts/classify_themes.py` | `data/reviews_classified.csv` |
| 4 | Compute Stats | `scripts/compute_stats.py` | `data/theme_stats.json`, `output/history.json` |
| 5 | Generate Note | `scripts/generate_note.py` | `output/weekly_note.md` |
| 6 | Draft Email | `scripts/draft_email.py` | `output/email_draft.txt`, `output/email_draft.eml` |

A helper stage renders the note as a self-contained web page:
`scripts/render_html.py` -> `docs/index.html` (hosted via GitHub Pages).

## Theme legend

Reviews are classified into EXACTLY ONE of these 5 fixed themes (there is
deliberately no 6th theme; anything that doesn't fit becomes `Unclassified`
and is ignored for theme stats):

| Theme | Covers |
| --- | --- |
| App Stability & Outages | Crashes, downtime during market hours, lag, login failures |
| Order Execution Failures | Failed buy/sell, exit-order failures, investment not executed |
| Withdrawals & Fund Transfers | Delayed payouts, money stuck |
| Customer Support | Unresponsive, unresolved tickets, no compensation offered |
| Onboarding & KYC | Signup friction, account freezes / re-KYC delays |

## How each stage works

### 1. Import

- **App Store** (`import_appstore.py`): pulls Groww's iOS reviews (App ID
  `1404871703`, storefront `in`) from Apple's public iTunes RSS feed
  (`/rss/customerreviews/page={n}/id={app_id}/sortby=mostrecent`). The JSON
  serialization of this feed returns empty for this app, so the script uses
  the XML serialization of the exact same feed. Apple caps the feed at
  ~400 reviews (8 pages x 50); the script stops when a page has no entries.
- **Play Store** (`import_playstore.py`): uses the `google-play-scraper`
  pip package (public endpoint, no login) for `com.nextbillion.groww`,
  sorted newest-first, filtered to the last 84 days. On any failure it
  prints a clear error and exits non-zero without writing partial data.

### 2. PII redaction + merge (`merge_and_scrub.py`)

- Keeps **all** App Store reviews and a **350-row stratified random sample**
  of Play Store reviews (proportional per 1-5 star bucket, fixed seed `42`),
  so 1-star complaints aren't lost to random chance.
- Redacts PII in `title` and `text` **before any LLM call**:
  - emails -> `[email removed]`
  - phone numbers (10+ digit runs) -> `[number removed]`
  - UPI IDs (`word@bankname`) -> `[upi removed]`
  - PAN numbers (`ABCDE1234F`) -> `[pan removed]`
- Validates each row: rating must be 1-5 and text non-empty; invalid rows are
  dropped.

### 3. Classification (`classify_themes.py`)

- Loads `GROQ_API_KEY` from `.env` (via `python-dotenv`).
- Uses Groq's OpenAI-compatible endpoint (`https://api.groq.com/openai/v1`)
  with the `openai` Python client.
- **Default model:** `openai/gpt-oss-20b` (overridable via `GROQ_MODEL`).
  Note: the original choice `llama-3.1-8b-instant` has been retired from
  Groq's line-up, so the working substitute is used instead.
- Reviews are classified in **batches of ~25** per API call (numbered list,
  model returns a JSON array of `{id, theme}`) — 750 reviews take ~30 calls,
  not 750.
- Model output is validated: any theme name that isn't one of the 5 (or
  `Unclassified`) is coerced to `Unclassified`. Unknown/missing ids default
  to `Unclassified`.
- Failed batches are retried (2 retries); a batch that still fails is marked
  `Unclassified` rather than crashing the run. A 0.5s delay runs between
  batches.

### 4. Stats (`compute_stats.py`)

For each of the 5 themes (ignoring `Unclassified`):

```
count = number of reviews
avg_rating = mean of the rating column
severity = 6 - avg_rating
priority_score = count * severity
```

Themes are ranked by `priority_score` (descending) and the **top 3** are kept.

**Week-over-week:** `output/history.json` stores the previous run's per-theme
counts. If it's missing, this is the first run: `wow_change` is `null` for
every theme and the note says "first run — no prior week to compare".
Otherwise `wow_change = this_run_count - last_run_count`. After computing
deltas, `output/history.json` is overwritten with this run's counts + date.

**Quotes:** for each top theme, one real review is quoted verbatim — the
shortest review (preferably under ~25 words) containing a theme keyword. The
quote is an exact substring of a real review's text; it is never paraphrased
or altered.

### 5. Note generation (`generate_note.py`)

- Sends the **computed facts only** (theme names, counts, avg ratings, and
  the exact quotes) to Groq and asks for a `<=250`-word weekly note:
  title "Groww — Weekly Review Pulse", one line with total reviews + date
  range, the top 3 themes with count + avg rating, the 3 quotes reproduced
  **verbatim** (never cleaned up, never paraphrased), and 3 concrete action
  ideas with owners.
- Post-generation checks in code:
  - Each of the 3 quotes must appear **exactly** (substring match) — if not,
    retry once, then the quote is inserted directly rather than trusting a
    broken generation.
  - Word count must be `<=250` — if over, the model is asked to tighten once;
    if still over, the note is truncated deterministically (quotes are
    re-inserted afterward so they can never be lost).

### 6. Email draft (`draft_email.py`)

- Builds a plain-text draft (`output/email_draft.txt`) and a real `.eml`
  file (via `email.message`) that double-clicks open in Mail/Outlook.
- Subject: `Groww Weekly Review Pulse — <date>`. Body: short intro, the full
  weekly note, and a footer noting it's auto-generated and contains no PII.
- Recipient passed via `--to` (default `you@example.com`).
- **Nothing is ever sent** — no SMTP, draft files only.

### Web page (`render_html.py`)

- Renders `output/weekly_note.md` + `data/theme_stats.json` into
  `docs/index.html`: a single self-contained page (inline CSS, no external
  dependencies) with the note, styled quote blockquotes, action ideas, a
  theme legend table, and a no-PII footer.

## Last run (2026-09-20)

| Metric | Value |
| --- | --- |
| Total reviews analysed | 750 |
| App Store (iTunes RSS) | 400 |
| Play Store (stratified sample) | 350 |
| Date range covered | 2026-06-28 to 2026-09-19 |
| Classified | 45 themed + 705 Unclassified |

Theme distribution: Customer Support 15, App Stability & Outages 9,
Withdrawals & Fund Transfers 8, Order Execution Failures 8, Onboarding & KYC 5.

Top 3 themes by priority score:

| Theme | Count | Avg rating | Quote |
| --- | --- | --- | --- |
| Customer Support | 15 | 1.2 | "Very very very bad service they even didn't replied" |
| Withdrawals & Fund Transfers | 8 | 1.0 | "This app is very slow in withdrawal and also many charges are applied" |
| Order Execution Failures | 8 | 1.12 | "bad experience in groww lag chart price not correct in excute order" |

Week-over-week: first run — no prior week to compare.

## How to re-run for a new week

1. Set up the environment (one time):

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install google-play-scraper python-dotenv openai
   cp .env.example .env
   ```

2. Put your real key in `.env` (`.env` is gitignored — never commit it):

   ```
   GROQ_API_KEY=<your_key_here>
   ```

3. Run each script in `scripts/`, in order:

   ```bash
   .venv/bin/python scripts/import_appstore.py
   .venv/bin/python scripts/import_playstore.py
   .venv/bin/python scripts/merge_and_scrub.py
   .venv/bin/python scripts/classify_themes.py
   .venv/bin/python scripts/compute_stats.py
   .venv/bin/python scripts/generate_note.py
   .venv/bin/python scripts/draft_email.py --to you@example.com
   .venv/bin/python scripts/render_html.py      # optional web page
   ```

## Known limitations

- **App Store coverage is capped.** Apple's public iTunes RSS feed returns at
  most ~400 reviews per app (8 pages x 50). For high-volume apps this may not
  reach back the full 8-12 week window.
- **Play Store is sampled, not exhaustive.** Classification uses a fixed
  random sample of 350 Play Store reviews (stratified by star rating, seed
  42) for cost and speed.
- **Model choice is a moving target.** `llama-3.1-8b-instant` was retired
  from Groq; the pipeline now defaults to `openai/gpt-oss-20b`, overridable
  via `GROQ_MODEL`.
- **LLMs can improvise figures.** Generated action ideas are not grounded in
  review data, so numeric claims must be checked (a fabricated "2% withdrawal
  fee" was caught and removed during development).
- **Theme count is fixed at 5.** There is deliberately no 6th theme; anything
  that doesn't fit is `Unclassified`.

## Repository layout

### data/ — generated datasets
| File | Contents |
| --- | --- |
| `appstore_reviews.csv` | Raw iOS reviews (platform, rating, title, text, date) |
| `playstore_reviews.csv` | Raw Play Store reviews from the last 84 days (same schema) |
| `reviews_all.csv` | Merged + PII-redacted (all iOS, 350 Play sample) |
| `reviews_classified.csv` | `reviews_all.csv` + a `theme` column per review |
| `theme_stats.json` | Top-3 themes with counts, avg ratings, WoW change, verbatim quotes |

### output/ — generated artifacts
| File | Contents |
| --- | --- |
| `history.json` | Last run's per-theme counts + date (for week-over-week deltas) |
| `weekly_note.md` | Generated one-page note (top 3 themes, 3 quotes, 3 actions) |
| `email_draft.txt` | Plain-text email draft |
| `email_draft.eml` | Double-clickable email draft for Mail/Outlook |

### docs/ — hosted page
| File | Contents |
| --- | --- |
| `index.html` | Self-contained weekly review page (served via GitHub Pages) |

### scripts/ — the pipeline
| File | Stage |
| --- | --- |
| `import_appstore.py` | Import iOS reviews from iTunes RSS |
| `import_playstore.py` | Import Play Store reviews (google-play-scraper) |
| `merge_and_scrub.py` | PII-redact + merge (stratified Play sample) |
| `classify_themes.py` | LLM theme classification (Groq, batched) |
| `compute_stats.py` | Counts, avg rating, severity, priority score, WoW deltas |
| `generate_note.py` | One-page note (<=250 words, verified quotes) |
| `draft_email.py` | `.txt` + `.eml` email draft (never sends) |
| `render_html.py` | Self-contained `docs/index.html` |