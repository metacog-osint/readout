"""Readout tests: the lanes' parsers, the claim word list, the say-do check, the feed contract and the terms scan,
on hand-made fixtures in each source's shape (tests/fixtures; made-up statements, not real ones)."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "doctrine" / "kit" / "python"))
sys.path.insert(0, str(ROOT / "tests"))

from readout import aupsc, claims, eeas, feed, govuk, kremlin, places, saydo, text, unsc  # noqa: E402
from tic_doctrine import contract, registers, tips  # noqa: E402

from fixture_getter import FIX, getter  # noqa: E402

# The CLI (tools/readout.py) shares its name with the package, so it is loaded by path, not by import.
_spec = importlib.util.spec_from_file_location("readout_cli", ROOT / "tools" / "readout.py")
cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cli)

NOW = "2026-11-25T23:00:00Z"
ALL = {"READOUT_ALLOW_HELD": "unsc,aupsc"}


def workdir() -> Path:
    d = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "doctrine", d / "doctrine")
    shutil.copytree(ROOT / "site_src", d / "site_src")
    return d


class Places(unittest.TestCase):
    def test_demonyms_capitals_and_set_forms(self):
        self.assertEqual(places.countries_in("Press statements following Russian-Bruneian talks")[0], ["RU", "BN"])
        self.assertEqual(places.countries_in("the Kiev regime has not stopped")[0], ["UA"])
        self.assertEqual(places.countries_in("drones crossed into Polish airspace")[0], ["PL"])
        self.assertEqual(places.countries_in("South Sudan and Sudan")[0], ["SS", "SD"])
        self.assertEqual(places.countries_in("Niger and Nigeria")[0], ["NE", "NG"])

    def test_words_that_name_no_one_country(self):
        self.assertEqual(places.countries_in("European and African partners, Congolese forces")[0], [])


class Claims(unittest.TestCase):
    def test_classes_and_words(self):
        c = claims.classify("Reports are baseless and fabricated. Our exercises are purely defensive.")
        self.assertEqual(c["denial"], ["baseless", "fabricated"])
        self.assertIn("assurance", c)
        self.assertTrue(claims.is_calm(c))
        self.assertEqual(claims.primary(c), "denial")

    def test_threat_is_not_calm(self):
        c = claims.classify("Attacks will be met with a mirror response.")
        self.assertIn("threat", c)
        self.assertFalse(claims.is_calm(c))

    def test_known_misreading_is_documented_not_hidden(self):
        # A negation still reads as de-escalation (RO-ASM-1): the page shows the word so a reader can see why.
        self.assertIn("deescalation", claims.classify("There will be no ceasefire."))

    def test_none(self):
        self.assertEqual(claims.primary(claims.classify("The President signed an Executive Order.")), "none")

    def test_quotes_only_hold_matched_sentences(self):
        c = claims.classify("Talks went well. We deny any involvement. Trade grew.")
        self.assertEqual(claims.sentences_with("Talks went well. We deny any involvement. Trade grew.", c),
                         ["We deny any involvement."])


class Lanes(unittest.TestCase):
    def test_kremlin(self):
        entries = []
        for u in kremlin.page_urls():
            entries += kremlin.parse(getter(u))
        recs = kremlin.build(entries)
        self.assertEqual(len(recs), 7)  # the /multimedia/ photo entry is skipped
        r = next(x for x in recs if x["key"] == "kremlin:81342")
        self.assertEqual(r["published_at"], "2026-11-24T10:00:00Z")  # +04:00 converted by its own offset
        self.assertEqual(r["url"], "https://en.kremlin.ru/events/president/news/81342")
        self.assertEqual(r["countries_mentioned"], ["UA", "RU", "PL"])
        self.assertEqual(r["claim"], "denial")
        self.assertTrue(r["quotes"])
        brunei = next(x for x in recs if x["key"] == "kremlin:81344")
        self.assertNotIn("static.kremlin.ru", json.dumps(brunei))  # images dropped (RIA/TASS photos excluded)
        self.assertEqual(brunei["doc_type"], "transcript")

    def test_govuk(self):
        pages = {o: govuk.parse(getter(govuk.url_for(o))) for o in govuk.ORGS}
        recs = govuk.build(pages)
        keys = [r["key"] for r in recs]
        self.assertEqual(len(keys), len(set(keys)))
        both = next(r for r in recs if r["key"].endswith("uk-poland-air-defence-fixture"))
        self.assertEqual(both["departments"], ["ministry-of-defence", "prime-ministers-office-10-downing-street"])
        osce = next(r for r in recs if "osce" in r["key"])
        self.assertEqual(osce["countries_tagged"], ["UA", "RU"])  # uk-and-the-osce is not a country
        self.assertFalse(any("spend" in k for k in keys))  # transparency data skipped
        self.assertTrue(govuk.url_for("ministry-of-defence").startswith("https://www.gov.uk/api/search.json?"))

    def test_eeas(self):
        cards = eeas.parse(getter(eeas.LIST))
        self.assertEqual(len(cards), 5)  # the <nav> and <footer> headings and the script's text are not cards
        self.assertEqual(cards[0]["day"], "2026-11-25")
        self.assertEqual(cards[0]["label"], "Statement/Declaration")
        self.assertEqual(cards[3]["url"][:31], "https://www.consilium.europa.eu")
        r = eeas.build(cards)[0]
        self.assertEqual(r["time_precision"], "day")
        self.assertIsNone(r["excerpt"])

    def test_eeas_empty_page_fails(self):
        with self.assertRaises(ValueError):
            eeas.parse(b"<html><body><h3>Nothing</h3></body></html>")

    def test_unsc(self):
        cards = unsc.parse(getter(unsc.LIST)) + unsc.parse(getter(unsc.page_urls()[1]))
        recs = {r["doc"]: r for r in unsc.build(cards)}
        self.assertEqual(recs["SC/16516"]["outcome"]["resolutions"], ["2838 (2026)"])
        self.assertTrue(recs["SC/16516"]["outcome"]["unanimous"])
        self.assertEqual(recs["SC/16516"]["countries_mentioned"], ["SS", "SD"])
        self.assertTrue(recs["SC/16514"]["outcome"]["failed"] and recs["SC/16514"]["outcome"]["veto"])
        self.assertEqual(recs["SC/16505"]["outcome"]["resolutions"], ["2836 (2026)", "2837 (2026)"])
        self.assertTrue(all(r["title"] is None and "heading" not in r for r in recs.values()))

    def test_aupsc(self):
        recs = aupsc.build(aupsc.parse(getter(aupsc.FEED)))
        self.assertEqual([r["meeting"] for r in recs], [1290, 1289])
        self.assertEqual(recs[0]["published_at"], "2026-11-20T00:00:00Z")  # the meeting date, not the post date
        self.assertEqual(recs[0]["countries_mentioned"], ["SD"])
        self.assertTrue(recs[0]["url"].startswith("https://www.peaceau.org/"))

    def test_text_helpers(self):
        self.assertEqual(text.utc("2026-11-25T20:30:00+04:00"), "2026-11-25T16:30:00Z")
        self.assertEqual(text.day_dots("25.11.2026"), "2026-11-25")
        self.assertIsNone(text.day_dots("31.13.2026"))
        self.assertEqual(text.day_words("4 November 2026"), "2026-11-04")
        self.assertEqual(text.plain("<p>A&amp;B<img src='x'/></p><p>C</p>"), "A&B C")


class SayDo(unittest.TestCase):
    def tip(self, prog, cc, asof, group=None, stale=False):
        return {"program": prog, "item_id": f"{prog}-{cc}-{asof}", "title": "t", "tier": "anomaly", "countries": [cc],
                "data_as_of": asof, "stale": stale, "group": group or prog}

    def stmt(self, text_, ccs, at="2026-11-24T10:00:00Z", precision="second"):
        c = claims.classify(text_)
        return {"key": "x:1", "claims": c, "claim": claims.primary(c), "countries_mentioned": ccs,
                "published_at": at, "time_precision": precision}

    def test_window_and_countries(self):
        s = self.stmt("Reports are baseless.", ["PL"])
        ts = [self.tip("noisefloor", "PL", "2026-11-26T09:00:00Z"),   # +71 h: in
              self.tip("watchfloor", "PL", "2026-11-27T11:00:00Z"),   # +73 h: out
              self.tip("blackout", "UA", "2026-11-24T11:00:00Z")]     # other country: out
        ps = saydo.pairs_for(s, ts)
        self.assertEqual([p["program"] for p in ps], ["noisefloor"])
        self.assertEqual(ps[0]["hours_from_statement"], 47.0)

    def test_day_precision_spans_the_day(self):
        s = self.stmt("calls for a ceasefire", ["SD"], at="2026-11-23T00:00:00Z", precision="day")
        ps = saydo.pairs_for(s, [self.tip("cordon", "SD", "2026-11-23T18:00:00Z")])
        self.assertEqual(ps[0]["hours_from_statement"], 0.0)

    def test_candidate_gap_needs_two_groups(self):
        s = self.stmt("Reports are baseless.", ["PL"])
        one = [self.tip("noisefloor", "PL", "2026-11-24T12:00:00Z", "adsb"),
               self.tip("watchfloor", "PL", "2026-11-24T13:00:00Z", "adsb")]   # same upstream: counts once
        self.assertFalse(saydo.rule(s, saydo.pairs_for(s, one))["candidate_gap"])
        two = one + [self.tip("blackout", "PL", "2026-11-24T14:00:00Z", "ioda")]
        res = saydo.rule(s, saydo.pairs_for(s, two))
        self.assertTrue(res["candidate_gap"])
        self.assertEqual(res["indicator_status"], "proposed")

    def test_stale_tips_do_not_count(self):
        s = self.stmt("Reports are baseless.", ["PL"])
        ts = [self.tip("noisefloor", "PL", "2026-11-24T12:00:00Z", "a", stale=True),
              self.tip("blackout", "PL", "2026-11-24T14:00:00Z", "b")]
        self.assertFalse(saydo.rule(s, saydo.pairs_for(s, ts))["candidate_gap"])

    def test_threat_is_context_only(self):
        s = self.stmt("will be met with a mirror response", ["UA"])
        res = saydo.rule(s, saydo.pairs_for(s, [self.tip("blackout", "UA", "2026-11-24T12:00:00Z")]))
        self.assertTrue(res["activity_near_threat"])
        self.assertFalse(res["candidate_gap"])

    def test_merge_keeps_recent_tips(self):
        old = [self.tip("wake", "TR", "2026-11-20T00:00:00Z"), self.tip("wake", "TR", "2026-11-01T00:00:00Z")]
        merged = saydo.merge(old, [self.tip("blackout", "UA", "2026-11-25T00:00:00Z")], NOW)
        self.assertEqual(len(merged), 2)
        self.assertEqual(sum(1 for t in merged if t["kept"]), 1)

    def test_interests_are_sound(self):
        self.assertEqual(tips.check_interests(json.loads((ROOT / "doctrine" / "interests.json").read_text())), [])


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = workdir()
        cls.snap = cli.collect(root=cls.root, getter=getter, now=NOW, env=ALL)
        cli.build_site(root=cls.root)
        cls.feed = json.loads((cls.root / "site" / "data" / "feed.geojson").read_text())
        cls.page = json.loads((cls.root / "site" / "data" / "snapshot.json").read_text())

    def test_every_lane_read(self):
        self.assertEqual({k: v["status"] for k, v in self.snap["lanes"].items()},
                         {k: "ok" for k in cli.LANES})

    def test_check_passes(self):
        self.assertEqual(cli.check_all(self.root), [])

    def test_contract(self):
        regs = registers.ids(self.root / "doctrine")
        for f in self.feed["features"]:
            errs = [m for _, sev, m in contract.check(f, regs) if sev == "error"]
            self.assertEqual(errs, [], f["properties"]["id"])
            self.assertEqual(f["properties"]["tier"], "routine")

    def test_statuses(self):
        by = {f["properties"]["statement"]["lane"]: f["properties"] for f in self.feed["features"]}
        self.assertEqual(by["kremlin"]["status_class"], "claimed")
        self.assertEqual(by["unsc"]["status_class"], "reported")
        self.assertEqual(by["eeas"]["data_as_of_precision"], "day")

    def test_the_candidate_gap(self):
        gaps = [f["properties"] for f in self.feed["features"] if (f["properties"].get("say_do") or {}).get("candidate_gap")]
        self.assertEqual([g["title"] for g in gaps], ["Kremlin: Meeting with Security Council permanent members"])
        sd = gaps[0]["say_do"]
        self.assertEqual(sorted(sd["programs"]), ["blackout", "noisefloor", "watchfloor"])
        self.assertIn("pointer to look, not a finding", gaps[0]["summary"])

    def test_held_lanes_are_off_by_default(self):
        root = workdir()
        snap = cli.collect(root=root, getter=getter, now=NOW, env={})
        self.assertEqual(snap["lanes"]["unsc"]["status"], "held")
        self.assertEqual(snap["records"]["aupsc"], [])
        cli.build_site(root=root)
        doc = json.loads((root / "site" / "data" / "feed.geojson").read_text())
        self.assertFalse(any(f["properties"]["statement"]["lane"] in ("unsc", "aupsc") for f in doc["features"]))
        self.assertEqual(doc["health"]["un-press-sc"]["last_error"], "held for terms")
        self.assertEqual(cli.check_all(root), [])

    def test_no_un_or_au_text_published(self):
        txt = (self.root / "site" / "data" / "feed.geojson").read_text() + \
            (self.root / "site" / "data" / "snapshot.json").read_text()
        self.assertNotIn("[fixture: UN text]", txt)
        self.assertNotIn("[fixture: AU text]", txt)
        self.assertNotIn("Fixture lede", txt)
        self.assertNotIn("Abyei", txt)  # the UN heading is read for its facts, then dropped

    def test_terms_scan_catches_leaks(self):
        bad = self.root / "bad.json"
        bad.write_text(json.dumps({"items": [{"lane": "eeas", "excerpt": "copied text"},
                                             {"lane": "unsc", "title": "UN heading"}],
                                   "x": "https://example.com/a <img src=x>"}))
        errs = cli.terms_scan([bad])
        self.assertEqual(len(errs), 4, errs)

    def test_terms_scan_allows_commission_subdomains_only(self):
        ok = self.root / "ok.json"
        ok.write_text(json.dumps({"items": [], "x": "https://transport.ec.europa.eu/news-events/news/a",
                                  "y": "https://cop.theintelligence.company/item/1"}))
        self.assertEqual(cli.terms_scan([ok]), [])
        bad = self.root / "bad2.json"
        bad.write_text(json.dumps({"items": [], "x": "https://ec.europa.eu.example.com/a",
                                   "y": "https://travel.gc.ca/destinations/uganda"}))
        self.assertEqual(len(cli.terms_scan([bad])), 2)

    def test_suite_tips_drop_upstream_links(self):
        self.assertIsNone(saydo.suite_link("https://travel.gc.ca/destinations/uganda"))
        self.assertIsNone(saydo.suite_link("https://wwwnc.cdc.gov/travel/notices/level2/x"))
        self.assertIsNone(saydo.suite_link("https://theintelligence.company.example.com/"))
        self.assertIsNone(saydo.suite_link(None))
        self.assertEqual(saydo.suite_link("https://cordon.theintelligence.company/#x"),
                         "https://cordon.theintelligence.company/#x")
        snap = {"records": {"suite": [{"program": "cordon", "item_id": "a", "link": "https://travel.gc.ca/x"},
                                      {"program": "cop", "item_id": "b", "link": "https://cop.theintelligence.company/"}]}}
        self.assertEqual([t["link"] for t in cli.suite_tips(snap)], [None, "https://cop.theintelligence.company/"])
        self.assertIsNone(saydo.compact({"program": "cordon", "item_id": "a", "link": "https://travel.gc.ca/x"},
                                        "2026-11-27T00:00:00Z")["link"])

    def test_failed_lane_keeps_last_good_copy(self):
        root = workdir()
        cli.collect(root=root, getter=getter, now=NOW, env={})
        snap = cli.collect(root=root, getter=lambda u, t: getter(u, t, fail=("eeas_p1.html",)),
                           now="2026-11-26T05:00:00Z", env={})
        self.assertEqual(snap["lanes"]["eeas"]["status"], "failed")
        self.assertTrue(snap["lanes"]["eeas"]["from_previous"])
        self.assertEqual(len(snap["records"]["eeas"]), 6)

    def test_suite_down_says_so(self):
        root = workdir()
        snap = cli.collect(root=root, getter=lambda u, t: getter(u, t, fail=("theintelligence.company",)),
                           now=NOW, env={})
        self.assertEqual(snap["lanes"]["suite"]["status"], "failed")

    def test_page_data(self):
        self.assertEqual(self.page["name"], "Readout")
        self.assertIn("PL", self.page["country_names"])
        row = next(i for i in self.page["items"] if i["lane"] == "kremlin" and i["claim"] == "denial")
        self.assertTrue(row["say_do"]["candidate_gap"])


class Registers(unittest.TestCase):
    def test_registers(self):
        self.assertEqual(registers.check(ROOT / "doctrine"), [])

    def test_rule_stays_routine(self):
        self.assertEqual(feed.rule("kremlin", {"result": {"candidate_gap": True}}), "routine")


if __name__ == "__main__":
    unittest.main()
