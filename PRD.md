PRD — Groww Weekly Review Pulse

Problem
Groww gets a steady stream of App Store + Play Store reviews. Product, Support, and Leadership have no fast way to see what's recurring — real issues (outages during market hours, failed orders, stuck withdrawals) surface late, often only after they spike into social media complaints or support tickets.

Goal
A weekly, one-page "Review Pulse" — top 3 themes, 3 verbatim quotes, 3 action ideas — generated and drafted into an email in one run, so it can be re-run every Monday in minutes.

Users

Product/Growth — what to fix next
Support — what users are already frustrated about
Leadership — 30-second health check

Theme legend (fixed, exactly 5 — never a 6th)
Derived from the assignment's suggested categories, an 8-review sample pull, and broader public reporting on Groww-specific complaint patterns:

App Stability & Outages — crashes, downtime during market hours, lag, login failures
Order Execution Failures — failed buy/sell, exit-order failures, investment not executed
Withdrawals & Fund Transfers — delayed payouts, money stuck
Customer Support — unresponsive, unresolved tickets, no compensation offered
Onboarding & KYC — signup friction, account freezes / re-KYC delays

Pipeline
Import (App Store RSS + Play Store scraper, public sources only) → PII redact → Classify (Mistral) → Compute stats in code (counts, avg rating, WoW change) → Generate note (Mistral, ≤250 words) → Draft email

Week-over-week handling
First run: note states "first run — no prior week yet." From the second weekly run onward, this run's per-theme counts get saved to a small history.json, and WoW deltas become real.

PII redaction
Regex-stripped before any Mistral call: emails, phone numbers, UPI IDs, PAN numbers. Applies to CSV, note, and email — no exceptions.

Constraints

Public review exports only, no login-scraping
Max 5 themes, fixed legend above
Note ≤250 words, exactly 3 themes / 3 quotes / 3 actions
No PII in any artifact

Build order

Local pipeline (Import → Classify → Note → Email), fully working
GitHub repo with README (re-run steps, theme legend)
Optional: wrap in a hosted web page, if time allows