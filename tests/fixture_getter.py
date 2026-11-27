"""A getter that answers the lanes' URLs from tests/fixtures/ (made-up data in each source's shape)."""
from __future__ import annotations

from pathlib import Path

FIX = Path(__file__).resolve().parent / "fixtures"
ROUTES = {
    "http://en.kremlin.ru/events/all/feed": "kremlin_p1.xml",
    "http://en.kremlin.ru/events/all/feed/page/2": "kremlin_p2.xml",
    "http://en.kremlin.ru/events/all/feed/page/3": "kremlin_p3.xml",
    "filter_organisations=foreign-commonwealth-development-office": "govuk_fcdo.json",
    "filter_organisations=ministry-of-defence": "govuk_mod.json",
    "filter_organisations=prime-ministers-office-10-downing-street": "govuk_pmo.json",
    "https://www.eeas.europa.eu/eeas/press-material_en": "eeas_p1.html",
    "https://www.eeas.europa.eu/eeas/press-material_en?page=1": "eeas_p2.html",
    "https://press.un.org/en/content/security-council/meetings-coverage": "unsc_p1.html",
    "https://press.un.org/en/content/security-council/meetings-coverage?page=1": "unsc_p2.html",
    "http://www.peaceau.org/en/rss": "aupsc.xml",
    "https://cop.theintelligence.company/data/today.geojson": "bus.geojson",
}


def getter(url: str, timeout: int = 60, fail: tuple = ()) -> bytes:
    if url in ROUTES:
        name = ROUTES[url]
    else:
        name = next((v for k, v in ROUTES.items() if "=" in k and k in url), None)
    if name is None or name in fail or any(f in url for f in fail):
        raise OSError(f"fixture getter: no route for {url}")
    return (FIX / name).read_bytes()
