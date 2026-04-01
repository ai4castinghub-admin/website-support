import json
import re
import sys
import html
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

SEARCH_QUERY = (
    '("virus forecasting" OR "influenza forecasting" OR '
    '"RSV forecasting" OR "COVID forecasting" OR '
    '"infectious disease forecasting" OR '
    '"respiratory virus forecasting") research'
)

RSS_URL = (
    "https://news.google.com/rss/search?"
    f"q={quote_plus(SEARCH_QUERY)}&hl=en-CA&gl=CA&ceid=CA:en"
)

OUTPUT_PATH = "news.json"
MAX_ITEMS = 5
DAYS_BACK = 7


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clip(text: str, limit: int = 210) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:") + "…"


def parse_pubdate(raw: str):
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def parse_source_from_title(title: str) -> str:
    # Google News RSS titles often look like:
    # "Some headline - Nature"
    if " - " in title:
      parts = title.rsplit(" - ", 1)
      if len(parts) == 2 and parts[1].strip():
          return parts[1].strip()
    return "News source"


def normalize_title(title: str) -> str:
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts) == 2 and parts[0].strip():
            return parts[0].strip()
    return title.strip()


def fetch_rss(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; ForecastingNewsSlider/1.0)"
        },
    )
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_items(xml_text: str):
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=DAYS_BACK)
    output = []

    for item in channel.findall("item"):
        title_raw = item.findtext("title", default="").strip()
        link = item.findtext("link", default="").strip()
        pub_raw = item.findtext("pubDate", default="").strip()
        desc_raw = item.findtext("description", default="").strip()

        pub_dt = parse_pubdate(pub_raw)
        if not pub_dt:
            continue

        if pub_dt < cutoff:
            continue

        title = normalize_title(title_raw)
        source = parse_source_from_title(title_raw)
        summary = clip(strip_html(desc_raw))

        if not title or not link:
            continue

        output.append(
            {
                "title": title,
                "link": link,
                "pubDate": pub_dt.isoformat(),
                "source": source,
                "summary": summary or "Open the article for more details."
            }
        )

    output.sort(key=lambda x: x["pubDate"], reverse=True)
    return output[:MAX_ITEMS]


def main():
    try:
        xml_text = fetch_rss(RSS_URL)
        items = extract_items(xml_text)

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "feed_source": RSS_URL,
            "items": items,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(f"Wrote {len(items)} items to {OUTPUT_PATH}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
