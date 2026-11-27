"""Small text helpers shared by the lanes: HTML to plain text, dates, and a flat reader for listing pages."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def plain(fragment: str | None) -> str:
    """HTML fragment to one line of text: tags dropped (images with them), entities decoded, spaces folded."""
    if not fragment:
        return ""
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragment)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", " ", s)
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", s))).strip()


def utc(ts: str | None) -> str | None:
    """Any ISO 8601 time with an offset ('2026-11-25T20:30:00+04:00', '...Z') -> '2026-11-25T16:30:00Z'."""
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_words(s: str) -> str | None:
    """'24 November 2026' -> '2026-11-24'; None if it is not that form."""
    m = re.fullmatch(r"\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*", s or "")
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


def day_dots(s: str) -> str | None:
    """'25.11.2026' -> '2026-11-25'."""
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*", s or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


class Flat(HTMLParser):
    """A page as a flat list of events: ("text", s), ("h3", None) / ("/h3", None), ("a", href) / ("/a", None),
    ("time", datetime-attr). Enough to read a listing page by order, without depending on its CSS classes."""

    KEEP = {"h2", "h3", "h4", "a", "time", "article", "li"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events: list[tuple[str, str | None]] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            return
        if tag in self.KEEP:
            a = dict(attrs)
            self.events.append((tag, a.get("href") if tag == "a" else a.get("datetime") if tag == "time" else None))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
            return
        if tag in self.KEEP:
            self.events.append(("/" + tag, None))

    def handle_data(self, data):
        if self._skip:
            return
        s = _WS.sub(" ", data).strip()
        if s:
            self.events.append(("text", s))


def flat(body: bytes | str) -> list[tuple[str, str | None]]:
    p = Flat()
    p.feed(body.decode("utf-8", "replace") if isinstance(body, bytes) else body)
    p.close()
    return p.events


def headed_links(events, heading: str = "h3") -> list[dict]:
    """Each link inside a heading, with the texts (and <time datetime> values) between the previous heading and
    this one (`before`, `times_before`) and between this heading and the next (`after`, `times_after`). Listing
    pages put a card's label and date around its heading; reading by order keeps the parser free of CSS class
    names that change with a redesign. A heading with no link is skipped."""
    spans, cur, heads = [[]], None, []
    for kind, val in events:
        if kind == heading:
            cur = {"href": None, "title": [], "in_a": False}
            continue
        if cur is not None:
            if kind == "/" + heading:
                heads.append(cur)
                spans.append([])
                cur = None
            elif kind == "a" and cur["href"] is None:
                cur["href"], cur["in_a"] = val, True
            elif kind == "/a":
                cur["in_a"] = False
            elif kind == "text" and cur["in_a"]:
                cur["title"].append(val)
            continue
        if kind in ("text", "time"):
            spans[-1].append((kind, val))
    out = []
    for i, h in enumerate(heads):
        if not h["href"]:
            continue
        b, a = spans[i], spans[i + 1]
        out.append({"href": h["href"], "title": " ".join(h["title"]).strip(),
                    "before": [v for k, v in b if k == "text"], "after": [v for k, v in a if k == "text"],
                    "times_before": [v for k, v in b if k == "time" and v],
                    "times_after": [v for k, v in a if k == "time" and v]})
    return out
