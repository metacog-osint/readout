# Method: Readout, readout-0.1

## What it reads
Official statements in the speakers' own words, read each run from their public pages (no keys):

- **Kremlin** (President of Russia, English site). Every publication in its Atom feed, three pages deep: news,
  transcripts, acts and letters. Kept: title, link, time (converted to UTC by the feed's own offset), a 400-character
  opening excerpt and up to three sentences that hold a claim word. CC BY 4.0, with a reference to en.kremlin.ru.
  No images (photos by RIA Novosti and TASS are excluded from the licence).
- **UK government** (GOV.UK search API). News, speeches, press releases and statements from the Foreign,
  Commonwealth & Development Office, the Ministry of Defence and the Prime Minister's Office, 40 newest each. Kept:
  title, GOV.UK's one-line description, link, time, document type and GOV.UK's own world-location tags. Open
  Government Licence v3.0.
- **European Union** (EEAS press material). Press releases, statements, declarations and speeches, two pages of the
  listing. Kept: title, category, date and link. Reuse with acknowledgement (Commission Decision 2011/833/EU). The
  page gives a date, not a time, so these items carry day precision.

Two lanes are built and **held**, off until their terms are cleared:

- **UN Security Council** (UN meetings coverage). The press release number, date, link, the resolutions adopted,
  whether unanimously, failed or vetoed, and the countries named. The UN's terms allow personal, non-commercial use
  and no redistribution, so the heading and lede are read to derive those facts and then dropped. How each member
  voted is in the UN Digital Library, whose terms forbid automated downloads without its approval: not fetched.
- **African Union Peace and Security Council** (peaceau.org RSS). Meeting number, date, link and the countries
  named. peaceau.org forbids redistribution and derivative works without written permission.

Each statement is the speaker's own claim: kind observation, status_class **claimed**, source grade A2 (the source
is the speaker, so the words are certainly what it said; that says nothing about whether they are true). A Council
or PSC record is the body's own record of what it did (status_class reported).

## What kind of claim
A fixed word list (`readout/claims.py`) read over the title and the kept text sorts each statement into the claim
classes it carries:

| Class | Says | Examples of the words |
|---|---|---|
| deescalation | fighting or a deployment is easing | ceasefire, truce, withdraw, pause, restraint |
| denial | denies an act or a part in one | denies, not involved, baseless, fabricated |
| assurance | its intent is not hostile | defensive, no threat, no intention, no plans to |
| threat | warns of a response | retaliation, will respond, consequences, red line |
| accusation | accuses another party | aggression, violation, provocation, attack on |

The first three are **calm** claims: they say less will happen. The page shows the words that matched. A word list
misreads negations ("there will be no ceasefire" reads as deescalation) and quotations (RO-ASM-1, untested).

## Which countries
GOV.UK's own world-location tags first, where present; then country names, demonyms ("Russian-Bruneian"), capitals
used for governments ("Kiev", "Moscow") and a few set forms ("the Kiev regime", "DPRK") matched in the title and kept
text. The issuer is added to an item's countries when it is a country (Russia, the UK); the EU, UN and AU are not
countries and are not placed. An item with no country is drawn off the map.

## The say-do check
"Do" is what the other TIC programs saw: anomalies and warnings from Watchfloor, Noisefloor, Wake, Blackout, Cordon
and Launch, read as tips from the suite bus through the doctrine kit (`doctrine/interests.json`, interest RO-INT-1).
Readout collects none of that data again; it keeps pointers (program, item id, title, tier, countries, time, link)
for 14 days, because the bus carries only what is current.

A **pair** is a tip that shares a country with what a statement names and whose data_as_of is within 72 hours of the
statement, before or after (for a day-precision statement, 72 hours either side of that whole day). Each statement
lists its pairs, nearest first, with the hours between them.

- **RO-IND-1, PROPOSED, not adopted.** A calm claim with pairs from at least two independence groups (not stale)
  is shown as a **candidate say-do gap**. It moves no tier: every Readout item is tier routine in readout-0.1, and
  the rule stays a proposal until it is adopted, changed or dropped.
- **RO-IND-2, information only.** A threat with any pair is shown as activity near a threat.

A pair is co-occurrence in a country within three days. It is not evidence that a statement was false: the activity
may be another party's, unrelated, routine for that place, or in another part of the country (RO-ASM-2). It is a
pointer to look.

## What it does not do
No translation, no sentiment score, no judgment of truth, no forecast. No statement text from the UN or the AU. No
US State Department lane in v1 (its site refused the build environment's browser on 25 Nov 2026).

## Feed
tic-feed/2, revision 2.1, one item per statement. The `statement` block carries the issuer, document type, claim
classes and words, countries named, and for Kremlin and GOV.UK items the excerpt and quoted sentences. The `say_do`
block carries the result and up to ten pairs. Licence of Readout's own text: CC BY 4.0. Each item keeps its source's
terms.
