<div align="center">

![Entra RoleLens](assets/project-banner.png)

# Entra RoleLens

[![Live](https://img.shields.io/website?url=https%3A%2F%2Fentrarolelens.aboutcloud.io&label=live&style=flat-square&color=00E5A3)](https://entrarolelens.aboutcloud.io)
[![Pipeline](https://img.shields.io/github/actions/workflow/status/arusso-aboutcloud/entra-rolelens/refresh.yml?label=nightly%20pipeline&style=flat-square&branch=master&color=00E5A3)](https://github.com/arusso-aboutcloud/entra-rolelens/actions)
[![Last commit](https://img.shields.io/github/last-commit/arusso-aboutcloud/entra-rolelens/master?style=flat-square&color=00E5A3)](https://github.com/arusso-aboutcloud/entra-rolelens/commits/master)
[![License](https://img.shields.io/badge/license-MIT-38BDF8?style=flat-square)](LICENSE)
[![Roles](https://img.shields.io/badge/dynamic/json?url=https://rolelens-worker.russo-antonio76.workers.dev/api/status&query=role_count&label=roles&color=0078D4&logo=microsoft&style=flat-square)](https://entrarolelens.aboutcloud.io)
[![Tasks](https://img.shields.io/badge/dynamic/json?url=https://rolelens-worker.russo-antonio76.workers.dev/api/status&query=task_count&label=tasks&color=0078D4&logo=microsoft&style=flat-square)](https://entrarolelens.aboutcloud.io)
[![Unlisted roles](https://img.shields.io/badge/dynamic/json?url=https://rolelens-worker.russo-antonio76.workers.dev/api/status&query=shadow_role_count&label=unlisted%20roles&color=E5A300&style=flat-square)](https://entrarolelens.aboutcloud.io)
[![Stars](https://img.shields.io/github/stars/arusso-aboutcloud/entra-rolelens?style=flat-square&color=00E5A3)](https://github.com/arusso-aboutcloud/entra-rolelens/stargazers)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-00E5A3?style=flat-square)](CONTRIBUTING.md)

[![LinkedIn](https://img.shields.io/badge/Connect%20on%20LinkedIn-Antonio%20Russo-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/antonio-russo-9295731b/)

**[entrarolelens.aboutcloud.io](https://entrarolelens.aboutcloud.io)** · [Report a mapping error](https://github.com/arusso-aboutcloud/entra-rolelens/issues) · [Request a task](https://github.com/arusso-aboutcloud/entra-rolelens/issues)

</div>

---

## What is Entra RoleLens?

You describe a task — *"reset a user's MFA"*, *"read audit logs"*, *"manage Conditional Access policies"* — and Entra RoleLens returns the minimum built-in Entra ID role required to do it, and nothing more. You can also compare any two roles side by side and see exactly what one has that the other lacks, permission by permission.

**It replaces the 50-tab Microsoft docs crawl that every Entra admin does when someone asks: "what role do I assign without giving them too much?"**

---

## Features

| Mode | What it does |
|------|-------------|
| **Task → Role** | Describe what you need to do in plain language. Get back the minimum built-in role, a direct link to Microsoft's source, and a privilege warning if the role is elevated. |
| **Role Diff** | Select any two built-in roles. See every permission one has that the other lacks in a clean three-column view — unique to A, shared, unique to B. |
| **What's New timeline** | A live feed of what Microsoft changed in the role catalog — which permissions were added/removed, privilege reclassifications, and brand-new roles — each entry expandable to the exact permissions. |
| **Shadow Detection** | Roles present in the Graph API but absent from public documentation are flagged as `isShadowRole: true` — catching unreleased Microsoft roles before announcement. |
| **Always current** | The full role catalog and task mappings refresh nightly via a secure, passwordless OIDC pipeline. Every change Microsoft makes is detected, logged, and live by morning. |

---

## Shadow role detection

Entra RoleLens cross-references the live Microsoft Graph API against Microsoft's public documentation on every nightly run. Roles that exist in the API but are not yet documented are flagged as **shadow roles** — this means the tool can surface new Microsoft roles before they appear in any documentation.

The shadow role count is logged in every pipeline run and visible in the pipeline status endpoint:
`GET /api/status` → `shadow_role_count`

---

## Task coverage

A role only appears as a least-privilege *recommendation* once a task points to it. Task mappings are scraped nightly from Microsoft's [delegate-by-task](https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/delegate-by-task) page, so most roles map themselves automatically. The exceptions are brand-new or shadow roles Microsoft hasn't documented yet.

`coverage_report.py` runs every night and:

- writes [`data/coverage.json`](data/coverage.json) with the full breakdown (covered vs. uncovered roles), and
- maintains a single idempotent **[Roles awaiting task coverage](https://github.com/arusso-aboutcloud/entra-rolelens/issues?q=label%3Acoverage)** issue listing only the *new/undocumented* roles that still need a task — updated each run and closed automatically when the list is empty. Implicit/default directory roles and **zero-permission workload roles** (e.g. Purview content roles, which grant no Entra directory actions and are governed in their own service portal) are excluded — they can't take a task mapping.

This keeps the one remaining manual step — seeding a task for a role Microsoft hasn't documented yet — explicit and visible, rather than silent.

---

## What's new

> Auto-generated from the nightly pipeline · Last updated by GitHub Actions

<!-- WHATS_NEW_START -->
- 🔄 **Tenant Governance Administrator** — modified (2026-07-18)
- 🔄 **Security Operator** — modified (2026-07-10)
- 🔄 **Agent ID Administrator** — modified (2026-07-02)
- 🔄 **Security Operator** — modified (2026-07-02)
- 🔄 **Tenant Governance Administrator** — modified (2026-07-02)
- 🔄 **Tenant Governance Reader** — modified (2026-07-02)
- 🔄 **Tenant Governance Relationship Administrator** — modified (2026-07-02)
- 🔄 **Tenant Governance Relationship Reader** — modified (2026-07-02)
- 🔄 **AI Administrator** — modified (2026-06-26)
- 🔄 **AI Reader** — modified (2026-06-26)
<!-- WHATS_NEW_END -->

---

## Architecture

[![Architecture](assets/pipeline-auth.svg)](assets/pipeline-auth.svg)

---

## Code quality

This codebase is continuously monitored for structural quality. Every nightly pipeline run validates that the architectural rules in [`.sentrux/rules.toml`](.sentrux/rules.toml) hold, and reports the latest quality score below.

The check runs via [Sentrux](https://github.com/sentrux/sentrux), a free open-source structural quality gate. The score reflects metrics like cyclic-dependency count, coupling between modules, and file-size distribution — informational only, never blocking the pipeline.

<!-- SENTRUX_QUALITY_START -->
<a href="assets/quality-dashboard.svg" target="_blank">
  <img src="assets/quality-dashboard.svg" alt="Code quality dashboard" width="720"/>
</a>

_Auto-generated by [Sentrux](https://github.com/sentrux/sentrux) on every nightly pipeline run._
<!-- SENTRUX_QUALITY_END -->

---

## Security

Dependencies are scanned for vulnerabilities on every push to master and weekly on Sundays using [Trivy](https://github.com/aquasecurity/trivy). Results (HIGH and CRITICAL CVEs) are uploaded to **GitHub Security → Code Scanning**. The dashboard below is regenerated and committed automatically after each scan.

<!-- TRIVY_SECURITY_START -->
<a href="assets/security-dashboard.svg" target="_blank">
  <img src="assets/security-dashboard.svg" alt="Security scan dashboard" width="720"/>
</a>

_Auto-generated by [Trivy](https://github.com/aquasecurity/trivy) v0.28.0 on every push and weekly scan._
<!-- TRIVY_SECURITY_END -->

---

## Technical stack

| Layer | Technology | Cost |
|-------|-----------|------|
| Frontend | Cloudflare Pages · Global CDN · 330+ PoPs | €0 |
| API | Cloudflare Workers · TypeScript · 6 routes | €0 |
| Database | Cloudflare D1 · SQLite · 144 roles · 237 tasks | €0 |
| Cache | Cloudflare KV · master.json · pipeline_status | €0 |
| Auth | Entra ID · Workload Identity Federation · OIDC | €0 |
| Pipeline | GitHub Actions · Python 3.11 · nightly cron | €0 |
| Analytics | Umami · self-hosted · privacy-first | €0 |
| Domain | aboutcloud.io · already owned | €0 |
| **Total** | | **€0 / month** |

**Search engine:** Pure SQL keyword matching against a weighted `task_search` table. Keywords extracted in the Worker, matched against D1. No LLM in the query path. Median response time: **< 5ms**.

---

## Passwordless pipeline — how authentication works

The nightly pipeline authenticates to Microsoft Entra ID without any stored credentials using **Workload Identity Federation**:

[![Pipeline Authentication](assets/pipeline-auth.png)](assets/pipeline-auth.png)

```
GitHub Actions requests a short-lived OIDC JWT from GitHub's identity provider
        │
        ▼
Microsoft Entra ID validates the JWT against a Federated Credential
  (scoped to: repo=arusso-aboutcloud/entra-rolelens, branch=master)
        │
        ▼
Entra ID issues a temporary access token — no secret stored anywhere
        │
        ▼
fetch_roles.py calls graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions
```

GitHub secrets required: `AZURE_CLIENT_ID` + `AZURE_TENANT_ID` only. No client secret. No certificate.

---

## How it stays accurate — the self-sustaining pipeline

This tool requires zero manual maintenance for daily operation. Every night at **01:00 UTC**, a GitHub Actions workflow runs automatically:

```
01:00 UTC — GitHub Actions wakes up (free tier · ~3 min runtime)
│
├── azure/login@v2     OIDC handshake → temporary Entra access token
│                      (Workload Identity Federation · EntraRoleFetcher-API)
│
├── fetch_roles.py     Calls Microsoft Graph API via OIDC token (live source of truth)
│   ├── Graph API      graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions
│   │                  Authenticated via OIDC token
│   │                  → data/roles_graph_raw.json  (source of truth for IDs; permissions reconciled with docs)
│   └── Docs scrape    Also scrapes MicrosoftDocs/entra-docs for descriptions
│                      → data/roles.json            (human-readable metadata)
│
├── scrape_tasks.py    Scrapes the Microsoft Learn least-privileged-by-task page
│                      Parses 237 task → minimum role mappings across 41 feature areas
│                      → data/tasks.json
│
├── diff_roles.py      Compares today's roles against yesterday's snapshot
│                      Detects ADDED, REMOVED, and MODIFIED roles
│                      Logs every change with timestamp to D1 role_changes table
│
├── enrich.py          Cross-references roles_graph_raw.json vs roles.json
│                      Permissions = union of Graph + docs (never under-states a role)
│                      Roles in Graph API but not in docs → isShadowRole: true
│                      Builds master.json and resolves role names to IDs
│
├── validate.py        Schema and quality checks
│                      On failure: auto-opens a GitHub Issue and aborts the push
│                      The live data is never overwritten with invalid data
│
├── coverage_report.py Flags new/undocumented roles that have no task mapping yet
│                      → data/coverage.json  (covered vs. uncovered breakdown)
│                      Maintains one idempotent "Roles awaiting task coverage" issue
│
└── push_to_cloudflare.py
                       Pushes master.json to Cloudflare KV (global cache)
                       Upserts all roles and tasks to Cloudflare D1 (SQLite)
                       Logs changelog entries to D1 role_changes table
                       Commits updated data files back to this repo
```

**If the pipeline fails** — a GitHub Issue is opened automatically. The previous night's data stays live. Nothing breaks for users.

**The commit history** of this repo is a permanent, searchable record of every role change Microsoft has made since launch.

---

## Project structure

```
entra-rolelens/
├── .github/
│   ├── workflows/
│   │   └── refresh.yml            # Nightly pipeline — OIDC auth + dual data sources
│   └── ISSUE_TEMPLATE/            # missing_task.md · bug_report.md
├── pipeline/                      # Python scripts — run by GitHub Actions
│   ├── fetch_roles.py             # Graph API (OIDC) + docs scrape — dual source
│   ├── scrape_tasks.py            # Scrapes task → role mappings
│   ├── diff_roles.py              # Detects role changes
│   ├── enrich.py                  # Union permissions + shadow detection → master.json
│   ├── validate.py                # Quality gate
│   ├── coverage_report.py         # Flags new roles lacking task coverage
│   └── push_to_cloudflare.py      # Writes to KV + D1
├── worker/                        # Cloudflare Worker — TypeScript API
│   ├── src/index.ts               # 6 routes: search, diff, role, roles, status, quality
│   └── wrangler.toml
├── frontend/                      # Static UI — deployed to Cloudflare Pages
│   └── index.html                 # Single file · dark theme · no framework
├── data/                          # Auto-committed nightly by the pipeline
│   ├── roles_graph_raw.json       # Live Graph API response — source of truth
│   ├── roles.json                 # Docs-sourced role metadata
│   ├── tasks.json                 # 237 task → role mappings
│   ├── master.json                # Merged dataset pushed to KV
│   ├── changelog.json             # Role changes detected this run
│   ├── coverage.json              # Task-coverage report (new roles needing a task)
│   └── previous_roles.json        # Yesterday's snapshot for diffing
└── assets/
    ├── architecture.svg           # System architecture diagram
    └── project-banner.png         # Project banner
```

---

## Data sources

| Source | URL | Used for |
|--------|-----|----------|
| Microsoft Graph API | `graph.microsoft.com/v1.0/roleManagement/directory/roleDefinitions` | Live role definitions · OIDC authenticated · source of truth |
| MicrosoftDocs/entra-docs | `github.com/MicrosoftDocs/entra-docs` | Role descriptions · metadata |
| Microsoft Learn | `learn.microsoft.com/.../delegate-by-task` | Task → minimum role mappings · 211 tasks |

**Why dual sources?** The Graph API is authoritative for role IDs; the documentation scrape supplies task → role mappings and human-readable metadata. The two sources also disagree on a role's **permissions** during Microsoft rollout windows — the docs lead for brand-new roles (e.g. the agent-identity permissions), the Graph API leads for some mature roles. RoleLens reconciles them with a **union per role**, so the catalog never *under-states* what a role grants — keeping role detail, diff, and least-privilege search consistent with what Microsoft has published (and with "What's new"). This dual sourcing also powers the shadow role detector: roles Microsoft has deployed to the API but not yet documented.

---

## Data quality
- **145+ built-in roles** - covers all named Entra ID built-in roles including preview roles
- **237 task mappings** - sourced from Microsoft's official documentation and community contributions
- **10 unlisted roles** - present in the Graph API but not yet in Microsoft's public documentation
- **0 partially documented roles** - in roles reference but missing from task mappings
- **Nightly diff** - every permission change Microsoft makes is logged to the role_changes D1 table
- **Self-healing pipeline** - validation gate prevents bad data reaching production

## Contributing

The task dataset lives in [`data/tasks.json`](data/tasks.json). If a mapping is wrong, a task is missing, or a role recommendation is outdated:

1. Check the [Microsoft Learn least-privileged-by-task](https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/delegate-by-task) page for the authoritative mapping
2. Open an [issue](https://github.com/arusso-aboutcloud/entra-rolelens/issues) with the task description and the Microsoft Learn source URL
3. Or submit a PR directly to `data/tasks.json` — see [CONTRIBUTING.md](CONTRIBUTING.md)

Every merged contribution is picked up by the nightly pipeline and live within minutes.

---

## License

MIT — see [LICENSE](LICENSE)

---

<div align="center">
  <sub>Built on Microsoft's public data · Not affiliated with or endorsed by Microsoft</sub><br>
  <sub>Made by <a href="https://aboutcloud.io">aboutcloud.io</a> ·
  <a href="https://www.linkedin.com/in/antonio-russo-9295731b/">Antonio Russo</a></sub>
</div>
