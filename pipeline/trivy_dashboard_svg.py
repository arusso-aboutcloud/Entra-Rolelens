"""
trivy_dashboard_svg.py

Reads .trivy/worker.json and .trivy/pipeline.json (Trivy JSON output written
by the workflow dashboard job), plus .trivy/version.txt (the real `trivy
--version` output captured right after those scans), and generates
assets/security-dashboard.svg. Committed by the workflow and embedded in
README.

Visual language matches the repo's other hand-authored diagrams (assets/
architecture.svg, app-architecture.svg, ai-automation-engine.svg): same
#0D1018 canvas + dot-grid texture, same mono/sans font-class convention, and
severity colors reused verbatim from those diagrams' own tiers rather than
invented here -- green from the Worker/D1/KV tier, amber from the pipeline
data tier, crimson from the Cloudflare edge-security tier -- so a reader who
has seen any of those recognizes this as the same family, not a one-off.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKER_JSON   = Path(".trivy/worker.json")
PIPELINE_JSON = Path(".trivy/pipeline.json")
VERSION_PATH  = Path(".trivy/version.txt")
SVG_OUTPUT    = Path("assets/security-dashboard.svg")

BG        = "#0D1018"
BORDER    = "#2A2A3A"
DOT_FILL  = "#444441"
DIM       = "#888780"
FOOTNOTE  = "#5A5850"

# {text, stroke, fill} triples lifted directly from the sibling diagrams'
# own tier colors -- not a separate palette invented for this file.
SAFE = {"text": "#6FE3B4", "stroke": "#1D9E75", "fill": "#03150E"}  # worker/D1/KV tier
WARN = {"text": "#F5C065", "stroke": "#F59E0B", "fill": "#241A05"}  # pipeline/data tier
CRIT = {"text": "#ECA9A9", "stroke": "#D65A5A", "fill": "#1E0C0E"}  # Cloudflare edge-security tier


def count_vulns(json_path: Path) -> tuple[int, int]:
    if not json_path.exists():
        return 0, 0
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return 0, 0
    high = crit = 0
    for result in data.get("Results") or []:
        for v in result.get("Vulnerabilities") or []:
            sev = v.get("Severity", "")
            if sev == "HIGH":
                high += 1
            elif sev == "CRITICAL":
                crit += 1
    return high, crit


def sev_palette(high: int, critical: int) -> dict:
    if critical > 0:
        return CRIT
    if high > 0:
        return WARN
    return SAFE


def read_trivy_version() -> str:
    """The real Trivy CLI version, captured by the workflow (`trivy
    --version` piped to .trivy/version.txt) right after the scan steps that
    produced worker.json/pipeline.json -- so this can never drift from
    whatever release actually ran, unlike a hardcoded string (exactly how
    the dashboard was stuck reading "v0.28.0" for a long time)."""
    if not VERSION_PATH.exists():
        return ""
    try:
        text = VERSION_PATH.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = re.search(r"Version:\s*(\S+)", text)
    return m.group(1) if m else ""


def render(worker_high: int, worker_crit: int,
           pipeline_high: int, pipeline_crit: int,
           timestamp_iso: str, trivy_version: str, pending: bool = False) -> str:

    total_high = worker_high + pipeline_high
    total_crit = worker_crit + pipeline_crit
    total      = total_high + total_crit

    overall  = sev_palette(total_high, total_crit)
    worker   = sev_palette(worker_high, worker_crit)
    pipeline = sev_palette(pipeline_high, pipeline_crit)

    if pending:
        score_display = "—"
        verdict       = "Pending first scan"
        verdict_color = DIM
    elif total == 0:
        score_display = "0"
        verdict       = "No HIGH or CRITICAL findings"
        verdict_color = SAFE["text"]
    else:
        score_display = str(total)
        frag = []
        if total_crit:
            frag.append(f"{total_crit} CRITICAL")
        if total_high:
            frag.append(f"{total_high} HIGH")
        verdict       = " · ".join(frag)
        verdict_color = CRIT["text"] if total_crit > 0 else WARN["text"]

    last_scanned = "—"
    if timestamp_iso:
        try:
            dt = datetime.fromisoformat(timestamp_iso.replace("Z", "+00:00"))
            last_scanned = dt.strftime("%Y-%m-%d %H:%M UTC")
        except (ValueError, AttributeError):
            last_scanned = timestamp_iso[:16]

    version_seg = f"&#160;&#183;&#160;TRIVY v{trivy_version}" if trivy_version else ""

    w_high_d = str(worker_high)
    w_crit_d = str(worker_crit)
    p_high_d = str(pipeline_high)
    p_crit_d = str(pipeline_crit)
    t_crit_d = str(total_crit)
    t_high_d = str(total_high)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 300">
  <defs>
    <style>
      .mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}}
      .sans{{font-family:-apple-system,BlinkMacSystemFont,sans-serif}}
      .bold{{font-weight:700}}
    </style>
    <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="12" cy="12" r="0.9" fill="{DOT_FILL}" opacity="0.4"/>
    </pattern>
    <!-- Standard glow: used on large score -->
    <filter id="glow">
      <feGaussianBlur stdDeviation="2.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Soft ambient glow: used on tile metric numbers -->
    <filter id="glow-soft">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Verdict glow: wider bloom for the status line -->
    <filter id="glow-verdict">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <!-- Security scan beam: sweeps across tile row left→right -->
    <linearGradient id="scan-beam" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0%"   stop-color="{overall['stroke']}" stop-opacity="0"/>
      <stop offset="40%"  stop-color="{overall['stroke']}" stop-opacity="0.1"/>
      <stop offset="50%"  stop-color="#ffffff"          stop-opacity="0.2"/>
      <stop offset="60%"  stop-color="{overall['stroke']}" stop-opacity="0.1"/>
      <stop offset="100%" stop-color="{overall['stroke']}" stop-opacity="0"/>
    </linearGradient>
    <!-- Clip scan beam strictly to tile row -->
    <clipPath id="tiles-clip">
      <rect x="20" y="182" width="680" height="80"/>
    </clipPath>
  </defs>

  <!-- Background + dot-grid texture + border, same canvas as the other diagrams -->
  <rect width="720" height="300" fill="{BG}" rx="12"/>
  <rect width="720" height="300" fill="url(#dots)" rx="12"/>
  <rect x="0.5" y="0.5" width="719" height="299" fill="none" stroke="{BORDER}" stroke-width="1" rx="12"/>

  <!-- Header -->
  <text x="20" y="30" class="mono bold" font-size="11" fill="{DIM}" letter-spacing="1.5">SECURITY SCAN&#160;&#183;&#160;ENTRA ROLELENS{version_seg}</text>
  <circle cx="700" cy="26" r="4" fill="{overall['stroke']}">
    <animate attributeName="opacity" values="1;0.35;1" dur="2.4s" repeatCount="indefinite"/>
  </circle>

  <!-- Total findings (large) -->
  <text x="20" y="80" class="mono" font-size="11" fill="{DIM}" letter-spacing="1.5">DEPENDENCY VULNERABILITIES (HIGH + CRITICAL)</text>
  <text x="20" y="138" class="mono bold" font-size="60" fill="{overall['text']}" filter="url(#glow)">
    {score_display}
    <animate attributeName="opacity" values="0;1" dur="0.7s" fill="freeze"/>
  </text>
  <text x="20" y="160" class="sans" font-size="11" fill="{DIM}">across worker (npm) and pipeline (Python)</text>

  <!-- Security scan beam sweeping across tile row -->
  <rect x="-120" y="182" width="120" height="80" fill="url(#scan-beam)" clip-path="url(#tiles-clip)">
    <animate attributeName="x" values="-120;720;-120" dur="3.6s" repeatCount="indefinite" calcMode="linear"/>
  </rect>

  <!-- Tile 1: Worker -->
  <g transform="translate(20,182)">
    <rect width="220" height="80" fill="{worker['fill']}" stroke="{worker['stroke']}" stroke-width="0.8" rx="8"/>
    <text x="12" y="22" class="mono bold" font-size="10" fill="{DIM}" letter-spacing="1">WORKER &#183; NPM</text>
    <text x="12" y="46" class="mono" font-size="10" fill="{DIM}">HIGH</text>
    <text x="12" y="66" class="mono bold" font-size="26" fill="{worker['text']}" filter="url(#glow-soft)">{w_high_d}</text>
    <text x="110" y="46" class="mono" font-size="10" fill="{DIM}">CRITICAL</text>
    <text x="110" y="66" class="mono bold" font-size="26" fill="{worker['text']}" filter="url(#glow-soft)">{w_crit_d}</text>
    <circle cx="204" cy="20" r="3" fill="{worker['stroke']}">
      <animate attributeName="opacity" values="1;0.3;1" dur="2.4s" repeatCount="indefinite"/>
    </circle>
  </g>

  <!-- Tile 2: Pipeline -->
  <g transform="translate(252,182)">
    <rect width="220" height="80" fill="{pipeline['fill']}" stroke="{pipeline['stroke']}" stroke-width="0.8" rx="8"/>
    <text x="12" y="22" class="mono bold" font-size="10" fill="{DIM}" letter-spacing="1">PIPELINE &#183; PYTHON</text>
    <text x="12" y="46" class="mono" font-size="10" fill="{DIM}">HIGH</text>
    <text x="12" y="66" class="mono bold" font-size="26" fill="{pipeline['text']}" filter="url(#glow-soft)">{p_high_d}</text>
    <text x="110" y="46" class="mono" font-size="10" fill="{DIM}">CRITICAL</text>
    <text x="110" y="66" class="mono bold" font-size="26" fill="{pipeline['text']}" filter="url(#glow-soft)">{p_crit_d}</text>
    <circle cx="204" cy="20" r="3" fill="{pipeline['stroke']}">
      <animate attributeName="opacity" values="1;0.3;1" dur="2.4s" begin="0.8s" repeatCount="indefinite"/>
    </circle>
  </g>

  <!-- Tile 3: Totals -->
  <g transform="translate(484,182)">
    <rect width="216" height="80" fill="{overall['fill']}" stroke="{overall['stroke']}" stroke-width="0.8" rx="8"/>
    <text x="12" y="22" class="mono bold" font-size="10" fill="{DIM}" letter-spacing="1">ALL COMPONENTS</text>
    <text x="12" y="46" class="mono" font-size="10" fill="{DIM}">CRITICAL</text>
    <text x="12" y="66" class="mono bold" font-size="26" fill="{overall['text']}" filter="url(#glow-soft)">{t_crit_d}</text>
    <text x="110" y="46" class="mono" font-size="10" fill="{DIM}">HIGH</text>
    <text x="110" y="66" class="mono bold" font-size="26" fill="{overall['text']}" filter="url(#glow-soft)">{t_high_d}</text>
    <circle cx="200" cy="20" r="3" fill="{overall['stroke']}">
      <animate attributeName="opacity" values="1;0.3;1" dur="2.4s" begin="1.6s" repeatCount="indefinite"/>
    </circle>
  </g>

  <!-- Verdict + timestamp -->
  <text x="20" y="280" class="mono bold" font-size="11" fill="{verdict_color}" filter="url(#glow-verdict)">&#9658; {verdict}</text>
  <text x="700" y="280" class="sans" font-size="9" fill="{FOOTNOTE}" text-anchor="end">scanned {last_scanned}</text>
</svg>"""


def main() -> int:
    pending = not WORKER_JSON.exists() and not PIPELINE_JSON.exists()
    if pending:
        print("trivy_dashboard_svg: scan JSONs not found — generating pending-state SVG", file=sys.stderr)

    worker_high, worker_crit     = count_vulns(WORKER_JSON)
    pipeline_high, pipeline_crit = count_vulns(PIPELINE_JSON)
    timestamp_iso = datetime.now(timezone.utc).isoformat()
    trivy_version = read_trivy_version()

    svg = render(worker_high, worker_crit, pipeline_high, pipeline_crit,
                 timestamp_iso, trivy_version, pending)
    SVG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUTPUT.write_text(svg, encoding="utf-8")
    print(f"trivy_dashboard_svg: wrote {SVG_OUTPUT} ({len(svg):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
