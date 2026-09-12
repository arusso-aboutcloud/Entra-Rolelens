"""
generate_scenarios.py

For each ADDED changelog entry, and each MODIFIED/permissions entry, computes
deterministic "role facts" (is it privileged, is it PIM-eligible, does it
support administrative-unit-scoped assignment, where is it configured) and --
for entries missing a "scenario" -- calls Cloudflare Workers AI for a short
real-world narrative that can reference those facts. Rendered in the
frontend's What's New panel: the verified facts as badges (always accurate,
since they're not AI-generated) for a new role, the narrative labeled
"AI-generated" alongside them.

Only ADDED and MODIFIED/permissions entries get a scenario. Description
updates, renames, and privilege flips deliberately do not: a description
change already shows an exact word-diff of what Microsoft reworded (an AI
paraphrase adds little), and a privilege flip already carries a deterministic
"why" explanation in the frontend (_wnDetailInner's wn-privnote) that's more
reliable than an LLM guess. A permission change, like a new role, represents
an actual capability change -- something the person assigned this role can
now do (or can no longer do) -- which is exactly the kind of concrete "why
would I care" narrative a scenario is good at.

Role facts are recomputed for every eligible entry on every run (pure local
computation, no network cost) so historical entries stay current too, not
just newly-changed ones. Scenario generation stays idempotent/best-effort --
only entries missing "scenario" are (re)processed, so a failed AI call is
retried automatically next run without duplicating work, and a missing
scenario just means the panel falls back to the facts + description only
(new role) or the added/removed permission list alone (permission change).

Cost stays trivial even with this wider scope: ~12 eligible entries/month
across the full changelog history to date (roughly 1 new role + 7 permission
changes/month), each call in the tens of neurons, against Workers AI's
10,000 free neurons/day.

Light continuity ("memory"): when a role has a prior scenario already on
record (from an earlier change to the same role), it's included in the
prompt as tone-consistency context -- read straight out of the changelog
history that's already persisted, no new storage or service needed.
"""

import json
import os
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
CHANGELOG_PATH = DATA_DIR / "changelog.json"
# master.json (enriched, union of live Graph API + docs) rather than the
# docs-only roles.json -- keeps role_facts/scenarios based on the same
# authoritative permission set diff_roles.py now diffs and push_to_cloudflare.py
# pushes live, instead of the docs snapshot that can lag Microsoft's live grants.
MASTER_PATH = DATA_DIR / "master.json"

CF_BASE = "https://api.cloudflare.com/client/v4"
MODEL = "@cf/meta/llama-3.3-70b-instruct-fp8-fast"

# Microsoft's exact, published list of built-in roles that support
# administrative-unit-scoped assignment (verified against
# learn.microsoft.com/entra/identity/role-based-access-control/
# administrative-units-role-assignment, updated 2026-02-19). This is NOT a
# guessable pattern -- most roles are tenant-scope only -- so it's hardcoded
# rather than left for the AI to infer.
AU_SCOPABLE_ROLES = frozenset({
    "Authentication Administrator",
    "Attribute Assignment Administrator",
    "Attribute Assignment Reader",
    "Cloud Device Administrator",
    "Groups Administrator",
    "Helpdesk Administrator",
    "License Administrator",
    "Password Administrator",
    "Printer Administrator",
    "Privileged Authentication Administrator",
    "SharePoint Administrator",
    "Teams Administrator",
    "Teams Devices Administrator",
    "User Administrator",
})


def compute_role_facts(role: dict) -> dict:
    """Deterministic, verified facts about a role -- no AI involved, so
    these are never wrong the way a generated sentence could be."""
    is_workload_role = len(role.get("permissions", [])) == 0
    return {
        "is_privileged": bool(role.get("isPrivileged")),
        # Workload roles (e.g. Purview content roles) grant zero Entra
        # directory actions and are governed in their own service portal,
        # not Entra RBAC -- so Entra PIM/admin-unit scoping don't apply.
        "is_workload_role": is_workload_role,
        "pim_eligible": not is_workload_role,
        "au_scopable": role.get("displayName") in AU_SCOPABLE_ROLES,
        "configured_via": (
            "its own service portal (not the Entra admin center)" if is_workload_role
            else "Microsoft Entra admin center (Roles & admins) or Microsoft Graph"
        ),
    }


