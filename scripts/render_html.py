import json
import os
import re
from html import escape

NOTE = "output/weekly_note.md"
STATS = "data/theme_stats.json"
OUT = "docs/index.html"

THEMES = [
    ("App Stability & Outages", "Crashes, downtime during market hours, lag, login failures"),
    ("Order Execution Failures", "Failed buy/sell, exit-order failures, investment not executed"),
    ("Withdrawals & Fund Transfers", "Delayed payouts, money stuck"),
    ("Customer Support", "Unresponsive, unresolved tickets, no compensation offered"),
    ("Onboarding & KYC", "Signup friction, account freezes / re-KYC delays"),
]

CSS = """
    :root {
        --accent: #4f46e5;
        --ink: #1f2430;
        --muted: #6b7280;
        --bg: #f6f7f9;
        --card: #ffffff;
        --border: #e5e7eb;
        --quote-bg: #eef0ff;
    }
    * { box-sizing: border-box; }
    body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                     Helvetica, Arial, sans-serif;
        background: var(--bg);
        color: var(--ink);
        line-height: 1.6;
        padding: 32px 16px;
    }
    .container { max-width: 820px; margin: 0 auto; }
    .hero {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 28px 36px;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
        border-top: 4px solid var(--accent);
    }
    h1 { margin: 0 0 6px; font-size: 24px; }
    .meta { color: var(--muted); font-size: 14px; margin-bottom: 24px; }
    h2 {
        font-size: 18px;
        margin: 28px 0 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border);
    }
    h3 { font-size: 15px; margin: 20px 0 8px; }
    p { margin: 8px 0; }
    blockquote {
        margin: 10px 0;
        padding: 12px 16px;
        background: var(--quote-bg);
        border-left: 3px solid var(--accent);
        border-radius: 0 8px 8px 0;
        color: #374151;
        font-style: italic;
    }
    ul { margin: 8px 0 8px 22px; padding: 0; }
    li { margin: 6px 0; }
    .theme-line { font-weight: 600; }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 14px;
        background: var(--card);
    }
    th, td {
        text-align: left;
        padding: 10px 12px;
        border-bottom: 1px solid var(--border);
        vertical-align: top;
    }
    th { background: #fafafa; }
    td:first-child { font-weight: 600; white-space: nowrap; }
    footer {
        color: var(--muted);
        font-size: 13px;
        text-align: center;
        margin-top: 28px;
    }
"""


def load_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def load_stats():
    with open(STATS) as f:
        return json.load(f)


def inline(s):
    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s


def render_note(note):
    lines = note.splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]

    html = []
    in_ul = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            html.append("</ul>")
            in_ul = False

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("### "):
            close_ul()
            html.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_ul()
            html.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_ul()
            html.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("> "):
            close_ul()
            html.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif re.match(r"^\d+\.\s", line):
            close_ul()
            body = re.sub(r"^\d+\.\s", "", line)
            html.append(f'<p class="theme-line">{inline(body)}</p>')
        elif line.startswith("- "):
            if not in_ul:
                html.append("<ul>")
                in_ul = True
            html.append(f"<li>{inline(line[2:])}</li>")
        elif line.strip() == "":
            close_ul()
        else:
            close_ul()
            html.append(f"<p>{inline(line)}</p>")
    close_ul()
    return "\n".join(html)


def legend_rows():
    return "".join(
        f"<tr><td>{escape(name)}</td><td>{escape(desc)}</td></tr>"
        for name, desc in THEMES
    )


def build_html(note_html, stats):
    gen = stats["generated_at"]
    total = stats["total_reviews"]
    start = stats["date_range"]["start"]
    end = stats["date_range"]["end"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Groww — Weekly Review Pulse</title>
<style>
{CSS}
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1>Groww — Weekly Review Pulse</h1>
    <div class="meta">Generated {gen} &middot; {total} reviews &middot; {start} to {end}</div>
{note_html}
    <h2>Theme legend</h2>
    <table>
      <tr><th>Theme</th><th>Covers</th></tr>
{legend_rows()}
    </table>
  </div>
  <footer>Auto-generated. No PII included. Data from public App Store + Play Store reviews only.</footer>
</div>
</body>
</html>
"""


def main():
    note = load_text(NOTE)
    stats = load_stats()
    note_html = render_note(note)
    page = build_html(note_html, stats)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)

    size = os.path.getsize(OUT)
    print(f"wrote {OUT} ({size} bytes)")


if __name__ == "__main__":
    main()