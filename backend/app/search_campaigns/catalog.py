"""Global targeting is independent from configured scraper support."""
from app.scrapers.country_map import COUNTRY_MAP

# ISO 3166-1 alpha-2; regions such as EU/REMOTE are intentionally not countries.
COUNTRY_CODES = frozenset("""AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW""".split())


def country_code(value: str) -> str:
    code = value.strip().upper()
    if code not in COUNTRY_CODES:
        raise ValueError("Use an ISO 3166-1 alpha-2 country code")
    return code


def coverage() -> dict:
    return {
        "execution_enabled": True,
        "execution_modalities": ["remote", "any"],
        "execution_sites": ["indeed"],
        "health_verified": False,
        "countries": [{"code": code,
                       "configured_connectors": ["jobspy"] if code in COUNTRY_MAP else [],
                       "status": "configured_not_verified" if code in COUNTRY_MAP else "not_configured"}
                      for code in sorted(COUNTRY_CODES)],
        "note": "Manual campaigns run configured country mappings through Indeed only. Other targets can be saved but cannot run yet. Configured country mapping does not guarantee vacancies or source availability.",
    }
