"""European External Action Service (EEAS): press releases, statements and speeches, from its press-material page.

    https://www.eeas.europa.eu/eeas/press-material_en  (HTML listing, newest first; no feed or API)

Each card on the page has a category ("Press release", "Statement/Declaration", "Speech/Remark", ...), a linked
heading and a date written dd.mm.yyyy. The parser reads the page in order (label, heading, date) instead of by CSS
class, so a redesign that keeps that order still parses. A read that finds no cards fails the lane: an empty page is
never published as "no statements".

Terms: the EEAS legal notice authorises reuse with acknowledgement of the source (Commission Decision 2011/833/EU).
Readout keeps the title, category, date and link; no statement text is copied. The issuer is the EU (its High
Representative or spokesperson), which has no ISO country code, so items are placed by the countries they name.
"""
from __future__ import annotations

from . import claims, places, text

LIST = "https://www.eeas.europa.eu/eeas/press-material_en"
PAGES = 2
PAGE = LIST + "?page={n}"
BASE = "https://www.eeas.europa.eu"
LABELS = ("Press release", "Statement/Declaration", "Speech/Remark", "Other", "Media advisory", "Article",
          "Opinion", "Interview", "Statement", "Declaration", "Speech", "Remarks")
ISSUER = "EU"


def page_urls() -> list[str]:
    return [LIST] + [PAGE.format(n=n) for n in range(1, PAGES)]


def _label(texts: list[str]) -> str | None:
    for t in reversed(texts):
        if t in LABELS:
            return t
    return None


def _day(texts: list[str], first: bool) -> str | None:
    seq = texts if first else list(reversed(texts))
    for t in seq:
        d = text.day_dots(t)
        if d:
            return d
    return None


def parse(body: bytes) -> list[dict]:
    cards = []
    for c in text.headed_links(text.flat(body), "h3"):
        label = _label(c["before"])
        href = c["href"] or ""
        if not label or not c["title"] or href.startswith(("#", "javascript:", "mailto:")):
            continue
        day = _day(c["after"], True) or _day(c["before"], False)
        url = href if href.startswith("http") else BASE + (href if href.startswith("/") else "/" + href)
        cards.append({"label": label, "title": c["title"], "url": url, "day": day})
    if not cards:
        raise ValueError("EEAS press-material page: no cards read (layout changed?)")
    return cards


def record(c: dict) -> dict | None:
    if not c.get("day") or not c["url"].startswith("https://"):
        return None
    cls = claims.classify(c["title"])
    ccs, _, _ = places.countries_in(c["title"])
    slug = c["url"].split("://", 1)[1].split("?", 1)[0]
    return {
        "key": f"eeas:{slug}",
        "lane": "eeas",
        "issuer": ISSUER,
        "issuer_name": "European Union (EEAS)",
        "doc_type": c["label"].lower(),
        "title": c["title"],
        "url": c["url"],
        "published_at": f"{c['day']}T00:00:00Z",
        "time_precision": "day",
        "countries_mentioned": ccs,
        "excerpt": None,
        "quotes": [],
        "claims": cls,
        "claim": claims.primary(cls),
    }


def build(cards: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in cards:
        r = record(c)
        if r and r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return sorted(out, key=lambda r: (r["published_at"], r["key"]), reverse=True)
