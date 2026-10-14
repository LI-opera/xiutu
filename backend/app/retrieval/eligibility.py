"""Server profile and current review gates, independent of search request."""


def exclusion(version, profile):
    if version["review_status"] != "approved":
        return "review_not_approved"
    if version["parse_status"] != "review_pending" or version["page_issues"]:
        return "parse_incomplete"
    synthetic = version["metadata_json"].get("synthetic") is True
    if profile == "synthetic":
        return None if synthetic else "profile_mismatch"
    if synthetic:
        return "synthetic"
    review = version["review_snapshot"]
    if review.get("source_status") != "verified":
        return "source_unverified"
    if review.get("license_status") not in {"private_use", "permitted"}:
        return "license_unverified"
    return None


def applicability(scope, vehicle):
    reasons, missing = [], []
    for key in ("model", "engine_family", "engine_code"):
        a, b = scope.get(key), vehicle.get(key)
        if not a or not b:
            missing.append(key)
        elif a.strip().casefold() != b.strip().casefold():
            reasons.append(key + "_conflict")
    year, low, high = vehicle.get("year"), scope.get("year_from"), scope.get("year_to")
    if year is not None and (
        (low is not None and year < low) or (high is not None and year > high)
    ):
        reasons.append("year_conflict")
    if year is None or low is None or high is None:
        missing.append("year")
    if reasons:
        return dict(status="mismatch", reasons=reasons, general_reference_only=False)
    return dict(
        status="unknown" if missing else "matched",
        reasons=["missing_" + x for x in missing]
        or ["submitted_information_match_not_certification"],
        general_reference_only=bool(missing),
    )
