"""What kind of claim a statement makes: a fixed keyword list read over its title and the text Readout keeps.

Classes (method readout-0.1). A statement can carry several; `primary()` picks one for display.

- deescalation: says fighting or a deployment is stopping or easing (ceasefire, truce, withdrawal, pause).
- denial: denies an act or an involvement (denies, not involved, baseless, fabricated).
- assurance: says the speaker means no harm (defensive, no threat, no intention, no plans to).
- threat: warns of a response (retaliation, will respond, consequences, red line, ultimatum).
- accusation: accuses another party (aggression, violation, provocation, attacks on).

The first three are "calm" claims: they say less will happen. They are the ones the say-do check holds against
what the suite's sensors saw (`saydo`). This is a word list, not a reading of meaning: "we deny any ceasefire
violation" is both denial and accusation, and a negated phrase ("there will be no ceasefire") still reads as
deescalation. The page shows the words that matched, so a reader can see why. Nothing here is a judgment that
the speaker is lying.
"""
from __future__ import annotations

import re

CLASSES = {
    "deescalation": ["ceasefire", "cease-fire", "truce", "de-escalat", "deescalat", "withdraw", "withdrew", "pull back",
                     "pulled back", "restraint", "halt", "pause", "moratorium", "armistice", "disengage",
                     "stand down", "end hostilities", "cessation of hostilities", "peace talks"],
    "denial": ["deny", "denies", "denied", "not involved", "no involvement", "baseless", "groundless",
               "unfounded", "fabricat", "false claims", "fake", "disinformation", "had nothing to do with",
               "has nothing to do with", "not responsible"],
    "assurance": ["defensive", "no threat", "poses no threat", "not at war", "does not seek", "do not seek",
                  "no intention", "no plans to", "not planning", "purely defensive", "routine exercise",
                  "pose no danger", "not directed against"],
    "threat": ["retaliat", "inevitable response", "will respond", "will be met", "consequences", "warns", "warned",
               "warning to", "ultimatum", "red line", "legitimate target", "mirror response", "countermeasures"],
    "accusation": ["aggressor", "aggression", "attacks on", "attack on", "violation", "violated", "provocation",
                   "provocative", "terrorist attack", "war crime", "shelling of", "strike on", "strikes on"],
}
CALM = ("deescalation", "denial", "assurance")
ORDER = ("denial", "deescalation", "assurance", "threat", "accusation")
# A word matches at the start of a word and runs to its end, so "fabricat" shows as "fabricated".
_PATTERNS = {c: [(w, re.compile(r"(?<![\w-])" + re.escape(w).replace(r"\-", "[- ]?") + r"\w*", re.I)) for w in words]
             for c, words in CLASSES.items()}


def classify(text: str) -> dict[str, list[str]]:
    """{class: [matched words]} for every class with at least one match, in the text's own wording."""
    out: dict[str, list[str]] = {}
    for cls, pats in _PATTERNS.items():
        hits = []
        for word, pat in pats:
            m = pat.search(text or "")
            if m and m.group(0).lower() not in (h.lower() for h in hits):
                hits.append(m.group(0))
        if hits:
            out[cls] = hits
    return out


def primary(classes: dict) -> str:
    for c in ORDER:
        if c in classes:
            return c
    return "none"


def is_calm(classes: dict) -> bool:
    return any(c in classes for c in CALM)


_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“‘(])")


def sentences_with(text: str, classes: dict, most: int = 3, width: int = 320) -> list[str]:
    """Up to `most` sentences of `text` that hold a matched word, each cut to `width` characters. Used only for
    sources whose terms allow quoting (Kremlin, CC BY 4.0; GOV.UK, OGL v3)."""
    words = [w.lower() for ws in classes.values() for w in ws]
    out = []
    for s in _SENT.split(text or ""):
        low = s.lower()
        if any(w in low for w in words):
            s = s.strip()
            out.append(s if len(s) <= width else s[: width - 1].rsplit(" ", 1)[0] + "…")
            if len(out) >= most:
                break
    return out
