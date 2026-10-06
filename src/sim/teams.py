"""Canonical club names. Every source's spelling maps to one name here."""

ALIASES: dict[str, list[str]] = {
    "Arsenal": [],
    "Aston Villa": [],
    "Bournemouth": ["AFC Bournemouth"],
    "Brentford": [],
    "Brighton & Hove Albion": ["Brighton"],
    "Burnley": [],
    "Cardiff City": ["Cardiff"],
    "Chelsea": [],
    "Coventry City": ["Coventry"],
    "Crystal Palace": [],
    "Everton": [],
    "Fulham": [],
    "Huddersfield Town": ["Huddersfield"],
    "Hull City": ["Hull"],
    "Ipswich Town": ["Ipswich"],
    "Leeds United": ["Leeds"],
    "Leicester City": ["Leicester"],
    "Liverpool": [],
    "Luton Town": ["Luton"],
    "Manchester City": ["Man City"],
    "Manchester United": ["Man United", "Man Utd"],
    "Middlesbrough": [],
    "Newcastle United": ["Newcastle"],
    "Norwich City": ["Norwich"],
    "Nottingham Forest": ["Nott'm Forest", "Forest"],
    "Sheffield United": ["Sheffield Utd"],
    "Southampton": [],
    "Stoke City": ["Stoke"],
    "Sunderland": [],
    "Swansea City": ["Swansea"],
    "Tottenham Hotspur": ["Tottenham", "Spurs"],
    "Watford": [],
    "West Bromwich Albion": ["West Brom"],
    "West Ham United": ["West Ham"],
    "Wolverhampton Wanderers": ["Wolves"],
}

_LOOKUP = {name.casefold(): canon for canon, alts in ALIASES.items() for name in [canon, *alts]}


def canon(name: str) -> str:
    """Canonical club name; raises KeyError for a spelling not in ALIASES."""
    try:
        return _LOOKUP[name.strip().casefold()]
    except KeyError:
        raise KeyError(f"Unknown club name {name!r}: add it to sim.teams.ALIASES") from None


def known(name: str) -> bool:
    return name.strip().casefold() in _LOOKUP


_FOLD = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "AE", "ß": "ss", "đ": "d", "Đ": "D", "ł": "l", "Ł": "L",
                       "ı": "i", "þ": "th", "Þ": "Th", "ð": "d", "œ": "oe", "Œ": "OE"})


def fold_name(name: str) -> str:
    """Lower-case ASCII form of a person's name for matching across sources (Ødegaard -> odegaard)."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name).translate(_FOLD)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace("'", "").replace("’", "").split())
