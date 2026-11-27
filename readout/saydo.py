"""The say-do check: what a statement says, held against what the suite's own sensors saw in the same places.

"Say" is a Readout statement whose claim words (`claims`) say less will happen: a ceasefire, a denial, an assurance.
"Do" is a tip: an anomaly or warning another TIC program published (Watchfloor, Noisefloor, Wake, Blackout, Cordon,
Launch), read from the suite bus (COP's merged snapshot) through the doctrine kit's tips module, never collected
again here (registry rule: each dataset is collected once, by its owner).

A pair is a tip that shares a country with what the statement names and whose data_as_of is within WINDOW_HOURS of
the statement, before or after. Readout lists the pairs under the statement, with how many hours apart they are.

RO-IND-1 (PROPOSED, not adopted): a calm claim paired with tips from at least MIN_GROUPS independence
groups is marked a candidate say-do gap on the page. It does not change the item's tier, which stays "routine":
co-occurrence in a country within three days is not evidence that the statement was false (assumption RO-A-2). A
threat paired with tips is shown as "activity near a threat", for information only.

The bus carries only what is current, so tips are kept in the snapshot for KEEP_DAYS: a statement from two days ago
still finds the tips seen yesterday.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import claims

WINDOW_HOURS = 72
MIN_GROUPS = 2
KEEP_DAYS = 14
TIP_FIELDS = ("program", "item_id", "title", "tier", "kind", "status_class", "countries", "data_as_of",
              "published_at", "link", "stale", "interest_id")


def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def group_of(tip: dict) -> str:
    """The independence group a tip counts under: its upstream sources' groups, else its program."""
    groups = sorted({u.get("independence_group") for u in tip.get("upstream") or [] if u.get("independence_group")})
    return "+".join(groups) if groups else tip["program"]


def compact(tip: dict, seen_at: str) -> dict:
    out = {k: tip.get(k) for k in TIP_FIELDS}
    out["group"] = group_of(tip)
    out["seen_at"] = seen_at
    return out


def merge(previous: list[dict], current: list[dict], now: str) -> list[dict]:
    """Current tips plus earlier ones still inside KEEP_DAYS (by data_as_of), one per program and item."""
    cut = _t(now) - timedelta(days=KEEP_DAYS)
    by = {}
    for t in previous or []:
        d = _t(t.get("data_as_of"))
        if d and d >= cut:
            by[(t["program"], t["item_id"])] = {**t, "kept": True}
    for t in current:
        by[(t["program"], t["item_id"])] = {**t, "kept": False}
    return sorted(by.values(), key=lambda t: (t.get("data_as_of") or "", t["program"], t["item_id"] or ""),
                  reverse=True)


def span(statement: dict) -> tuple[datetime, datetime] | None:
    """The statement's time as an interval: its second, or the whole day for a day-precision date."""
    s = _t(statement.get("published_at"))
    if not s:
        return None
    if statement.get("time_precision") == "day":
        return s, s + timedelta(days=1)
    return s, s


def pairs_for(statement: dict, tips: list[dict]) -> list[dict]:
    ccs = set(statement.get("countries_mentioned") or [])
    sp = span(statement)
    if not ccs or not sp:
        return []
    lo, hi = sp[0] - timedelta(hours=WINDOW_HOURS), sp[1] + timedelta(hours=WINDOW_HOURS)
    out = []
    for t in tips:
        d = _t(t.get("data_as_of"))
        shared = sorted(ccs & set(t.get("countries") or []))
        if not d or not shared or not (lo <= d <= hi):
            continue
        hours = 0.0 if sp[0] <= d <= sp[1] else ((d - sp[1]) if d > sp[1] else (d - sp[0])).total_seconds() / 3600
        out.append({"program": t["program"], "item_id": t["item_id"], "title": t.get("title"), "tier": t.get("tier"),
                    "status_class": t.get("status_class"), "countries": shared, "data_as_of": t["data_as_of"],
                    "link": t.get("link"), "stale": bool(t.get("stale")), "group": t.get("group") or t["program"],
                    "hours_from_statement": round(hours, 1)})
    out.sort(key=lambda p: (abs(p["hours_from_statement"]), p["program"], p["item_id"] or ""))
    return out


def rule(statement: dict, pairs: list[dict]) -> dict:
    """What the say-do check shows for a statement. `candidate_gap` is RO-IND-1 as proposed (not adopted)."""
    cls = statement.get("claims") or {}
    live = [p for p in pairs if not p["stale"]]
    groups = sorted({p["group"] for p in live})
    calm = claims.is_calm(cls)
    return {
        "claim": statement.get("claim") or "none",
        "calm": calm,
        "pairs": len(pairs),
        "groups": groups,
        "programs": sorted({p["program"] for p in live}),
        "candidate_gap": bool(calm and len(groups) >= MIN_GROUPS),
        "activity_near_threat": bool("threat" in cls and live),
        "indicator": "RO-IND-1" if calm and len(groups) >= MIN_GROUPS else None,
        "indicator_status": "proposed",
    }


def check(statements: list[dict], tips: list[dict]) -> dict[str, dict]:
    """{statement key: {"pairs": [...], "result": {...}}} for every statement that names a country."""
    out = {}
    for s in statements:
        ps = pairs_for(s, tips)
        out[s["key"]] = {"pairs": ps, "result": rule(s, ps)}
    return out
