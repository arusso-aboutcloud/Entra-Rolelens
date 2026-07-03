"""
security_summary.py

Writes data/security.json with the current Trivy vulnerability posture, read
from GitHub code-scanning (the Trivy SARIF the security workflow uploads). Lets
the app show a live daily security status. Reflects exactly what's in
GitHub Security -> Code scanning. Safe on any error: writes an 'unknown' status
rather than failing the pipeline.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(__file__).parent.parent / "data" / "security.json"
GH_API = "https://api.github.com"


def fetch_open_alerts(repo: str, token: str) -> list:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    alerts, page = [], 1
    while True:
        r = requests.get(
            f"{GH_API}/repos/{repo}/code-scanning/alerts",
            headers=headers,
            params={"state": "open", "per_page": 100, "page": page},
            timeout=20,
        )
        if not r.ok:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        batch = r.json()
        alerts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return alerts


def main() -> None:
    summary = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "tool": "Trivy",
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "total": 0,
        "status": "unknown",
    }

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO") or os.environ.get("GITHUB_REPOSITORY")

    if token and repo:
        try:
            trivy = [
                a for a in fetch_open_alerts(repo, token)
                if (a.get("tool") or {}).get("name") == "Trivy"
            ]
            for a in trivy:
                sev = ((a.get("rule") or {}).get("security_severity_level") or "").lower()
                if sev in ("critical", "high", "medium", "low"):
                    summary[sev] += 1
            summary["total"] = len(trivy)
            summary["status"] = "clean" if summary["total"] == 0 else "issues"
            print(
                f"  Trivy code-scanning: {summary['total']} open "
                f"(C{summary['critical']} H{summary['high']} "
                f"M{summary['medium']} L{summary['low']}) -> {summary['status']}"
            )
        except Exception as exc:  # noqa: BLE001 - never fail the pipeline for this
            print(f"  WARN: could not read code-scanning alerts ({exc}) — status 'unknown'",
                  file=sys.stderr)
    else:
        print("  (GITHUB_TOKEN/GITHUB_REPO not set — security status 'unknown')")

    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Written -> {OUT}")


if __name__ == "__main__":
    main()