def _facts_text(facts: dict) -> str:
    return (
        f"Privileged role: {'yes' if facts['is_privileged'] else 'no'}. "
        f"PIM-eligible for time-bound activation: {'yes' if facts['pim_eligible'] else 'not applicable -- governed outside Entra RBAC'}. "
        f"Administrative-unit-scoped assignment: {'supported' if facts['au_scopable'] else 'not supported -- tenant-wide only'}. "
        f"Configured via: {facts['configured_via']}."
    )


def _prior_scenario(changelog: list[dict], role_id: str, exclude: dict) -> str | None:
    """Most recent previously-generated scenario for this same role, if any
    -- e.g. its own "new role" scenario, or an earlier permission-change one.
    Used as light tone-consistency context, not fact grounding (the facts
    text already carries anything that needs to be accurate). This is the
    whole "persistent memory" mechanism: re-reading changelog history that's
    already committed to the repo, no vector store or extra service needed
    at this call volume."""
    candidates = [
        e for e in changelog
        if e is not exclude and e.get("role_id") == role_id and e.get("scenario")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: e.get("date", ""))
    return candidates[-1]["scenario"]


def _continuity_text(prior: str | None) -> str:
    if not prior:
        return ""
    return (
        f"\n\nA previously written scenario for this same role (context only, for tone "
        f"consistency -- describe the NEW change above, do not repeat or restate this one): "
        f"{prior}"
    )


def _run_workers_ai(prompt: str, role_name: str, account_id: str, token: str) -> str | None:
    url = f"{CF_BASE}/accounts/{account_id}/ai/run/{MODEL}"
    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": prompt}]},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f"  WARN: Workers AI request failed for {role_name!r}: {exc}", file=sys.stderr)
        return None
    if not resp.ok:
        print(f"  WARN: Workers AI HTTP {resp.status_code} for {role_name!r}: "
              f"{resp.text[:200]}", file=sys.stderr)
        return None
    try:
        text = resp.json().get("result", {}).get("response", "").strip()
    except (ValueError, AttributeError):
        return None
    return text or None


def generate_scenario(
    role: dict, facts: dict, account_id: str, token: str, prior: str | None = None
) -> str | None:
    perms = role.get("permissions", [])
    perms_text = ", ".join(perms) if perms else "(none -- this role is governed outside Entra)"
    prompt = (
        f"Role: {role['displayName']}\n"
        f"Official Microsoft description: {role.get('description', '')}\n"
        f"Exact Microsoft Entra permissions this role grants: {perms_text}\n"
        f"Verified facts about this role (state these accurately if you reference them -- do not "
        f"contradict or guess beyond them): {_facts_text(facts)}\n\n"
        "Write one or two sentences describing a concrete, technically specific scenario in which "
        "a Microsoft Entra (Azure AD) tenant administrator would assign this role to someone on "
        "their IT, security, or compliance team. Ground the scenario in what the permissions above "
        "actually let the person do -- name a real operational trigger (e.g. an active security "
        "incident, a compliance audit, an access review, an AI/agent deployment, a Purview "
        "eDiscovery case), not a generic 'IT support' or vacation-coverage story. The role name is "
        "Microsoft's internal label for a permission set, not a job title -- never invent an "
        "unrelated real-world job from it (e.g. do not read \"Writer\" as a marketing content "
        "writer). Plain prose, no markdown, no preamble, do not restate the role name verbatim, do "
        "not restate the verified facts verbatim (they're shown separately) -- only weave them in "
        "naturally if it helps the scenario (e.g. 'because this is a privileged, PIM-eligible role...')."
        + _continuity_text(prior)
    )
    return _run_workers_ai(prompt, role["displayName"], account_id, token)


