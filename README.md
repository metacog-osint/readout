# Readout

Part of The Intelligence Company's suite of public monitoring programs. It reads what governments say, in their own
words, and holds it against what the suite's sensors saw:

- **Kremlin** (en.kremlin.ru): every publication in its Atom feed, three pages deep.
- **UK government** (GOV.UK search API): news, speeches and statements from the Foreign, Commonwealth & Development
  Office, the Ministry of Defence and the Prime Minister's Office.
- **European Union** (EEAS press material): press releases, statements, declarations and speeches.
- **UN Security Council** and **African Union Peace and Security Council**: built and **held**, off until each
  publisher's terms are cleared.

A fixed word list sorts each statement into the kinds of claim it makes (de-escalation, denial, assurance, threat,
accusation). The say-do check lists the anomalies and warnings other TIC programs published in the countries a
statement names within 72 hours. A calm claim with such pairs from two independent sources is shown as a
**candidate say-do gap**: proposed rule RO-IND-1, not adopted, a pointer to look and never a finding that anyone
lied. Every item is tier routine. Method: [`doctrine/method.md`](doctrine/method.md). Feed: `tic-feed/2` GeoJSON at
`data/feed.geojson`.

```bash
python tools/readout.py collect && python tools/readout.py build && python tools/readout.py check
python -m unittest discover -s tests
python tools/serve.py          # the built site at http://localhost:8783 with its _headers
```

Python 3.12, standard library only, no keys. `READOUT_ALLOW_HELD=unsc,aupsc` reads the held lanes; leave it unset
until their publishers say yes. `READOUT_BUS` points the say-do check at another suite bus (default: COP's).

Sources and terms: the Kremlin (CC BY 4.0 with a reference to en.kremlin.ru; RIA Novosti and TASS photos are
excluded, and none are kept), GOV.UK (Open Government Licence v3.0), the EEAS (reuse with acknowledgement,
Commission Decision 2011/833/EU; title, date and link only), the UN (personal, non-commercial use, no
redistribution; number, date, outcome and link only, held) and the AU (no redistribution or compilation without
written permission; held). Not read: the US State Department, whose site refused the build environment's browser on
25 Nov 2026, and UN Digital Library voting records, whose terms need the Library's approval for automated downloads.
The test fixtures are made up in each source's shape; none is a real statement. The feed's own text is CC BY 4.0;
the code's licence is below.

## Licence

Copyright © 2026 Thomas Brummer, The Intelligence Company. Readout's code is licensed under the GNU Affero General
Public License v3.0 (`LICENSE`). Third-party and shared files keep their own licences, and data keeps its sources'
terms; both are listed in `NOTICE`.

## AI assistance

This repository is built with AI coding assistance (Anthropic's Claude Code). The Intelligence Company is responsible
for everything published here.
