import csv
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

APP_ID = "1404871703"
COUNTRY = "in"
MAX_PAGES = 10
PAGE_SIZE = 50
OUT = "data/appstore_reviews.csv"

ATOM = "{http://www.w3.org/2005/Atom}"
ITUNES = "{http://itunes.apple.com/rss}"

BASE = ("https://itunes.apple.com/{country}/rss/customerreviews/page={page}/"
        "id={app_id}/sortby=mostrecent/xml")


def fetch_page(page):
    url = BASE.format(country=COUNTRY, page=page, app_id=APP_ID)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return ET.fromstring(resp.read())


def iter_reviews(root):
    for entry in root.iter(f"{ATOM}entry"):
        title = entry.findtext(f"{ATOM}title", "")
        text = ""
        for content in entry.findall(f"{ATOM}content"):
            if content.get("type") == "text":
                text = content.text or ""
                break
        rating = entry.findtext(f"{ITUNES}rating", "")
        updated = entry.findtext(f"{ATOM}updated", "")
        yield {
            "platform": "appstore",
            "rating": rating,
            "title": title,
            "text": text,
            "date": updated[:10],
        }


def write_reviews(reviews):
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["platform", "rating", "title", "text", "date"])
        writer.writeheader()
        writer.writerows(reviews)


def main():
    reviews = []
    for page in range(1, MAX_PAGES + 1):
        try:
            root = fetch_page(page)
        except urllib.error.HTTPError as e:
            if e.code == 400:
                break
            print(f"error: HTTP {e.code} while fetching page {page}", file=sys.stderr)
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"error: could not reach iTunes feed: {e}", file=sys.stderr)
            sys.exit(1)

        page_reviews = list(iter_reviews(root))
        if not page_reviews:
            break
        reviews.extend(page_reviews)
        if len(page_reviews) < PAGE_SIZE:
            break

    if not reviews:
        print("error: no reviews returned by the iTunes feed", file=sys.stderr)
        sys.exit(1)

    write_reviews(reviews)

    dates = [r["date"] for r in reviews]
    print(f"fetched {len(reviews)} app stores (ios) reviews")
    print(f"date range: {min(dates)} to {max(dates)}")


if __name__ == "__main__":
    main()