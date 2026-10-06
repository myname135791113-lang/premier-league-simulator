"""A short history for every club: founding facts, one line of story, and an honours count.

Honours run to the end of the 2024/25 season (cups included). League titles won after that
are added from the results in football.db, so the count stays right without editing this file.
Counts: top-flight league titles, FA Cups, League Cups, European Cup / Champions League,
and other UEFA trophies (UEFA Cup / Europa League, Cup Winners' Cup, Fairs Cup, Conference League).
"""

HONOURS_AS_OF = "2024/25"
LAST_KNOWN_SEASON = 2024     # start year of the last season these counts include

# name: (founded, ground, ground_since, nickname, story,
#        (league, last_league), (fa_cup, last_fa), (league_cup, last_lc), (european_cup, last_ec), (other_europe, last_oe))
CLUBS = {
    "Arsenal": (1886, "Emirates Stadium", 2006, "The Gunners",
                "Formed by workers at the Royal Arsenal in Woolwich; moved north to Highbury in 1913. Arsène Wenger's 2003/04 side went the whole league season unbeaten.",
                (13, 2004), (14, 2020), (2, 1993), (0, None), (2, 1994)),
    "Aston Villa": (1874, "Villa Park", 1897, "The Villans",
                    "A founder member of the Football League in 1888, and European champions in 1982.",
                    (7, 1981), (7, 1957), (5, 1996), (1, 1982), (0, None)),
    "Bournemouth": (1899, "Vitality Stadium", 1910, "The Cherries",
                    "Spent nearly all of their history in the lower divisions before reaching the top flight for the first time in 2015.",
                    (0, None), (0, None), (0, None), (0, None), (0, None)),
    "Brentford": (1889, "Gtech Community Stadium", 2020, "The Bees",
                  "Returned to the top flight in 2021 for the first time since 1947.",
                  (0, None), (0, None), (0, None), (0, None), (0, None)),
    "Brighton & Hove Albion": (1901, "Amex Stadium", 2011, "The Seagulls",
                               "Moved into the Amex in 2011 after years without a ground of their own; FA Cup finalists in 1983 and in Europe for the first time in 2023/24.",
                               (0, None), (0, None), (0, None), (0, None), (0, None)),
    "Burnley": (1882, "Turf Moor", 1883, "The Clarets",
                "A founder member of the Football League; league champions in 1921 and 1960.",
                (2, 1960), (1, 1914), (0, None), (0, None), (0, None)),
    "Cardiff City": (1899, "Cardiff City Stadium", 2009, "The Bluebirds",
                     "The only club from outside England to have won the FA Cup, in 1927.",
                     (0, None), (1, 1927), (0, None), (0, None), (0, None)),
    "Chelsea": (1905, "Stamford Bridge", 1905, "The Blues",
                "Founded to play at Stamford Bridge; European champions in 2012 and 2021, and winners of all three current UEFA club competitions.",
                (6, 2017), (8, 2018), (5, 2015), (2, 2021), (5, 2025)),
    "Coventry City": (1883, "Coventry Building Society Arena", 2005, "The Sky Blues",
                      "Spent 34 consecutive seasons in the top flight from 1967 to 2001, and won the FA Cup in 1987.",
                      (0, None), (1, 1987), (0, None), (0, None), (0, None)),
    "Crystal Palace": (1905, "Selhurst Park", 1924, "The Eagles",
                       "Won their first major trophy, the FA Cup, in 2025.",
                       (0, None), (1, 2025), (0, None), (0, None), (0, None)),
    "Everton": (1878, "Hill Dickinson Stadium", 2025, "The Toffees",
                "Have spent more seasons in the top flight than any other club; left Goodison Park for a new stadium at Bramley-Moore Dock in 2025.",
                (9, 1987), (5, 1995), (0, None), (0, None), (1, 1985)),
    "Fulham": (1879, "Craven Cottage", 1896, "The Cottagers",
               "Have played on the Thames at Craven Cottage since 1896; Europa League finalists in 2010.",
               (0, None), (0, None), (0, None), (0, None), (0, None)),
    "Huddersfield Town": (1908, "John Smith's Stadium", 1994, "The Terriers",
                          "The first club to win three successive league titles, from 1924 to 1926.",
                          (3, 1926), (1, 1922), (0, None), (0, None), (0, None)),
    "Hull City": (1904, "MKM Stadium", 2002, "The Tigers",
                  "Reached the top flight for the first time in 2008, and the FA Cup final in 2014.",
                  (0, None), (0, None), (0, None), (0, None), (0, None)),
    "Ipswich Town": (1878, "Portman Road", 1884, "Town",
                     "Won the league at the first attempt in 1962 under Alf Ramsey, and the UEFA Cup in 1981 under Bobby Robson.",
                     (1, 1962), (1, 1978), (0, None), (0, None), (1, 1981)),
    "Leeds United": (1919, "Elland Road", 1919, "The Whites",
                     "Don Revie's side won two league titles and two Fairs Cups; champions again in 1992.",
                     (3, 1992), (1, 1972), (1, 1968), (0, None), (2, 1971)),
    "Leicester City": (1884, "King Power Stadium", 2002, "The Foxes",
                       "Won the 2015/16 Premier League after starting the season as 5,000-1 outsiders.",
                       (1, 2016), (1, 2021), (3, 2000), (0, None), (0, None)),
    "Liverpool": (1892, "Anfield", 1892, "The Reds",
                  "Six times European champions; a 20th league title in 2024/25 drew them level with Manchester United.",
                  (20, 2025), (8, 2022), (10, 2024), (6, 2019), (3, 2001)),
    "Luton Town": (1885, "Kenilworth Road", 1905, "The Hatters",
                   "League Cup winners in 1988; climbed from non-league football to the Premier League between 2014 and 2023.",
                   (0, None), (0, None), (1, 1988), (0, None), (0, None)),
    "Manchester City": (1880, "Etihad Stadium", 2003, "The Citizens",
                        "Won six of the seven Premier League titles from 2017/18 to 2023/24, and the treble in 2023.",
                        (10, 2024), (7, 2023), (8, 2021), (1, 2023), (1, 1970)),
    "Manchester United": (1878, "Old Trafford", 1910, "The Red Devils",
                          "Founded as Newton Heath; 13 Premier League titles under Sir Alex Ferguson, including the 1999 treble.",
                          (20, 2013), (13, 2024), (6, 2023), (3, 2008), (2, 2017)),
    "Middlesbrough": (1876, "Riverside Stadium", 1995, "Boro",
                      "League Cup winners in 2004 and UEFA Cup finalists in 2006.",
                      (0, None), (0, None), (1, 2004), (0, None), (0, None)),
    "Newcastle United": (1892, "St James' Park", 1892, "The Magpies",
                         "Won the League Cup in 2025, their first major domestic trophy since the 1955 FA Cup.",
                         (4, 1927), (6, 1955), (1, 2025), (0, None), (1, 1969)),
    "Norwich City": (1902, "Carrow Road", 1935, "The Canaries",
                     "League Cup winners in 1962 and 1985; third in the first Premier League season, 1992/93.",
                     (0, None), (0, None), (2, 1985), (0, None), (0, None)),
    "Nottingham Forest": (1865, "City Ground", 1898, "Forest",
                          "Brian Clough's side won the league in 1978, a year after promotion, then the European Cup in 1979 and 1980.",
                          (1, 1978), (2, 1959), (4, 1990), (2, 1980), (0, None)),
    "Sheffield United": (1889, "Bramall Lane", 1889, "The Blades",
                         "Play at Bramall Lane, the oldest major stadium still hosting professional football; league champions in 1898.",
                         (1, 1898), (4, 1925), (0, None), (0, None), (0, None)),
    "Southampton": (1885, "St Mary's Stadium", 2001, "The Saints",
                    "Won the FA Cup as a Second Division side in 1976.",
                    (0, None), (1, 1976), (0, None), (0, None), (0, None)),
    "Stoke City": (1863, "bet365 Stadium", 1997, "The Potters",
                   "Claim 1863 as their founding year; League Cup winners in 1972.",
                   (0, None), (0, None), (1, 1972), (0, None), (0, None)),
    "Sunderland": (1879, "Stadium of Light", 1997, "The Black Cats",
                   "Six times English champions, the last in 1936; back in the Premier League from 2025.",
                   (6, 1936), (2, 1973), (0, None), (0, None), (0, None)),
    "Swansea City": (1912, "Swansea.com Stadium", 2005, "The Swans",
                     "Climbed from the fourth tier to the Premier League between 2005 and 2011, and won the League Cup in 2013.",
                     (0, None), (0, None), (1, 2013), (0, None), (0, None)),
    "Tottenham Hotspur": (1882, "Tottenham Hotspur Stadium", 2019, "Spurs",
                          "The first club of the 20th century to win the league and FA Cup double, in 1961; Europa League winners in 2025.",
                          (2, 1961), (8, 1991), (4, 2008), (0, None), (4, 2025)),
    "Watford": (1881, "Vicarage Road", 1922, "The Hornets",
                "Rose from the Fourth Division to league runners-up in 1983 under Graham Taylor.",
                (0, None), (0, None), (0, None), (0, None), (0, None)),
    "West Bromwich Albion": (1878, "The Hawthorns", 1900, "The Baggies",
                             "A founder member of the Football League; league champions in 1920 and five times FA Cup winners.",
                             (1, 1920), (5, 1968), (1, 1966), (0, None), (0, None)),
    "West Ham United": (1895, "London Stadium", 2016, "The Hammers",
                        "Founded as Thames Ironworks; Cup Winners' Cup winners in 1965 and Conference League winners in 2023.",
                        (0, None), (3, 1980), (0, None), (0, None), (2, 2023)),
    "Wolverhampton Wanderers": (1877, "Molineux", 1889, "Wolves",
                                "Stan Cullis's side won three league titles in the 1950s.",
                                (3, 1959), (4, 1960), (2, 1980), (0, None), (0, None)),
}

HONOUR_LABELS = ["League titles", "FA Cups", "League Cups", "European Cups", "Other European"]


def club_history(team: str, champions: dict[int, str]) -> dict | None:
    """`champions`: season start year -> champion, from the database (used for titles after HONOURS_AS_OF)."""
    row = CLUBS.get(team)
    if row is None:
        return None
    founded, ground, since, nickname, story, *honours = row
    honours = [list(h) for h in honours]
    for season, champ in sorted(champions.items()):
        if season > LAST_KNOWN_SEASON and champ == team:
            honours[0][0] += 1
            honours[0][1] = season + 1
    return {
        "founded": founded, "ground": ground, "ground_since": since, "nickname": nickname, "story": story,
        "honours": [{"label": lbl, "count": c, "last": last} for lbl, (c, last) in zip(HONOUR_LABELS, honours)],
        "honours_note": f"Cup counts to the end of {HONOURS_AS_OF}; league titles include later seasons in the data.",
    }
