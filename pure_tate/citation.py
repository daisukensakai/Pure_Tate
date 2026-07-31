import datetime as _datetime
import re
from typing import Dict

from .models import CheckResult, Claim, Source


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}$")
VERSION_RE = re.compile(r"^v[1-9]\d*$")
PUBLICATION_STATUSES = {"preprint", "accepted", "published", "retracted"}


def _parse_date(value: str, label: str, result: CheckResult) -> None:
    if not value:
        return
    if not DATE_RE.match(value):
        result.errors.append("%s has malformed date %r" % (label, value))
        return
    try:
        _datetime.date.fromisoformat(value)
    except ValueError:
        result.errors.append("%s has invalid calendar date %r" % (label, value))


def audit_citations(
    sources: Dict[str, Source],
    claims: Dict[str, Claim],
    freshness_days: int,
    today: _datetime.date,
) -> CheckResult:
    result = CheckResult()
    for source in sources.values():
        if source.publication_status not in PUBLICATION_STATUSES:
            result.errors.append(
                "%s has invalid publication_status %r"
                % (source.id, source.publication_status)
            )
        if source.arxiv_id:
            if not ARXIV_RE.match(source.arxiv_id):
                result.errors.append(
                    "%s has malformed arXiv id %r" % (source.id, source.arxiv_id)
                )
            if not VERSION_RE.match(source.arxiv_version):
                result.errors.append(
                    "%s has malformed arXiv version %r"
                    % (source.id, source.arxiv_version)
                )
        for field_name in (
            "submitted_on",
            "revised_on",
            "published_on",
            "checked_on",
        ):
            _parse_date(
                getattr(source, field_name), "%s.%s" % (source.id, field_name), result
            )
        if source.checked_on and DATE_RE.match(source.checked_on):
            checked = _datetime.date.fromisoformat(source.checked_on)
            age = (today - checked).days
            if age < 0:
                result.errors.append("%s was checked in the future" % source.id)
            elif age > freshness_days:
                result.warnings.append(
                    "%s citation check is stale (%d days)" % (source.id, age)
                )
        if source.publication_status == "published" and not (
            source.doi or source.url
        ):
            result.errors.append("%s published source lacks DOI/URL" % source.id)
        if source.publication_status == "retracted":
            result.errors.append("%s is retracted" % source.id)

    for claim in claims.values():
        locator_sources = {locator.source_id for locator in claim.locators}
        for source_id in claim.source_ids:
            if source_id not in sources:
                result.errors.append(
                    "%s references unknown source %s" % (claim.id, source_id)
                )
            if source_id not in locator_sources:
                result.errors.append(
                    "%s lacks an exact locator for %s" % (claim.id, source_id)
                )
        for locator in claim.locators:
            if locator.source_id not in sources:
                result.errors.append(
                    "%s locator references unknown source %s"
                    % (claim.id, locator.source_id)
                )
            if not locator.locator.strip():
                result.errors.append("%s has an empty source locator" % claim.id)
            if not locator.evidence_note.strip():
                result.errors.append("%s has an empty evidence note" % claim.id)
        if claim.truth_status == "established" and not claim.source_ids:
            result.errors.append("%s established claim has no source" % claim.id)
        if claim.conditional and "assumption" not in claim.notes.lower():
            result.warnings.append(
                "%s is conditional but notes do not name an assumption" % claim.id
            )
    return result

