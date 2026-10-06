"""Manager tenures from Wikipedia's "List of Premier League managers".

Wikipedia lags behind real sackings, so data/manual/manager_overrides.csv
is applied on top when the database is built.
"""
import csv
import json
import logging
import re

from .. import config
from ..fetch import Fetcher

log = logging.getLogger(__name__)

URL = ("https://en.wikipedia.org/w/api.php?action=parse&page=List_of_Premier_League_managers"
       "&prop=wikitext&format=json&formatversion=2")

DTS = re.compile(r"\{\{dts\|(?:format=dmy\|)?(\d{4})\|(\d{1,2})\|(\d{1,2})\}\}")
SORTNAME = re.compile(r"\{\{sortname\|([^|}]+)\|([^|}]+)")
LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")


def raw_file():
    return config.path("raw") / "managers" / "wikipedia.json"


def parsed_file():
    return config.path("raw") / "managers" / "managers.csv"


def _date(cell: str) -> str | None:
    m = DTS.search(cell)
    return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}" if m else None


def _name(cell: str) -> str:
    m = SORTNAME.search(cell)
    if m:
        return f"{m[1].strip()} {m[2].strip()}"
    m = LINK.search(cell)
    return m[1].strip() if m else re.sub(r"[{}\[\]!|]|scope=\"?row\"?", "", cell).strip()


def parse(wikitext: str) -> list[dict]:
    start = wikitext.index("|+Managers")
    table = wikitext[start: wikitext.index("\n|}", start)]
    rows = []
    for block in table.split("\n|-")[1:]:
        lines = [ln for ln in block.strip().split("\n") if ln.strip()]
        head = next((ln for ln in lines if ln.startswith("!")), None)
        cells = [ln[1:].strip() for ln in lines if ln.startswith("|")]
        if head is None or len(cells) < 4:
            continue
        club = LINK.search(cells[1])
        rows.append({
            "manager": _name(head.split("|", 1)[-1] if "scope" in head else head),
            "club": club[1].strip() if club else cells[1],
            "start": _date(cells[2]),
            "end": _date(cells[3]),            # None = still in charge
            "caretaker": "b7e8b9" in head or "double dagger" in head,
        })
    return rows


def ingest(fetcher: Fetcher) -> None:
    raw = fetcher.get(URL, raw_file(), refresh=True)
    rows = parse(json.loads(raw)["parse"]["wikitext"])
    with open(parsed_file(), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["manager", "club", "start", "end", "caretaker"])
        w.writeheader()
        w.writerows(rows)
    log.info("managers: %d tenures", len(rows))
