#!/usr/bin/env node
// Auto-patch the worker's vulnerable transitive dependencies.
//
// Dependabot cannot bump deps that a parent pins (e.g. undici/sharp pinned by
// wrangler), so security advisories on them linger until wrangler updates. This
// bumps each vulnerable LEAF package to the newest version WITHIN ITS CURRENT
// MAJOR via an npm `overrides` entry, then lets `npm audit` confirm the result.
//
// - Only "leaf" packages (those with their own advisory) are touched; parent
//   packages flagged merely for containing a vulnerable child are fixed
//   transitively once the leaf is overridden.
// - Only IN-MAJOR bumps are applied automatically (semver-safe). Anything still
//   vulnerable after that — i.e. needs a MAJOR bump or has no fix — is returned
//   in `escalate` for human review, never auto-applied.
// Run from the worker/ directory.
import { execSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';

const sh = (c) => execSync(c, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] });
const auditJson = () => { try { return JSON.parse(sh('npm audit --json')); } catch (e) { try { return JSON.parse(e.stdout || '{}'); } catch { return {}; } } };
const lockVersion = (name) => {
  const lock = JSON.parse(readFileSync('package-lock.json', 'utf8'));
  return Object.entries(lock.packages || {})
    .filter(([k]) => k.endsWith('node_modules/' + name)).map(([, v]) => v.version)
    .filter(Boolean).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).pop();
};
const latestInMajor = (name, major) => {
  const all = JSON.parse(sh(`npm view ${name} versions --json`));
  return (Array.isArray(all) ? all : [all])
    .filter((v) => /^\d+\.\d+\.\d+$/.test(v) && v.split('.')[0] === String(major))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true })).pop();
};

const pkg = JSON.parse(readFileSync('package.json', 'utf8'));
pkg.overrides = pkg.overrides || {};
const before = JSON.stringify(pkg.overrides);
const applied = [];

// Pass 1 — override each vulnerable LEAF to the latest in-major version.
for (const [name, v] of Object.entries(auditJson().vulnerabilities || {})) {
  if (v.severity === 'info') continue;
  const isLeaf = (v.via || []).some((x) => typeof x === 'object'); // has its own advisory
  if (!isLeaf) continue; // parent — resolved transitively when the leaf is fixed
  const installed = lockVersion(name);
  if (!installed) continue;
  let cand = null;
  try { cand = latestInMajor(name, installed.split('.')[0]); } catch {}
  if (cand && cand.localeCompare(installed, undefined, { numeric: true }) > 0) {
    pkg.overrides[name] = cand;
    applied.push(`${name}: ${installed} -> ${cand} (${v.severity})`);
  }
}

let changed = JSON.stringify(pkg.overrides) !== before;
if (changed) {
  writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
  execSync('npm install --package-lock-only --ignore-scripts', { stdio: 'inherit' });
}

// Escalate = whatever remains vulnerable AFTER the in-major overrides (leaves only).
const escalate = [];
for (const [name, v] of Object.entries(auditJson().vulnerabilities || {})) {
  if (v.severity === 'info') continue;
  if (!(v.via || []).some((x) => typeof x === 'object')) continue;
  escalate.push(`${name} (${v.severity}): no in-major fix — needs a major bump / manual review`);
}

writeFileSync('../audit-result.json', JSON.stringify({ changed, applied, escalate }, null, 2));
console.log('APPLIED:', applied.length ? '' : '(none)'); applied.forEach((a) => console.log('  ' + a));
console.log('ESCALATE:', escalate.length ? '' : '(none)'); escalate.forEach((e) => console.log('  ' + e));
console.log('CHANGED=' + changed);
