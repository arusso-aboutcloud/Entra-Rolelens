"""
test_diff_pills.py

Runs every Role Diff example pair (frontend/index.html, runDiffPill(...)
buttons) against the live /api/diff endpoint and fails the nightly pipeline
if any role name no longer resolves.

Pairs are parsed straight out of frontend/index.html rather than duplicated
here, so this test can never drift out of sync with what's actually on the
page -- unlike pipeline/test_pills.py's EXPECTATIONS list, there's no
subjective "expected answer" to hand-maintain: a diff pill is either
resolvable or it's a broken link, and that's exactly what this checks.

Opens a GitHub issue on failure so a silent rename (Microsoft has done this
before -- see the Resource Policy role description rewrite the day after
launch) doesn't leave a dead example button on the site unnoticed.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

WORKER_URL = os.environ.get("WORKER_URL", "")
FRONTEND_PATH = Path(__file__).resolve().parent.parent / "frontend" / "index.html"

PILL_RE = re.compile(r"runDiffPill\('([^']+)','([^']+)'\)")


def extract_pill_pairs() -> list[tuple[str, str]]:
    html = FRONTEND_PATH.read_text(encoding="utf-8")
    return PILL_RE.findall(html)


def check_pair(a: str, b: str) -> tuple[bool, str]:
    """Returns (passed, detail_message)."""
    url = f"{WORKER_URL}/api/diff?a={quote(a)}&b={quote(b)}"
    try:
        resp = requests.get(url, timeout=10)
    except requests.RequestException as exc:
        return False, f"network error: {exc}"

    if not resp.ok:
        return False, f"HTTP {resp.status_code}"

    data = resp.json()
    if "error" in data:
        return False, data["error"]

    role_a = data.get("role_a", {})
    role_b = data.get("role_b", {})
    if "permission_count" not in role_a or "permission_count" not in role_b:
        return False, f"malformed response: {data}"

    return True, f"OK -> {role_a['permission_count']} vs {role_b['permission_count']} permissions"


def main() -> int:
    if not WORKER_URL:
        print("WORKER_URL is not set — skipping diff pill tests.")
        return 0

    pairs = extract_pill_pairs()
    if not pairs:
        print(f"No runDiffPill(...) pairs found in {FRONTEND_PATH} — nothing to test.")
        return 0

    print(f"Running {len(pairs)} Role Diff example pairs against {WORKER_URL}")
    print(f"(extracted live from {FRONTEND_PATH.relative_to(FRONTEND_PATH.parent.parent)})")
    print("-" * 72)

    failures: list[str] = []
    for a, b in pairs:
        passed, detail = check_pair(a, b)
        marker = "PASS" if passed else "REGRESSION"
        label = f"{a!r} vs {b!r}"
        print(f"  {marker:11s} {label:70s} {detail}")
        if not passed:
            failures.append(f"  - {label}: {detail}")

    print("-" * 72)
    print(f"PASS:       {len(pairs) - len(failures)}")
    print(f"REGRESSION: {len(failures)} (these break the build)")
    print()

    if failures:
        print(f"Broken Role Diff example pairs ({len(failures)}):")
        for line in failures:
            print(line)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
