"""UK government: news, speeches and statements from three departments, from GOV.UK's public search API (no key).

    https://www.gov.uk/api/search.json?filter_organisations=<slug>
        &filter_content_purpose_supergroup=news_and_communications&order=-public_timestamp&count=40&fields=...

Departments: the Foreign, Commonwealth and Development Office, the Ministry of Defence and the Prime Minister's
Office. Terms: GOV.UK content is under the Open Government Licence v3.0 (footer of every page): reuse with the
attribution "Contains public sector information licensed under the Open Government Licence v3.0." Readout keeps the
title, GOV.UK's one-line description, the link, the time, the document type and GOV.UK's own world-location tags.
"""
from __future__ import annotations

import json
import urllib.parse

from . import claims, places, text

API = "https://www.gov.uk/api/search.json"
BASE = "https://www.gov.uk"
ORGS = {
    "foreign-commonwealth-development-office": "Foreign, Commonwealth & Development Office",
    "ministry-of-defence": "Ministry of Defence",
    "prime-ministers-office-10-downing-street": "Prime Minister's Office, 10 Downing Street",
}
FIELDS = ("title", "description", "link", "public_timestamp", "content_store_document_type", "organisations",
          "world_locations")
COUNT = 40
ISSUER = "GB"
# Document types that carry no statement of position (job adverts, consultations, transparency data).
SKIP_TYPES = {"official_statistics", "transparency", "corporate_report", "foi_release", "consultation_outcome",
              "open_consultation", "closed_consultation"}
# GOV.UK world-location slugs that are not a country (or name a delegation to an organisation).
LOCATION_NOT_COUNTRY = ("uk-and-the-", "uk-mission-to-", "uk-joint-delegation-", "the-uk-permanent-", "overseas-")


def url_for(org: str) -> str:
    q = {"filter_organisations": org, "filter_content_purpose_supergroup": "news_and_communications",
         "order": "-public_timestamp", "count": str(COUNT), "fields": ",".join(FIELDS)}
    return API + "?" + urllib.parse.urlencode(q, safe=",")


def parse(body: bytes) -> list[dict]:
    doc = json.loads(body.decode("utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        raise ValueError("GOV.UK reply has no results list")
    return doc["results"]


def _slugs(v) -> list[str]:
    out = []
    for x in v or []:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            s = x.get("slug") or x.get("link", "").rstrip("/").rsplit("/", 1)[-1] or x.get("title")
            if s:
                out.append(s)
    return out


def location_countries(slugs: list[str]) -> list[str]:
    out = []
    for s in slugs:
        if s.startswith(LOCATION_NOT_COUNTRY):
            continue
        ccs, _, _ = places.countries_in(s.replace("-", " "))
        for c in ccs:
            if c not in out:
                out.append(c)
    return out


def record(r: dict, org: str) -> dict | None:
    if not r.get("title") or not r.get("link") or not r.get("public_timestamp"):
        return None
    if r.get("content_store_document_type") in SKIP_TYPES:
        return None
    link = r["link"] if r["link"].startswith("http") else BASE + r["link"]
    if not link.startswith(BASE + "/"):
        return None
    desc = (r.get("description") or "").strip()
    full = f"{r['title']}. {desc}"
    cls = claims.classify(full)
    tagged = location_countries(_slugs(r.get("world_locations")))
    found, _, _ = places.countries_in(full)
    mentioned = tagged + [c for c in found if c not in tagged and c != ISSUER] + \
        ([ISSUER] if ISSUER in found and ISSUER not in tagged else [])
    return {
        "key": "govuk:" + link[len(BASE):],
        "lane": "govuk",
        "issuer": ISSUER,
        "issuer_name": "UK government (" + ", ".join(ORGS[o] for o in [org]) + ")",
        "departments": [org],
        "doc_type": (r.get("content_store_document_type") or "news").replace("_", " "),
        "title": r["title"].strip(),
        "url": link,
        "published_at": text.utc(r["public_timestamp"]),
        "time_precision": "second",
        "countries_mentioned": mentioned,
        "countries_tagged": tagged,
        "excerpt": desc or None,
        "quotes": [],
        "claims": cls,
        "claim": claims.primary(cls),
    }


def build(pages: dict[str, list[dict]]) -> list[dict]:
    """pages: {org slug: results}. One item may be tagged by several departments; it is kept once, with all."""
    by_key: dict[str, dict] = {}
    for org, results in pages.items():
        for r in results:
            rec = record(r, org)
            if not rec or not rec["published_at"]:
                continue
            if rec["key"] in by_key:
                old = by_key[rec["key"]]
                if org not in old["departments"]:
                    old["departments"].append(org)
                    old["issuer_name"] = "UK government (" + ", ".join(ORGS[o] for o in old["departments"]) + ")"
                continue
            by_key[rec["key"]] = rec
    return sorted(by_key.values(), key=lambda r: (r["published_at"], r["key"]), reverse=True)
