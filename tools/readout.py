"""Readout CLI: collect, build and check.

    python tools/readout.py collect               # fetch every enabled lane, write data/snapshot.json
    python tools/readout.py collect --only govuk  # one or more lanes; the rest keep their last copy
    python tools/readout.py build                 # build site/ from data/snapshot.json
    python tools/readout.py check                 # registers, feed linter, terms scan

Lanes: kremlin, govuk and eeas (statements, on), unsc and aupsc (held: off until their terms are cleared; enable one
with READOUT_ALLOW_HELD=unsc,aupsc), and suite (the say-do side: other TIC programs' anomalies and warnings, read from
the suite bus through the doctrine kit's tips module).

collect never falls back to made-up data. A lane that fails keeps its last good copy (from_previous) or stays empty,
and the snapshot's "lanes" block says which.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))

from readout import aupsc, eeas, feed, fetch, govuk, kremlin, saydo, unsc  # noqa: E402
from tic_doctrine import contract, registers, tips  # noqa: E402
from tic_doctrine.lint import check_header  # noqa: E402

LANES = ["kremlin", "govuk", "eeas", "unsc", "aupsc", "suite"]
HELD = ("unsc", "aupsc")
STATEMENT_LANES = ["kremlin", "govuk", "eeas", "unsc", "aupsc"]
HELD_ENV = "READOUT_ALLOW_HELD"


def held_enabled(env: dict) -> set[str]:
    return {x.strip() for x in (env.get(HELD_ENV) or "").split(",") if x.strip()}


def _lane_kremlin(raw_dir, now, getter, env):
    entries, recs = [], []
    for url in kremlin.page_urls():
        body, rec = fetch.fetch("kremlin-en", url, raw_dir, "xml", timeout=60, getter=getter, gz=True)
        recs.append(rec)
        entries += kremlin.parse(body)
    records = kremlin.build(entries)
    if len(records) < 5:
        raise ValueError(f"Kremlin feed gave only {len(records)} usable entries")
    return {"records": records, "extra": {"entries_read": len(entries)}}, recs


def _lane_govuk(raw_dir, now, getter, env):
    pages, recs = {}, []
    for org in govuk.ORGS:
        body, rec = fetch.fetch("govuk-news", govuk.url_for(org), raw_dir, "json", timeout=60, getter=getter, gz=True)
        recs.append(rec)
        pages[org] = govuk.parse(body)
    records = govuk.build(pages)
    if len(records) < 10:
        raise ValueError(f"GOV.UK search gave only {len(records)} items for three departments")
    return {"records": records, "extra": {"per_department": {o: len(v) for o, v in pages.items()}}}, recs


def _lane_eeas(raw_dir, now, getter, env):
    cards, recs = [], []
    for i, url in enumerate(eeas.page_urls()):
        try:
            body, rec = fetch.fetch("eeas-press", url, raw_dir, "html", timeout=60, getter=getter, gz=True)
        except Exception:
            if i == 0:
                raise
            break  # a later page failing leaves the first page's cards
        recs.append(rec)
        cards += eeas.parse(body)
    records = eeas.build(cards)
    undated = sum(1 for c in cards if not c.get("day"))
    if not records:
        raise ValueError("EEAS page read but no dated cards")
    return {"records": records, "extra": {"cards_read": len(cards), "undated": undated}}, recs


def _lane_unsc(raw_dir, now, getter, env):
    cards, recs = [], []
    for url in unsc.page_urls():
        body, rec = fetch.fetch("un-press-sc", url, raw_dir, "html", timeout=60, getter=getter, gz=True)
        recs.append(rec)
        cards += unsc.parse(body)
    return {"records": unsc.build(cards), "extra": {"cards_read": len(cards)}}, recs


def _lane_aupsc(raw_dir, now, getter, env):
    body, rec = fetch.fetch("au-psc", aupsc.FEED, raw_dir, "xml", timeout=60, getter=getter, gz=True)
    entries = aupsc.parse(body)
    return {"records": aupsc.build(entries), "extra": {"entries_read": len(entries)}}, [rec]


def interests() -> dict:
    return json.loads((ROOT / "doctrine" / "interests.json").read_text(encoding="utf-8"))


def _lane_suite(raw_dir, now, getter, env, prev_tips=None):
    recs = []

    def load(src):
        """tips.load, but through fetch.fetch, so the raw reply is kept and a test can supply it."""
        if getter is None and not re.match(r"^https?://", src):
            return tips.load(src)
        body, rec = fetch.fetch("tic-suite", src, raw_dir, "json", timeout=90, getter=getter, gz=True)
        recs.append(rec)
        with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as fh:
            fh.write(body)
        try:
            return tips.load(fh.name)
        finally:
            os.unlink(fh.name)

    doc = interests()
    bus = env.get("READOUT_BUS") or None
    items, problems = tips.gather(doc, bus=bus, fetch=load)
    if not items:
        raise ValueError("no suite items read: " + "; ".join(p["error"] for p in problems)[:200])
    nowd = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(timezone.utc)
    found = [saydo.compact(t, now) for t in tips.tips(items, doc, nowd)]
    merged = saydo.merge(prev_tips or [], found, now)
    return {"records": merged, "extra": {"items_read": len(items), "tips_now": len(found),
                                         "tips_kept": len(merged), "problems": problems}}, recs


LANE_FN = {"kremlin": _lane_kremlin, "govuk": _lane_govuk, "eeas": _lane_eeas, "unsc": _lane_unsc,
           "aupsc": _lane_aupsc, "suite": _lane_suite}


def collect(root: Path = ROOT, getter=None, only: list[str] | None = None, now: str | None = None,
            env: dict | None = None) -> dict:
    data_dir = root / "data"
    raw_dir = data_dir / "raw"
    snap_path = data_dir / "snapshot.json"
    prev = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {}
    now = now or fetch.now_utc()
    env = dict(os.environ) if env is None else env
    allowed = held_enabled(env)
    snap = {"generated_at": now, "method_version": feed.METHOD, "lanes": {}, "records": {}, "extra": {}}
    for lane in LANES:
        prev_lane = (prev.get("lanes") or {}).get(lane) or {}
        prev_recs = (prev.get("records") or {}).get(lane, [])
        keep = lambda: (prev_recs, (prev.get("extra") or {}).get(lane, {}))  # noqa: E731
        if lane in HELD and lane not in allowed:
            snap["records"][lane], snap["extra"][lane] = [], {}
            snap["lanes"][lane] = {"status": "held", "items": 0, "checked_at": now,
                                   "note": f"terms not cleared; set {HELD_ENV}={lane} to read"}
            continue
        if only and lane not in only:
            snap["records"][lane], snap["extra"][lane] = keep()
            snap["lanes"][lane] = {**prev_lane, "from_previous": True} if prev_lane else {"status": "not run"}
            continue
        try:
            fn = LANE_FN[lane]
            result, recs = (fn(raw_dir, now, getter, env, prev_recs) if lane == "suite"
                            else fn(raw_dir, now, getter, env))
            snap["records"][lane] = result["records"]
            snap["extra"][lane] = result["extra"]
            snap["lanes"][lane] = {"status": "ok", "fetched_at": now, "from_previous": False,
                                   "items": len(result["records"]), "failures": 0,
                                   "fetches": [{k: r[k] for k in ("url", "sha256", "bytes")} for r in recs]}
        except Exception as exc:
            had = bool(prev_lane.get("fetched_at"))
            snap["records"][lane], snap["extra"][lane] = keep() if had else ([], {})
            snap["lanes"][lane] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300],
                                   "failed_at": now, "from_previous": had, "fetched_at": prev_lane.get("fetched_at"),
                                   "items": len(snap["records"][lane]),
                                   "failures": int(prev_lane.get("failures") or 0) + 1}
    data_dir.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(json.dumps(snap, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return snap


def statements(snap: dict) -> list[dict]:
    return [r for lane in STATEMENT_LANES for r in (snap.get("records") or {}).get(lane, [])]


def suite_tips(snap: dict) -> list[dict]:
    return (snap.get("records") or {}).get("suite", [])


def page_data(snap: dict, records: list[dict], sd: dict) -> dict:
    rows = []
    for r in records:
        iid = feed.item_id(r["key"])
        s = sd.get(r["key"]) or {"pairs": [], "result": saydo.rule(r, [])}
        rows.append({"id": iid, **{k: v for k, v in r.items() if k != "key"}, "countries": feed.countries(r),
                     "title_shown": feed.title(r), "summary": feed.summary(r, s),
                     "say_do": {**s["result"], "pair_items": s["pairs"][:feed.MAX_PAIRS]}})
    ccs = sorted({c for r in rows for c in r["countries"]} | {c for t in suite_tips(snap) for c in t.get("countries") or []})
    claims_n = {}
    for r in rows:
        claims_n[r.get("claim") or "none"] = claims_n.get(r.get("claim") or "none", 0) + 1
    return {"generated_at": snap["generated_at"], "method_version": snap["method_version"], "name": feed.NAME,
            "lanes": {k: {kk: vv for kk, vv in v.items() if kk != "fetches"} for k, v in snap["lanes"].items()},
            "extra": snap.get("extra") or {}, "items": rows, "claims": claims_n,
            "tips": suite_tips(snap)[:300], "window_hours": saydo.WINDOW_HOURS,
            "country_names": {c: feed._name(c) for c in ccs}}  # noqa: SLF001


def build_site(root: Path = ROOT, snapshot: dict | None = None) -> dict[str, str]:
    snap_path = root / "data" / "snapshot.json"
    if snapshot is None:
        if not snap_path.exists():
            raise SystemExit("No data/snapshot.json. Run `python tools/readout.py collect` first; "
                             "Readout does not build from made-up data.")
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    snap = snapshot
    records = statements(snap)
    sd = saydo.check(records, suite_tips(snap))
    feed_doc = feed.build_feed(records, snap["generated_at"], sd, feed.health(snap.get("lanes") or {}, records))

    def dump(obj) -> str:
        return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

    files = {"data/feed.geojson": dump(feed_doc), "data/snapshot.json": dump(page_data(snap, records, sd))}
    src_dir = root / "site_src"
    if src_dir.exists():
        for p in sorted(src_dir.rglob("*")):
            if p.is_file():
                files[p.relative_to(src_dir).as_posix()] = p.read_text(encoding="utf-8")
    for p in sorted((root / "doctrine").glob("*.md")):
        files[f"doctrine/{p.name}"] = p.read_text(encoding="utf-8")
    out_dir = root / "site"
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel, txt in files.items():
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(txt, encoding="utf-8", newline="\n")
    return files


# Links the published output may carry: the publishers' own pages, the suite's sites and the references cited.
ALLOWED_URL_PREFIXES = (
    "https://en.kremlin.ru/", "https://www.gov.uk/", "https://www.nationalarchives.gov.uk/doc/open-government-licence/",
    "https://www.eeas.europa.eu/", "https://www.consilium.europa.eu/", "https://ec.europa.eu/",
    "https://commission.europa.eu/", "https://press.un.org/en/", "https://www.peaceau.org/",
    "https://readout.theintelligence.company", "https://theintelligence.company",
    "https://github.com/metacog-osint/", "https://creativecommons.org/",
)
SUITE_HOST = re.compile(r"^https://[a-z0-9-]+\.theintelligence\.company(/|$)")
URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>)\]]+")
# Kept out of the published output: UN and AU text (their terms), Kremlin images (RIA/TASS), raw feed bodies.
BANNED_FIELDS = ("heading", "lede", "content", "content_html", "body")
BANNED_MARKERS = ("static.kremlin.ru", "<img", "[fixture: UN text]", "[fixture: AU text]")
EXCERPT_LANES_ALLOWED = ("kremlin", "govuk")


def terms_scan(paths: list[Path]) -> list[str]:
    errs = []
    for p in paths:
        txt = p.read_text(encoding="utf-8")
        for f in BANNED_FIELDS:
            if f'"{f}"' in txt:
                errs.append(f"{p.name}: field {f} is in the published output")
        for m in BANNED_MARKERS:
            if m in txt:
                errs.append(f"{p.name}: {m!r} is in the published output (UN or AU text, or a Kremlin image)")
        for m in URL_IN_TEXT.finditer(txt):
            u = m.group(0)
            if not (u.startswith(ALLOWED_URL_PREFIXES) or SUITE_HOST.match(u)):
                errs.append(f"{p.name}: URL outside the allowed publisher pages: {u[:80]}")
        if p.suffix in (".json", ".geojson"):
            doc = json.loads(txt)
            for row in _rows(doc):
                lane = row.get("lane") or (row.get("statement") or {}).get("lane")
                st = row.get("statement") or row
                if lane not in EXCERPT_LANES_ALLOWED and (st.get("excerpt") or st.get("quotes")):
                    errs.append(f"{p.name}: {lane} item carries text, which its terms do not allow")
                if lane in ("unsc", "aupsc") and row.get("lane") and row.get("title"):
                    errs.append(f"{p.name}: {lane} item carries the publisher's title")
    return errs


def _rows(doc: dict) -> list[dict]:
    if doc.get("type") == "FeatureCollection":
        return [f.get("properties") or {} for f in doc.get("features") or []]
    return list(doc.get("items") or [])


def check_all(root: Path = ROOT) -> list[str]:
    errs = registers.check(root / "doctrine")
    errs += [f"interests.json: {e}" for e in tips.check_interests(json.loads(
        (root / "doctrine" / "interests.json").read_text(encoding="utf-8")))]
    regs = registers.ids(root / "doctrine")
    data = root / "site" / "data"
    feed_path = data / "feed.geojson"
    if not feed_path.exists():
        return errs + ["site/data/feed.geojson is missing: run collect and build first"]
    doc = json.loads(feed_path.read_text(encoding="utf-8"))
    errs += [f"feed header: {std}: {msg}" for std, sev, msg in check_header(doc) if sev == "error"]
    for feat in doc.get("features", []):
        p = feat.get("properties") or {}
        for std, sev, msg in contract.check(feat, regs):
            if sev == "error":
                errs.append(f"{p.get('id', '?')}: {std}: {msg}")
        if p.get("kind") != "observation":
            errs.append(f"{p.get('id')}: Readout publishes observations only")
        if p.get("tier") != feed.rule((p.get("statement") or {}).get("lane"), p.get("say_do")):
            errs.append(f"{p.get('id')}: tier {p.get('tier')} is not what feed.rule gives (routine in readout-0.1)")
        sd = p.get("say_do")
        if sd and sd.get("candidate_gap") != bool(sd.get("calm") and len(sd.get("groups") or []) >= saydo.MIN_GROUPS):
            errs.append(f"{p.get('id')}: say_do.candidate_gap does not match RO-IND-1 as proposed")
    scan = [data / "feed.geojson", data / "snapshot.json", data / "ended.geojson"]
    errs += terms_scan([p for p in scan if p.exists()] + sorted((root / "history").rglob("*.jsonl")))
    return errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Readout: official statements, Security Council votes and AU "
                                             "communiqués, with a say-do check against the suite.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--only", nargs="*", choices=LANES)
    sub.add_parser("build")
    sub.add_parser("check")
    args = ap.parse_args(argv)
    if args.cmd == "collect":
        snap = collect(only=args.only)
        for lane, st in snap["lanes"].items():
            extra = f" ({st.get('error') or st.get('note')})" if st.get("status") in ("failed", "held") else ""
            print(f"  {lane:8s} {st.get('status')} {st.get('items', '')}"
                  f"{' [last good copy]' if st.get('from_previous') else ''}{extra}")
        return 0 if any(s.get("status") == "ok" for s in snap["lanes"].values()) else 1
    if args.cmd == "build":
        print(f"Built site/ ({len(build_site(ROOT))} files).")
        return 0
    if args.cmd == "check":
        errs = check_all(ROOT)
        for e in errs[:60]:
            print("  -", e)
        print(f"Readout check: {'PASS' if not errs else f'FAIL ({len(errs)} problems)'}")
        return 1 if errs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
