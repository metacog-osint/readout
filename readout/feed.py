"""Build Readout's contract-v2 feed (tic-feed/2, GeoJSON) from the collected statements.

One item per statement, communiqué or Council meeting: kind "observation". A government's statement is that party's
own claim (status_class "claimed", source grade A2: the source is the speaker, so the text is certainly what it said,
never that what it said is true). A UN Security Council meeting or an AU PSC communiqué is the body's own record of
what it did (status_class "reported").

Tier is always "routine" in readout-0.1. The say-do check (`saydo`) is shown on each item in its own `say_do` block
and on the page; RO-IND-1, the rule that would mark a candidate say-do gap, is proposed and not adopted, so it moves
no tier. `rule()` states that once; build and `check` both call it.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))
from tic_doctrine import CONTRACT, __version__ as KIT_VERSION, geo  # noqa: E402

from . import places  # noqa: E402

PROGRAM = "readout"
NAME = "Readout"
SITE = "https://readout.theintelligence.company"  # planned address; no DNS or Pages project yet
METHOD = "readout-0.1"
LANGUAGE_KEY = "https://github.com/metacog-osint/tic-doctrine/blob/main/docs/language-key.md"
CONTRACT_REV = "2.1"
MAX_PAIRS = 10

SOURCES = {
    "kremlin": {"id": "kremlin-en", "publisher": "President of Russia, official website (en.kremlin.ru)",
                "licence": "CC BY 4.0, with reference to en.kremlin.ru (photos by RIA Novosti and TASS excluded; "
                           "none kept)",
                "licence_url": "https://creativecommons.org/licenses/by/4.0/",
                "independence_group": "kremlin", "source_type": "official statement (head of state)",
                "descriptor": "The Kremlin's own English record of what the President of Russia said, signed or "
                              "did: news, transcripts, acts and letters."},
    "govuk": {"id": "govuk-news", "publisher": "UK government (GOV.UK): FCDO, Ministry of Defence, Prime Minister's "
                                               "Office",
              "licence": "Open Government Licence v3.0: contains public sector information licensed under the Open "
                         "Government Licence v3.0",
              "licence_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
              "independence_group": "uk-government", "source_type": "official statement (government)",
              "descriptor": "A UK government department's own news story, speech, press release or statement, with "
                            "GOV.UK's one-line description and its world-location tags."},
    "eeas": {"id": "eeas-press", "publisher": "European External Action Service (EEAS)",
             "licence": "EEAS legal notice: reuse authorised with acknowledgement of the source (Commission "
                        "Decision 2011/833/EU); title, date and link only",
             "independence_group": "eu-eeas", "source_type": "official statement (EU diplomatic service)",
             "descriptor": "The EU's own press release, statement, declaration or speech by the High "
                           "Representative, the spokesperson or an EU delegation."},
    "unsc": {"id": "un-press-sc", "publisher": "United Nations, Meetings Coverage and Press Releases (press.un.org)",
             "licence": "UN terms of use: personal, non-commercial use, no redistribution without permission; "
                        "number, date, link and derived outcome only (held until permission is given)",
             "independence_group": "un-dgc", "source_type": "official record (UN Security Council)",
             "descriptor": "The UN's own press release on a Security Council meeting: its number, date, what the "
                           "Council adopted or failed to adopt, and the countries it concerned."},
    "aupsc": {"id": "au-psc", "publisher": "African Union Peace and Security Department (peaceau.org)",
              "licence": "peaceau.org legal notice: no redistribution, compilation or derivative works without "
                         "written permission; held until the AU answers",
              "independence_group": "au-psd", "source_type": "official record (AU Peace and Security Council)",
              "descriptor": "The AU's own record of a Peace and Security Council communiqué or press statement: "
                            "meeting number, date and the countries it concerned."},
}
REQUIREMENT = {"kremlin": ["RO-PIR-1", "RO-EEI-1"], "govuk": ["RO-PIR-1", "RO-EEI-1"],
               "eeas": ["RO-PIR-1", "RO-EEI-1"], "unsc": ["RO-PIR-2"], "aupsc": ["RO-PIR-3"]}
STATEMENT_LANES = ("kremlin", "govuk", "eeas")
ISSUER_NAMES = {"EU": "the European Union", "UN": "the UN Security Council", "AU": "the African Union"}
CLAIM_WORDS = {"deescalation": "says fighting or a deployment is easing", "denial": "denies an act or a part in one",
               "assurance": "says its intent is not hostile", "threat": "warns of a response",
               "accusation": "accuses another party", "none": "makes none of the claims Readout reads for"}


def rule(lane: str, say_do: dict | None) -> str:
    """The tier an item gets. readout-0.1: always routine; RO-IND-1 is proposed, not adopted."""
    return "routine"


def item_id(key: str) -> str:
    lane = key.split(":", 1)[0]
    return f"RO-{lane.upper()}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:10]}"


def _name(cc: str) -> str:
    return geo.name(cc) or ISSUER_NAMES.get(cc, cc)


def countries(r: dict) -> list[str]:
    """Countries the item is about: those it names, then the issuer when the issuer is a country."""
    out = list(r.get("countries_mentioned") or [])
    if len(r.get("issuer") or "") == 2 and r["issuer"] not in ("EU", "UN", "AU") and r["issuer"] not in out:
        out.append(r["issuer"])
    return out


def _geometry(ccs: list[str]):
    pts = []
    for cc in ccs:
        p = places.point(cc)
        if p:
            pts.append([p[1], p[0]])
    if not pts:
        return None
    return {"type": "Point", "coordinates": pts[0]} if len(pts) == 1 else {"type": "MultiPoint", "coordinates": pts}


def _day_text(ts: str | None) -> str:
    if not ts:
        return "an unstated date"
    x = date.fromisoformat(ts[:10])
    return f"{x.day} {x.strftime('%b %Y')}"


def _where(ccs: list[str], most: int = 4) -> str:
    names = [_name(c) for c in ccs]
    return ", ".join(names) if len(names) <= most else ", ".join(names[:most]) + f" and {len(names) - most} more"


def say_do_sentence(sd: dict | None) -> str | None:
    if not sd:
        return None
    res, pairs = sd["result"], sd["pairs"]
    if not pairs:
        return None
    progs = sorted({p["program"] for p in pairs})
    s = (f"In the same countries within 72 hours, other TIC programs published {len(pairs)} anomaly or warning "
         f"item{'' if len(pairs) == 1 else 's'} ({', '.join(p.capitalize() for p in progs)}).")
    if res["candidate_gap"]:
        s += (" Readout lists this as a candidate say-do gap under the proposed rule RO-IND-1: a calm claim beside "
              "activity seen by at least two independent sources. That is a pointer to look, not a finding that the "
              "statement was false.")
    elif res["activity_near_threat"]:
        s += " The statement warns of a response; the items are shown for context."
    return s


def summary(r: dict, sd: dict | None = None) -> str:
    lane = r["lane"]
    if lane == "unsc":
        oc = r.get("outcome") or {}
        did = ("adopted " + ", ".join(f"resolution {x}" for x in oc["resolutions"]) if oc.get("adopted") and
               oc.get("resolutions") else "adopted a resolution" if oc.get("adopted") else
               "failed to adopt a draft resolution" if oc.get("failed") else
               "agreed a presidential statement" if oc.get("presidential_statement") else "met")
        if oc.get("unanimous"):
            did += " unanimously"
        if oc.get("veto"):
            did += "; the UN's record mentions a veto"
        where = f", on {_where(r['countries_mentioned'])}" if r.get("countries_mentioned") else ""
        return (f"The UN Security Council {did}{where} ({r['doc']}, {_day_text(r['published_at'])}). "
                f"Readout keeps the UN's number, date and link; the UN's own text is at the link.")
    if lane == "aupsc":
        where = f" on {_where(r['countries_mentioned'])}" if r.get("countries_mentioned") else ""
        num = f" of its {r['meeting']}th meeting" if r.get("meeting") else ""
        return (f"The AU Peace and Security Council issued a {r['doc_type']}{num}{where}, "
                f"{_day_text(r['published_at'])}. The AU's own text is at the link.")
    bits = [f"{r['issuer_name']} published a {r['doc_type']} on {_day_text(r['published_at'])}"
            + (f" naming {_where(r['countries_mentioned'])}." if r.get("countries_mentioned") else ".")]
    c = r.get("claim") or "none"
    if c != "none":
        words = ", ".join(f"“{w}”" for ws in r["claims"].values() for w in ws[:2])
        bits.append(f"By Readout's word list it {CLAIM_WORDS[c]} ({words}).")
    s = say_do_sentence(sd)
    if s:
        bits.append(s)
    return " ".join(bits)


def title(r: dict) -> str:
    if r["lane"] == "unsc":
        return f"UN Security Council meeting {r['doc']}"
    if r["lane"] == "aupsc":
        return f"AU PSC {r['doc_type']}" + (f", meeting {r['meeting']}" if r.get("meeting") else "")
    who = {"kremlin": "Kremlin", "govuk": "UK", "eeas": "EU"}[r["lane"]]
    return f"{who}: {r['title']}"


def feature(r: dict, generated: str, sd: dict | None = None) -> dict:
    lane = r["lane"]
    src = dict(SOURCES[lane])
    src.update({"url": r["url"], "grade": "A2", "accessed_at": generated,
                "title": r.get("title") or title(r), "published_at": r["published_at"]})
    iid = item_id(r["key"])
    ccs = countries(r)
    stmt = lane in STATEMENT_LANES
    props = {
        "contract": CONTRACT, "id": iid, "subject_id": iid, "program": PROGRAM, "kind": "observation",
        "tier": rule(lane, sd), "status": "actual", "msg_type": "new", "human_review": "none",
        # Statements name officials; Council and PSC records name states and bodies.
        "us_person_data": "individuals" if stmt else "organizations",
        "status_class": "claimed" if stmt else "reported", "product_category": "current", "published_at": generated,
        "pmesii_pt": ["political", "information"], "ie_aspect": ["informational"],
        "ascope": ["organizations", "events"], "requirement_ids": REQUIREMENT[lane], "method_version": METHOD,
        "visual": {"type": "page", "url": f"{SITE}/#{iid}"},
        "title": title(r),
        "summary": summary(r, sd),
        "data_as_of": r.get("updated_at") or r["published_at"],
        "event_start": r["published_at"],
        "countries": ccs,
        "precision_class": "country" if ccs else "none",
        "coverage_fraction": 1.0,
        "sources": [src],
        "statement": {"issuer": r["issuer"], "issuer_name": r["issuer_name"], "lane": lane,
                      "doc_type": r["doc_type"], "countries_mentioned": r.get("countries_mentioned") or [],
                      "claim": r.get("claim") or "none", "claims": r.get("claims") or {},
                      "quotes": r.get("quotes") or [], "excerpt": r.get("excerpt")},
    }
    if r.get("time_precision") == "day":
        props["data_as_of_precision"] = "day"
        props["event_time_precision"] = "day"
    if lane == "unsc":
        props["council"] = {"doc": r["doc"], **(r.get("outcome") or {})}
    if lane == "aupsc":
        props["psc"] = {"meeting": r.get("meeting"), "doc_type": r["doc_type"]}
    if sd and stmt:
        props["say_do"] = {**sd["result"], "window_hours": 72, "pairs_shown": min(len(sd["pairs"]), MAX_PAIRS),
                           "pair_items": sd["pairs"][:MAX_PAIRS]}
    if props["data_as_of"] > generated:   # contract 2.1: never after publication
        props["data_as_of"] = generated
        props.pop("data_as_of_precision", None)
    return {"type": "Feature", "geometry": _geometry(ccs), "properties": props}


def health(lanes: dict, records: list[dict], held: dict | None = None) -> dict:
    """Per-source health, keyed by the items' source id. A held lane that is not enabled reports "failing" with the
    reason, so COP shows it as not read rather than quiet."""
    newest: dict[str, str] = {}
    for r in records:
        if r["published_at"] > newest.get(r["lane"], ""):
            newest[r["lane"]] = r["published_at"]
    out = {}
    for lane, src in SOURCES.items():
        st = lanes.get(lane) or {}
        ok, failed = st.get("status") == "ok", st.get("status") == "failed"
        n = st.get("items") or 0
        if ok:
            detail = f"{n} items" + (" (last good copy, not read on this run)" if st.get("from_previous") else "")
        elif failed:
            detail = (f"not read; {n} items from the last good copy" if st.get("from_previous")
                      else "not read; no earlier copy, so no items")
        elif st.get("status") == "held":
            detail = "held: not read until its terms are cleared"
        else:
            detail = "not run yet"
        out[src["id"]] = {
            "state": "up" if ok else "failing",
            "last_ok": st.get("fetched_at"),
            "last_error": st.get("error") if failed else ("held for terms" if st.get("status") == "held" else None),
            "failures": int(st.get("failures") or 0) if (ok or failed) else 0,
            "checked_at": st.get("failed_at") if failed else (st.get("fetched_at") or st.get("checked_at")),
            "detail": detail,
            "lane": lane,
            "data_as_of": newest.get(lane),
        }
    return out


def build_feed(records: list[dict], generated: str, say_do: dict | None = None,
               health_record: dict | None = None) -> dict:
    say_do = say_do or {}
    feats = [feature(r, generated, say_do.get(r["key"])) for r in records]
    feats.sort(key=lambda f: (f["properties"]["data_as_of"], f["properties"]["id"]), reverse=True)
    doc = {
        "type": "FeatureCollection",
        "contract": CONTRACT,
        "contract_rev": CONTRACT_REV,
        "kit": KIT_VERSION,
        "program": PROGRAM,
        "generated_at": generated,
        "method_version": METHOD,
        "licence": ("Readout's own text: CC BY 4.0 (The Intelligence Company). Each item keeps its source's terms: "
                    "Kremlin, CC BY 4.0 with reference to en.kremlin.ru; GOV.UK, Open Government Licence v3.0 "
                    "(contains public sector information licensed under the Open Government Licence v3.0); EEAS, "
                    "reuse with acknowledgement (Commission Decision 2011/833/EU), title, date and link only; UN and "
                    "AU records, when enabled, number, date and link only."),
        "attribution": ("Readout, The Intelligence Company. Sources: President of Russia (en.kremlin.ru); GOV.UK "
                        "(Foreign, Commonwealth & Development Office, Ministry of Defence, Prime Minister's Office); "
                        "European External Action Service. Say-do pairs point to items of other TIC programs."),
        "language_key": LANGUAGE_KEY,
        "note": ("Official statements as their speakers published them: claims, not facts. Tier is routine for "
                 "every item. The say-do block lists other TIC programs' anomalies and warnings in the same countries "
                 "within 72 hours; a candidate say-do gap (RO-IND-1, proposed, not adopted) is a pointer to look, "
                 "not a finding that a statement was false."),
    }
    if health_record is not None:
        doc["health"] = health_record
    doc["features"] = feats
    return doc
