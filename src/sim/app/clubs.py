"""Club short codes and kit colours (primary, secondary) for bands and chart series."""

CLUBS: dict[str, tuple[str, str, str]] = {
    "Arsenal": ("ARS", "#EF0107", "#FFFFFF"),
    "Aston Villa": ("AVL", "#670E36", "#95BFE5"),
    "Bournemouth": ("BOU", "#DA291C", "#111111"),
    "Brentford": ("BRE", "#E30613", "#FFFFFF"),
    "Brighton & Hove Albion": ("BHA", "#0057B8", "#FFFFFF"),
    "Burnley": ("BUR", "#6C1D45", "#99D6EA"),
    "Cardiff City": ("CAR", "#0070B5", "#D11524"),
    "Chelsea": ("CHE", "#034694", "#FFFFFF"),
    "Coventry City": ("COV", "#5FA8E0", "#FFFFFF"),
    "Crystal Palace": ("CRY", "#1B458F", "#C4122E"),
    "Everton": ("EVE", "#003399", "#FFFFFF"),
    "Fulham": ("FUL", "#141414", "#FFFFFF"),
    "Huddersfield Town": ("HUD", "#0E63AD", "#FFFFFF"),
    "Hull City": ("HUL", "#F5A12D", "#111111"),
    "Ipswich Town": ("IPS", "#0044A9", "#FFFFFF"),
    "Leeds United": ("LEE", "#1D428A", "#FFCD00"),
    "Leicester City": ("LEI", "#003090", "#FDBE11"),
    "Liverpool": ("LIV", "#C8102E", "#00B2A9"),
    "Luton Town": ("LUT", "#F78F1E", "#002D62"),
    "Manchester City": ("MCI", "#6CABDD", "#1C2C5B"),
    "Manchester United": ("MUN", "#DA291C", "#FBE122"),
    "Middlesbrough": ("MID", "#E11B22", "#FFFFFF"),
    "Newcastle United": ("NEW", "#241F20", "#FFFFFF"),
    "Norwich City": ("NOR", "#00A650", "#FFF200"),
    "Nottingham Forest": ("NFO", "#DD0000", "#FFFFFF"),
    "Sheffield United": ("SHU", "#EE2737", "#111111"),
    "Southampton": ("SOU", "#D71920", "#FFFFFF"),
    "Stoke City": ("STK", "#E03A3E", "#FFFFFF"),
    "Sunderland": ("SUN", "#EB172B", "#FFFFFF"),
    "Swansea City": ("SWA", "#121212", "#FFFFFF"),
    "Tottenham Hotspur": ("TOT", "#132257", "#FFFFFF"),
    "Watford": ("WAT", "#FBEE23", "#ED2127"),
    "West Bromwich Albion": ("WBA", "#122F67", "#FFFFFF"),
    "West Ham United": ("WHU", "#7A263A", "#1BB1E7"),
    "Wolverhampton Wanderers": ("WOL", "#FDB913", "#231F20"),
}


def info(team: str) -> dict:
    short, primary, secondary = CLUBS.get(team, (team[:3].upper(), "#555555", "#FFFFFF"))
    return {"name": team, "short": short, "primary": primary, "secondary": secondary}
