"""Kremlin (President of Russia), English site: every publication, from its Atom feed (no key).

    http://en.kremlin.ru/events/all/feed  (and /page/2, /page/3: about 20 entries a page)

Terms: the site's footer and /about/copyrights put its text under CC BY 4.0 (reuse with a reference to
en.kremlin.ru); photos credited to RIA Novosti or TASS are excluded, so no image is kept. Readout keeps the title,
link, times, a short opening excerpt and the sentences that hold a claim word, with the source named.

The feed's times carry +04:00 (shown as published; Moscow is +03:00 in winter), so they are converted to UTC by their
own offset, never assumed.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import claims, places, text

FEED = "http://en.kremlin.ru/events/all/feed"
PAGE = FEED + "/page/{n}"
PAGES = 3
EXCERPT = 400
A = "{http://www.w3.org/2005/Atom}"
ISSUER = "RU"
# Paths that are not statements: acts are decrees and laws (kept, they are what the state did), but calendar
# announcements and photo galleries carry no claim.
SKIP_PATHS = ("/events/president/trips/", "/multimedia/")


def page_urls() -> list[str]:
    return [FEED] + [PAGE.format(n=n) for n in range(2, PAGES + 1)]


def parse(body: bytes) -> list[dict]:
    root = ET.fromstring(body)
    if root.tag != A + "feed":
        raise ValueError("Kremlin reply is not an Atom feed")
    out = []
    for e in root.findall(A + "entry"):
        link = None
        for ln in e.findall(A + "link"):
            if ln.get("rel", "alternate") == "alternate":
                link = ln.get("href")
        out.append({"id": (e.findtext(A + "id") or "").strip(), "title": (e.findtext(A + "title") or "").strip(),
                    "published": e.findtext(A + "published"), "updated": e.findtext(A + "updated"),
                    "link": link or (e.findtext(A + "id") or "").strip(),
                    "summary": e.findtext(A + "summary") or "", "content": e.findtext(A + "content") or ""})
    return out


def kind_of(url: str) -> str:
    for part, k in (("/transcripts/", "transcript"), ("/acts/", "act"), ("/letters/", "letter"),
                    ("/news/", "news"), ("/messages/", "message"), ("/statements/", "statement")):
        if part in url:
            return k
    return "publication"


def record(e: dict) -> dict | None:
    url = e["link"].replace("http://", "https://", 1) if e["link"].startswith("http://en.kremlin.ru") else e["link"]
    if not url.startswith("https://en.kremlin.ru/") or any(p in url for p in SKIP_PATHS):
        return None
    num = re.search(r"/(\d+)$", url)
    body = text.plain(e["content"]) or text.plain(e["summary"])
    full = f"{e['title']}. {body}"
    cls = claims.classify(full)
    ccs, _, _ = places.countries_in(full)
    excerpt = body if len(body) <= EXCERPT else body[: EXCERPT - 1].rsplit(" ", 1)[0] + "…"
    return {
        "key": f"kremlin:{num.group(1) if num else e['id']}",
        "lane": "kremlin",
        "issuer": ISSUER,
        "issuer_name": "President of Russia (Kremlin)",
        "doc_type": kind_of(url),
        "title": e["title"],
        "url": url,
        "published_at": text.utc(e["published"]) or text.utc(e["updated"]),
        "updated_at": text.utc(e["updated"]),
        "time_precision": "second",
        "countries_mentioned": [c for c in ccs],
        "excerpt": excerpt or None,
        "quotes": claims.sentences_with(body, cls),
        "claims": cls,
        "claim": claims.primary(cls),
        "words": len(body.split()),
    }


def build(entries: list[dict]) -> list[dict]:
    seen, out = set(), []
    for e in entries:
        r = record(e)
        if r and r["key"] not in seen and r["published_at"]:
            seen.add(r["key"])
            out.append(r)
    return sorted(out, key=lambda r: (r["published_at"], r["key"]), reverse=True)
