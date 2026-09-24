"""Conservative residence screening using explicit structured restrictions only."""
from app.search_campaigns.catalog import country_code


def evaluate_eligibility(
    residence_country: str | None,
    allowed_residence_countries: list[str] | None = None,
    *, worldwide_explicit: bool = False,
) -> dict[str, str]:
    """This checks residence only, never citizenship, visa or work authorization.

    Empty restrictions mean missing evidence, not worldwide permission. Contradictory
    worldwide and restricted-country declarations require human clarification.
    """
    allowed = {country_code(code) for code in allowed_residence_countries or []}
    residence = country_code(residence_country) if residence_country else None
    if worldwide_explicit and allowed:
        return {"status": "unknown", "reason": "Conflicting worldwide and country restrictions"}
    if worldwide_explicit:
        return {"status": "yes", "reason": "Posting explicitly permits worldwide residence; other eligibility requirements remain separate"}
    if not residence:
        return {"status": "unknown", "reason": "Candidate residence has not been established"}
    if not allowed:
        return {"status": "unknown", "reason": "Posting does not establish eligible countries; remote does not imply worldwide"}
    if residence in allowed:
        return {"status": "yes", "reason": "Residence matches an explicitly permitted country; work authorization remains separate"}
    return {"status": "no", "reason": "Residence is outside the explicitly permitted countries"}
