# Security Policy

## Supported Versions

Entra RoleLens is a continuously deployed service. Users always interact
with the latest version served from Cloudflare. Security fixes are applied
to `master` and promoted to production within one business day.

| Version | Status |
|---------|--------|
| Latest deployed (`master`) | Supported |
| Any pinned or self-hosted fork | Not supported |

---

## Reporting a Vulnerability

**Please do not open a public GitHub Issue for security vulnerabilities.**

Report privately via
[GitHub Security Advisories](https://github.com/arusso-aboutcloud/Entra-Rolelens/security/advisories/new).

Include as much as possible:

- A clear description of the vulnerability and its impact
- Steps to reproduce or a proof-of-concept
- Browser and OS (for frontend issues) or curl/HTTP trace (for API issues)

### Response timeline

| Milestone | Target |
|-----------|--------|
| Acknowledgement | Within 48 hours |
| Initial triage | Within 5 business days |
| Fix or mitigation | Dependent on severity (see below) |
| Public disclosure | Coordinated with the reporter |

| Severity | Fix target |
|----------|------------|
| Critical (data integrity, worker exploit, auth bypass) | Within 24–48 hours |
| High (XSS, injection, information disclosure) | Within 7 days |
| Medium (CORS misconfiguration, API enumeration) | Within 30 days |
| Low (hardening improvements) | Next regular release |

---

## Security Architecture

### What Entra RoleLens does

- Serves a **public, unauthenticated** search API (`/api/search`, `/api/status`)
  — no user credentials are collected or stored
- Data consists entirely of **publicly available Microsoft role and task
  mappings** scraped from Microsoft Learn — no PII is stored or returned
- The Cloudflare Worker queries **Cloudflare D1** (SQLite) and **KV** for
  pre-computed role/task data loaded by the nightly pipeline
- The nightly GitHub Actions pipeline authenticates to Microsoft Graph using
  **OIDC (passwordless)** — no stored secrets in the repo or environment

### What Entra RoleLens does not do

- Store any user data, sign-in data, or credentials
- Accept write input from external users
- Hold secrets in source code (API keys, tokens, database credentials)

### Trust boundaries

| Boundary | Notes |
|----------|-------|
| Internet → Cloudflare Worker | Cloudflare WAF; unauthenticated public API |
| Worker → D1 / KV | Cloudflare-internal binding; no network exposure |
| GitHub Actions → Microsoft Graph | OIDC federated identity; read-only delegated scopes |
| GitHub Actions → Cloudflare | API token scoped to KV/D1 write + Worker deploy |

---

## In-Scope Vulnerabilities

- **Injection in the search API** — SQL injection or KV key manipulation via
  the `q` query parameter reaching D1 or KV
- **XSS** — script injection via search results rendered in the frontend
- **Worker exploit** — remote code execution or data exfiltration from the
  Cloudflare Worker process
- **Data integrity** — manipulation of role/task data in D1 or KV outside
  the nightly pipeline
- **CORS misconfiguration** — cross-origin access to the Worker API from
  unintended origins
- **Sensitive data in source** — credentials, API tokens, or operator-specific
  values committed to the public repository
- **Supply chain** — malicious code introduced via an npm or Python dependency

---

## Out-of-Scope

- Vulnerabilities in **Microsoft Graph API or Entra ID** — report to
  [Microsoft MSRC](https://msrc.microsoft.com/report)
- Vulnerabilities in **Cloudflare's platform** — report to
  [Cloudflare](https://www.cloudflare.com/disclosure/)
- Rate limiting of the public search API — this is governed by Cloudflare
  WAF rate limiting rules
- The fact that role/task data is public — all content is sourced from
  publicly available Microsoft documentation
- Scanner findings with no demonstrated impact (automated reports without a PoC)
- Social engineering or physical attacks

---

## Dependency Security

- **Dependabot** is enabled for npm (worker) and Python (pipeline) dependencies
- **Trivy** runs a filesystem vulnerability scan on every push and pull request
  (`trivy.yml`), with results uploaded to GitHub Security → Code scanning alerts
- The Sentrux quality gate (`sentrux.yml`) runs on every pull request

---

## Security Contact

Report vulnerabilities via
[GitHub Security Advisories](https://github.com/arusso-aboutcloud/Entra-Rolelens/security/advisories/new)
or contact [security@aboutcloud.io](mailto:security@aboutcloud.io).
