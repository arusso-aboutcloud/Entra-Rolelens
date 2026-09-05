"""
check_ai_model.py

Keeps generate_scenarios.py's Cloudflare Workers AI model current as
Cloudflare deprecates models over time (18 models were retired in one wave
on 2026-05-30). Run weekly (check-ai-model.yml), not nightly -- the model
catalog changes far less often than role data.

Cloudflare deprecates models via a changelog post naming a retirement date,
not a structured "use X instead" API field, so there is no way to derive
the *correct* replacement purely from data. Trade-off: this script walks a
small hand-maintained CANDIDATES list and switches to the first entry that
is (a) still in Workers AI's live catalog, (b) not flagged deprecated, and
(c) actually returns a completion in a live smoke test -- so a candidate
that's merely listed but broken/renamed never gets written. Only if every
candidate fails does it fall back to opening a GitHub issue asking a human
to add fresh options -- the one case true automation can't solve without
guessing.
"""

import os
import re
import sys
from pathlib import Path

import requests

GENERATE_SCENARIOS_PATH = Path(__file__).parent / "generate_scenarios.py"
CF_BASE = "https://api.cloudflare.com/client/v4"
GH_API = "https://api.github.com"
ISSUE_TITLE = "Workers AI model candidates all deprecated -- generate_scenarios.py needs new options"
ISSUE_LABEL = "pipeline-failure"

# Ordered by output quality first (call volume is 0-3/month, so cost is a
# non-factor at any of these sizes) -- smaller/cheaper models are kept as
# fallbacks for resilience, not preferred. This list is the one manual
# judgment call the API can't make for us (no "recommended replacement"
# field exists) -- refresh it occasionally as Cloudflare's catalog evolves.
CANDIDATES = [
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
    "@cf/google/gemma-4-26b-a4b-it",
    "@cf/zai-org/glm-4.7-flash",
    "@cf/moonshotai/kimi-k2.6",
    "@cf/meta/llama-3.1-8b-instruct-fast",
    "@cf/meta/llama-3.2-3b-instruct",
]

MODEL_RE = re.compile(r'^MODEL = "([^"]+)"$', re.MULTILINE)


def get_live_models(account_id: str, token: str) -> dict[str, bool]:
    """Returns {model_name: is_deprecated}, including models still inside
    their post-deprecation grace window (include_deprecated=true) so a model
    on its way out is caught before it hard-fails."""
    url = f"{CF_BASE}/accounts/{account_id}/ai/models/search"
    live: dict[str, bool] = {}
    page = 1
    while True:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            params={"include_deprecated": "true", "per_page": 100, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("result", [])
        if not results:
            break
        for m in results:
            name = m.get("name")
            if not name:
                continue
            props = m.get("properties")
            deprecated = bool(props.get("deprecated")) if isinstance(props, dict) else bool(m.get("deprecated"))
            live[name] = deprecated
        if len(results) < 100:
            break
        page += 1
    return live


def smoke_test(account_id: str, token: str, model: str) -> bool:
    url = f"{CF_BASE}/accounts/{account_id}/ai/run/{model}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "Reply with the single word: OK"}]},
            timeout=20,
        )
    except requests.RequestException:
        return False
    if not resp.ok:
        return False
    try:
        text = resp.json().get("result", {}).get("response", "")
    except ValueError:
        return False
    return bool(text and text.strip())


def read_current_model() -> str | None:
    text = GENERATE_SCENARIOS_PATH.read_text(encoding="utf-8")
    m = MODEL_RE.search(text)
    return m.group(1) if m else None


def write_model(new_model: str) -> None:
    text = GENERATE_SCENARIOS_PATH.read_text(encoding="utf-8")
    text = MODEL_RE.sub(f'MODEL = "{new_model}"', text, count=1)
    GENERATE_SCENARIOS_PATH.write_text(text, encoding="utf-8")


def open_no_candidates_issue(current: str) -> None:
    """Idempotent issue -- mirrors coverage_report.upsert_issue()'s pattern."""
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

    body = (
        f"`pipeline/check_ai_model.py` could not find a working, non-deprecated model for "
        f"`generate_scenarios.py`. Current configured model: `{current}`.\n\n"
        "All entries in `CANDIDATES` are deprecated, missing from the catalog, or failed "
        "a live smoke test:\n\n"
        + "\n".join(f"- `{c}`" for c in CANDIDATES)
        + "\n\nAdd fresh candidates from https://developers.cloudflare.com/workers-ai/models/ "
        "(prefer small/cheap instruct-class text-generation models, smallest first) and "
        "re-run the \"Check AI model\" workflow.\n\n"
        "_Maintained automatically by `check_ai_model.py`. Closes itself once a candidate works._"
    )

    if existing:
        requests.patch(
            f"{GH_API}/repos/{repo}/issues/{existing['number']}",
            headers=headers, json={"body": body, "state": "open"}, timeout=15,
        )
        print(f"  Issue #{existing['number']} updated.")
    else:
        resp = requests.post(
            f"{GH_API}/repos/{repo}/issues",
            headers=headers,
            json={"title": ISSUE_TITLE, "body": body, "labels": [ISSUE_LABEL]},
            timeout=15,
        )
        if resp.ok:
            print(f"  Issue opened: {resp.json().get('html_url', '')}")
        else:
            print(f"  Failed to open issue: HTTP {resp.status_code}", file=sys.stderr)


def close_no_candidates_issue() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPO") or os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    q = requests.get(
        f"{GH_API}/repos/{repo}/issues",
        headers=headers,
        params={"state": "open", "labels": ISSUE_LABEL, "per_page": 100},
        timeout=15,
    )
    if not q.ok:
        return
    for it in q.json():
        if it.get("title") == ISSUE_TITLE and "pull_request" not in it:
            requests.patch(
                f"{GH_API}/repos/{repo}/issues/{it['number']}",
                headers=headers,
                json={"state": "closed",
                      "body": "A working candidate was found. ✅\n\n"
                              "_Closed automatically by `check_ai_model.py`._"},
                timeout=15,
            )
            print(f"  Issue #{it['number']} closed (candidate found).")
            break


def main() -> None:
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not token:
        print("CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN not set -- skipping model check")
        return

    current = read_current_model()
    if not current:
        print("ERROR: could not find MODEL = \"...\" in generate_scenarios.py", file=sys.stderr)
        sys.exit(1)

    try:
        live = get_live_models(account_id, token)
    except requests.RequestException as exc:
        print(f"WARN: could not fetch Workers AI model list ({exc}) -- skipping check",
              file=sys.stderr)
        return

    current_ok = live.get(current) is False  # present in catalog AND not deprecated
    if current_ok:
        print(f"Current model {current!r} is active and not deprecated -- nothing to do")
        return

    print(f"Current model {current!r} is deprecated or no longer listed -- "
          f"looking for a replacement")

    for candidate in CANDIDATES:
        if candidate == current:
            continue
        if live.get(candidate) is not False:
            print(f"  skip {candidate!r}: not active in current catalog")
            continue
        if not smoke_test(account_id, token, candidate):
            print(f"  skip {candidate!r}: failed live smoke test")
            continue
        print(f"  selected replacement: {candidate!r}")
        write_model(candidate)
        close_no_candidates_issue()
        print(f"MODEL_CHANGED={candidate}")
        return

    print("No healthy candidate found -- opening tracking issue", file=sys.stderr)
    open_no_candidates_issue(current)


if __name__ == "__main__":
    main()
