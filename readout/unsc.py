"""UN Security Council meetings and votes, from the UN's meetings coverage listing. HELD: off unless enabled.

    https://press.un.org/en/content/security-council/meetings-coverage  (HTML listing, newest first)

Each card has a date ("24 November 2026"), a press release number (SC/16518), a linked heading and a lede. The
heading says what the Council did: "Adopting Resolution 2838 (2026)", "Unanimously", "Fails to Adopt",
"vetoes", and the countries it is about.

Terms: the UN's terms of use allow personal, non-commercial use and forbid redistribution without permission.
Headwind (the suite's sanctions program) already publishes UN press releases as number, date and link only, and
Readout does the same: the document number, date, link, resolution numbers, an outcome flag and the countries named
are kept; the heading and lede are read to derive those, then dropped. Whether even that is allowed for a public
site needs the UN's permission, so the lane runs only with READOUT_ALLOW_HELD=unsc.

Vote counts and how each member voted come from the UN Digital Library, whose terms forbid automated downloads
without the Library's approval: not fetched here (permission not yet given).
"""
from __future__ import annotations

import re

from . import places, text

LIST = "https://press.un.org/en/content/security-council/meetings-coverage"
PAGE = LIST + "?page={n}"
PAGES = 2
BASE = "https://press.un.org"
ISSUER = "UN"
DOC = re.compile(r"^SC/\d{4,6}$")
RES = re.compile(r"Resolutions?\s+((?:\d{4}\s*\(\d{4}\)(?:\s*(?:,|and)\s*)?)+)", re.I)
RES_NUM = re.compile(r"(\d{4})\s*\((\d{4})\)")


def page_urls() -> list[str]:
    return [LIST] + [PAGE.format(n=n) for n in range(1, PAGES)]


def outcome(title: str) -> dict:
    t = title.lower()
    fails = bool(re.search(r"fail(s|ed)? to adopt|not adopted|rejects? draft", t))
    veto = bool(re.search(r"\bveto", t))
    adopted = (not fails) and bool(re.search(r"adopt(s|ing|ed)?\b", t)) and "resolution" in t
    statement = "presidential statement" in t or "press statement" in t
    res = []
    for m in RES.finditer(title):
        res += [f"{a} ({b})" for a, b in RES_NUM.findall(m.group(1))]
    return {"adopted": adopted, "unanimous": adopted and "unanimous" in t, "failed": fails, "veto": veto,
            "presidential_statement": statement, "resolutions": res}


def parse(body: bytes) -> list[dict]:
    cards = []
    for c in text.headed_links(text.flat(body), "h3"):
        href = c["href"] or ""
        m = re.search(r"/en/(\d{4})/sc(\d+)\.doc\.htm$", href)
        if not m:
            continue
        doc = next((t for t in reversed(c["before"]) if DOC.match(t)), f"SC/{m.group(2)}")
        day = next((d for d in (text.day_words(t) for t in reversed(c["before"])) if d), None)
        cards.append({"doc": doc, "day": day, "url": BASE + href if href.startswith("/") else href,
                      "heading": c["title"]})
    if not cards:
        raise ValueError("UN meetings coverage page: no SC cards read (layout changed?)")
    return cards


def record(c: dict) -> dict | None:
    if not c.get("day"):
        return None
    ccs, _, _ = places.countries_in(c["heading"])
    oc = outcome(c["heading"])
    return {
        "key": f"unsc:{c['doc']}",
        "lane": "unsc",
        "issuer": ISSUER,
        "issuer_name": "UN Security Council",
        "doc_type": "meeting",
        "doc": c["doc"],
        "title": None,   # not kept (UN terms); the page shows the number and links to the UN
        "url": c["url"],
        "published_at": f"{c['day']}T00:00:00Z",
        "time_precision": "day",
        "countries_mentioned": ccs,
        "outcome": oc,
        "excerpt": None,
        "quotes": [],
        "claims": {},
        "claim": "none",
    }


def build(cards: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in cards:
        r = record(c)
        if r and r["key"] not in seen:
            seen.add(r["key"])
            out.append(r)
    return sorted(out, key=lambda r: (r["published_at"], r["key"]), reverse=True)
