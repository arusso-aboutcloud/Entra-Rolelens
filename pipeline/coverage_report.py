"""
coverage_report.py

Reports task coverage for the role catalog: which built-in roles have at least
one in-scope task mapping (and are therefore offered as least-privilege search
results) versus which do not.

Most uncovered roles are expected — Microsoft's delegate-by-task page only lists
common admin tasks, so many niche roles never appear. The *actionable* signal is
narrower: built-in roles that are **new or undocumented (shadow)** yet have no
task. Those are the ones a maintainer may want to seed in data/tasks.json (until
Microsoft adds a task to the delegate-by-task page, after which the scraper takes
over automatically).

Outputs:
  - data/coverage.json     full breakdown (committed; can drive a UI stat)
  - stdout                 summary for the run log
  - GitHub issue           a single idempotent issue listing roles that need
                           attention, updated each run and auto-closed when empty
                           (only when GITHUB_TOKEN + GITHUB_REPO are set)
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
MASTER_PATH = DATA_DIR / "master.json"
CHANGELOG_PATH = DATA_DIR / "changelog.json"
COVERAGE_PATH = DATA_DIR / "coverage.json"

RECENT_DAYS = 60
GH_API = "https://api.github.com"
ISSUE_TITLE = "Roles awaiting task coverage"
ISSUE_LABEL = "coverage"


def load(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def recently_added_ids(changelog: list, cutoff: str) -> set:
    return {
        e.get("role_id")
        for e in (changelog or [])
        if e.get("change_type", "").upper() == "ADDED"
        and e.get("date", "") >= cutoff
        and e.get("role_id")
    }


def _slim(role: dict) -> dict:
    return {
        "id": role["id"],
        "displayName": role.get("displayName", role["id"]),
        "isShadowRole": bool(role.get("isShadowRole")),
    }


def upsert_issue(attention: list) -> None:
    """Maintain a single idempotent issue: create/update when roles need
    attention, close it when the list is empty. No-op without credentials."""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO") or os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        print("  (GITHUB_TOKEN/GITHUB_REPO not set -- skipping issue upsert)")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    existing = None
    q = requests.get(
        f"{GH_API}/repos/{repo}/issues",
        headers=headers,
        params={"state": "open", "labels": ISSUE_LABEL, "per_page": 100},
        timeout=15,
    )
    if q.ok:
        for it in q.json():
            if it.get("title") == ISSUE_TITLE and "pull_request" not in it:
                existing = it
                break

    if not attention:
        if existing:
            requests.patch(
                f"{GH_API}/repos/{repo}/issues/{existing['number']}",
                headers=headers,
                json={
                    "state": "closed",
                    "body": "All new/undocumented roles now have task coverage. ✅\n\n"
                            "_Closed automatically by `coverage_report.py`._",
                },
                timeout=15,
            )
            print(f"  Coverage issue #{existing['number']} closed (nothing awaiting coverage).")
        else:
            print("  Nothing awaiting coverage; no issue needed.")
        return

    lines = [
        "These built-in roles are **new or undocumented (shadow)** and have **no task mapping**,",
        "so they are not yet offered as least-privilege search results.",
        "",
        "Seed a task for the role in `data/tasks.json` (a manual feature area is preserved",
        "across scrapes via `MANUAL_FEATURE_AREAS` in `scrape_tasks.py`), or wait for Microsoft",
        "to add one to the [delegate-by-task page](https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/delegate-by-task)",
        "— the scraper then takes over automatically.",
        "",
        "| Role | Reason | Role ID |",
        "| --- | --- | --- |",
    ]
    for r in attention:
        reason = "shadow (in Graph API, not yet in docs)" if r["isShadowRole"] else "recently added"
        lines.append(f"| {r['displayName']} | {reason} | `{r['id']}` |")
    lines += ["", "_Maintained automatically by `coverage_report.py` on each nightly run._"]
    body = "\n".join(lines)

    if existing:
        requests.patch(
            f"{GH_API}/repos/{repo}/issues/{existing['number']}",
            headers=headers,
            json={"body": body, "state": "open"},
            timeout=15,
        )
        print(f"  Coverage issue #{existing['number']} updated ({len(attention)} role(s) awaiting coverage).")
    else:
        resp = requests.post(
            f"{GH_API}/repos/{repo}/issues",
            headers=headers,
            json={"title": ISSUE_TITLE, "body": body, "labels": [ISSUE_LABEL]},
            timeout=15,
        )
        if resp.ok:
            print(f"  Coverage issue opened: {resp.json().get('html_url', '')}")
        else:
            print(f"  Failed to open coverage issue: HTTP {resp.status_code}", file=sys.stderr)


def main() -> None:
    master = load(MASTER_PATH)
    if not master:
        print("ERROR: data/master.json not found -- run enrich.py first", file=sys.stderr)
        sys.exit(1)
    changelog = load(CHANGELOG_PATH, [])

    roles = master.get("roles", [])
    tasks = master.get("tasks", [])

    covered_ids = {
        t.get("role_id") for t in tasks
        if t.get("role_id") and not t.get("out_of_scope")
    }

    builtin = [r for r in roles if r.get("isBuiltIn", True)]
    uncovered = [r for r in builtin if r.get("id") not in covered_ids]

    cutoff = (date.today() - timedelta(days=RECENT_DAYS)).isoformat()
    recent_ids = recently_added_ids(changelog, cutoff)

    attention = sorted(
        (_slim(r) for r in uncovered if r.get("isShadowRole") or r.get("id") in recent_ids),
        key=lambda r: r["displayName"].lower(),
    )

    covered_n = len(builtin) - len(uncovered)
    pct = round(100 * covered_n / len(builtin), 1) if builtin else 0.0

    coverage = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "builtin_role_count": len(builtin),
        "covered_role_count": covered_n,
        "coverage_pct": pct,
        "uncovered_role_count": len(uncovered),
        "attention_count": len(attention),
        "attention": attention,
        "uncovered": sorted((_slim(r) for r in uncovered), key=lambda r: r["displayName"].lower()),
    }
    COVERAGE_PATH.write_text(
        json.dumps(coverage, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Task coverage: {covered_n}/{len(builtin)} built-in roles ({pct}%) have >=1 task")
    print(f"  {len(uncovered)} uncovered total; {len(attention)} new/undocumented need attention")
    for r in attention:
        print(f"    - {r['displayName']} ({'shadow' if r['isShadowRole'] else 'recent'})")
    print(f"Written -> {COVERAGE_PATH}")

    upsert_issue(attention)


if __name__ == "__main__":
    main()