def generate_permission_change_scenario(
    role: dict,
    facts: dict,
    added: list[str],
    removed: list[str],
    account_id: str,
    token: str,
    prior: str | None = None,
) -> str | None:
    """Scenario for a MODIFIED/permissions changelog entry -- grounded in the
    specific delta (what was actually added or removed), not the role's full
    permission set, since the reader already sees the full added/removed
    list rendered right above this in the UI; restating it would be noise.

    Mixed add+remove in one entry is described from the addition's side,
    matching the frontend's own least-privilege-safe bias for this exact
    case (see _wnPermGlowBadge): a newly granted permission is the more
    consequential direction for someone deciding whether an existing
    assignment now grants more than intended.
    """
    if added:
        delta_text = f"Permission(s) newly ADDED to this role: {', '.join(added)}."
        direction = (
            "Write one sentence describing a concrete, technically specific scenario in which the "
            "newly added permission(s) above let someone already assigned this role do something "
            "they could not do before. Name a real operational trigger, not a generic restatement "
            "of the permission."
        )
    else:
        delta_text = f"Permission(s) REMOVED from this role: {', '.join(removed)}."
        direction = (
            "Write one sentence describing what someone assigned this role can no longer do "
            "because of the permission(s) removed above, framed as something a tenant admin "
            "reviewing this role should be aware of (e.g. an existing automation or workflow that "
            "relied on it may now need a different role)."
        )
    prompt = (
        f"Role: {role['displayName']}\n"
        f"Official Microsoft description: {role.get('description', '')}\n"
        f"{delta_text}\n"
        f"Verified facts about this role (state these accurately if you reference them -- do not "
        f"contradict or guess beyond them): {_facts_text(facts)}\n\n"
        f"{direction} The role name is Microsoft's internal label for a permission set, not a job "
        "title -- never invent an unrelated real-world job from it. Plain prose, no markdown, no "
        "preamble, do not restate the role name or the permission string(s) verbatim (they're "
        "shown separately)."
        + _continuity_text(prior)
    )
    return _run_workers_ai(prompt, role["displayName"], account_id, token)


def main() -> None:
    if not CHANGELOG_PATH.exists() or not MASTER_PATH.exists():
        print("No changelog.json/master.json yet -- skipping scenario generation")
        return

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    token = os.environ.get("CLOUDFLARE_API_TOKEN")

    changelog = json.loads(CHANGELOG_PATH.read_text(encoding="utf-8"))
    master = json.loads(MASTER_PATH.read_text(encoding="utf-8"))
    roles_by_id = {r["id"]: r for r in master.get("roles", master)}

    changed = False
    generated = 0
    facts_updated = 0
    for entry in changelog:
        change_type = entry.get("change_type")
        is_added = change_type == "ADDED"
        is_perm_change = change_type == "MODIFIED" and entry.get("field") == "permissions"
        if not is_added and not is_perm_change:
            continue
        role = roles_by_id.get(entry.get("role_id"))
        if not role:
            continue

        # Deterministic, zero-cost -- recomputed every run so historical
        # entries stay current too, not just newly-changed ones. Only
        # persisted on ADDED entries (the frontend renders it as badges for a
        # new role); a permission-change entry uses it purely as in-memory
        # prompt grounding, so there's nothing worth writing back for it.
        facts = compute_role_facts(role)
        if is_added and entry.get("role_facts") != facts:
            entry["role_facts"] = facts
            changed = True
            facts_updated += 1

        if "scenario" in entry or not account_id or not token:
            continue

        prior = _prior_scenario(changelog, entry.get("role_id"), entry)
        if is_added:
            scenario = generate_scenario(role, facts, account_id, token, prior)
        else:
            added = entry.get("added_permissions") or []
            removed = entry.get("removed_permissions") or []
            if not added and not removed:
                continue
            scenario = generate_permission_change_scenario(
                role, facts, added, removed, account_id, token, prior
            )
        if scenario:
            entry["scenario"] = scenario
            changed = True
            generated += 1
            print(f"  Generated scenario for {role['displayName']!r} ({change_type}/{entry.get('field')})")

    if not account_id or not token:
        print("CLOUDFLARE_ACCOUNT_ID/CLOUDFLARE_API_TOKEN not set -- skipped AI scenario generation "
              "(role facts still computed)")

    if changed:
        CHANGELOG_PATH.write_text(
            json.dumps(changelog, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    print(f"Scenario generation complete -- {generated} scenario(s) generated, "
          f"{facts_updated} role_facts entries updated")


if __name__ == "__main__":
    main()
