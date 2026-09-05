"""
generate_scenarios.py

For each ADDED changelog entry that doesn't yet have a "scenario" field,
calls Cloudflare Workers AI to generate a short, concrete real-world scenario
describing when an admin would need that role. Rendered in the frontend's
What's New panel alongside the role's official description.

Best-effort and idempotent: only processes entries missing "scenario", so a
failed run is retried automatically next time without duplicating work, and
a missing scenario just means the panel falls back to the description only
(this feature didn't exist before). Costs effectively nothing -- typically
0-3 new roles a month against Workers AI's 10,000 free neurons/day.
"""

import json
import os
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
CHANGELOG_PATH = DATA_DIR / "changelog.json"
ROLES_PATH = DATA_DIR / "roles.json"

CF_BASE = "https://api.cloudflare.com/client/v4"
MODEL = "@cf/meta/llama-3.1-8b-instruct-fast"


def generate_scenario(role: dict, account_id: str, token: str) -> str | None:
    perms = role.get("permissions", [])
    perms_text = ", ".join(perms) if perms else "(none -- this role is governed outside Entra)"
    prompt = (
        f"Role: {role['displayName']}\n"
        f"Official description: {role.get('description', '')}\n"
        f"Grants exactly these Microsoft Entra permissions: {perms_text}\n\n"
        "In exactly one or two sentences, describe a realistic day-to-day scenario in "
        "which a Microsoft Entra admin would assign this role to someone. Plain prose, "
        "no markdown, no preamble, do not restate the role name verbatim."
    )
    url = f"{CF_BASE}/accounts/{account_id}/ai/run/{MODEL}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  WARN: Workers AI request failed for {role['displayName']!r}: {exc}",
              file=sys.stderr)
        return None
    if not resp.ok:
        print(f"  WARN: Workers AI HTTP {resp.status_code} for {role['displayName']!r}: "
              f"{resp.text[:200]}", file=sys.stderr)
        return None
    try:
        text = resp.json().get("result", {}).get("response", "").strip()
    except (ValueError, AttributeError):
        return None
    return text or None


def main() -> None:
    if not CHANGELOG_PATH.exists() or not ROLES_PATH.exists():
        print("No changelog.json/roles.json yet -- skipping scenario generation")
        return

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not token:
        print("CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN not set -- skipping scenario generation")
        return

    changelog = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
    roles_by_id = {r["id"]: r for r in json.loads(ROLES_PATH.read_text(encoding="utf-8"))}

    changed = False
    generated = 0
    for entry in changelog:
        if entry.get("change_type") != "ADDED" or "scenario" in entry:
            continue
        role = roles_by_id.get(entry.get("role_id"))
        if not role:
            continue
        scenario = generate_scenario(role, account_id, token)
        if scenario:
            entry["scenario"] = scenario
            changed = True
            generated += 1
            print(f"  Generated scenario for {role['displayName']!r}")

    if changed:
        CHANGELOG_PATH.write_text(
            json.dumps(changelog, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(f"Scenario generation complete -- {generated} generated")


if __name__ == "__main__":
    main()
