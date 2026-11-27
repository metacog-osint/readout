"""African Union Peace and Security Council (PSC) communiqués, from the AU Peace and Security Department's RSS feed.
HELD: off unless enabled.

    http://www.peaceau.org/en/rss  (RSS 2.0; the format was not read from this environment, so the parser takes any
    RSS 2.0 or Atom feed and keeps only items whose title is a PSC communiqué or press statement)

Titles read "Communiqué of the 1290th meeting of the PSC held on 20 November 2026 on the situation in ...".

Terms: peaceau.org's legal notice forbids redistributing, compiling or making derivative works of its content without
written permission (situationroom@africa-union.org). Readout would keep the meeting number, date, link and the
countries named, and drop the title. It runs only with READOUT_ALLOW_HELD=aupsc, once the AU has given written
permission.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from . import places, text

FEED = "http://www.peaceau.org/en/rss"
ISSUER = "AU"
A = "{http://www.w3.org/2005/Atom}"
WANT = re.compile(r"communiqu|press statement", re.I)
MEETING = re.compile(r"(\d{3,5})(?:st|nd|rd|th)\s+(?:\w+\s+)?meeting", re.I)
HELD_ON = re.compile(r"held on\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})", re.I)


def parse(body: bytes) -> list[dict]:
    root = ET.fromstring(body)
    out = []
    if root.tag == A + "feed":
        for e in root.findall(A + "entry"):
            ln = e.find(A + "link")
            out.append({"title": (e.findtext(A + "title") or "").strip(), "link": ln.get("href") if ln is not None
                        else "", "date": text.utc(e.findtext(A + "published") or e.findtext(A + "updated"))})
    else:
        ch = root.find("channel")
        if ch is None:
            raise ValueError("AU PSC reply is neither RSS 2.0 nor Atom")
        for it in ch.findall("item"):
            pub = it.findtext("pubDate")
            try:
                d = text.utc(parsedate_to_datetime(pub).isoformat()) if pub else None
            except (TypeError, ValueError):
                d = None
            out.append({"title": (it.findtext("title") or "").strip(), "link": (it.findtext("link") or "").strip(),
                        "date": d})
    return out


def record(e: dict) -> dict | None:
    if not WANT.search(e["title"] or "") or not e.get("link"):
        return None
    m, h = MEETING.search(e["title"]), HELD_ON.search(e["title"])
    day = text.day_words(h.group(1)) if h else (e["date"] or "")[:10] or None
    if not day:
        return None
    ccs, _, _ = places.countries_in(e["title"])
    link = e["link"].replace("http://", "https://", 1)
    return {
        "key": f"aupsc:{m.group(1) if m else link}",
        "lane": "aupsc",
        "issuer": ISSUER,
        "issuer_name": "African Union Peace and Security Council",
        "doc_type": "communique" if "communiqu" in e["title"].lower() else "press statement",
        "meeting": int(m.group(1)) if m else None,
        "title": None,  # not kept (AU terms)
        "url": link,
        "published_at": f"{day}T00:00:00Z",
        "time_precision": "day",
        "countries_mentioned": ccs,
        "excerpt": None,
        "quotes": [],
        "claims": {},
        "claim": "none",
    }


def build(entries: list[dict]) -> list[dict]:
    seen, out = set(), []
    for e in entries:
        r = record(e)
        if r and r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return sorted(out, key=lambda r: (r["published_at"], r["key"]), reverse=True)
