import json
import urllib.error
import urllib.request
from typing import Dict, List

from .models import CheckResult, Source


USER_AGENT = "PureTateResearch/0.1 (citation audit)"


def _head_or_get(url: str, timeout: int) -> int:
    request = urllib.request.Request(url, method="HEAD")
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        if exc.code not in (403, 405):
            return int(exc.code)
    request = urllib.request.Request(url, method="GET")
    request.add_header("User-Agent", USER_AGENT)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read(1)
        return int(response.status)


def online_source_audit(
    sources: Dict[str, Source], timeout: int = 15
) -> CheckResult:
    result = CheckResult()
    for source in sources.values():
        urls: List[str] = [source.url]
        if source.doi:
            urls.append("https://doi.org/" + source.doi)
        for url in urls:
            if not url:
                continue
            try:
                status = _head_or_get(url, timeout)
            except (OSError, urllib.error.URLError) as exc:
                result.errors.append("%s unreachable at %s: %s" % (source.id, url, exc))
                continue
            if status >= 400:
                result.errors.append(
                    "%s returned HTTP %d at %s" % (source.id, status, url)
                )
    return result

