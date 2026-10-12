"""Self-contained HTML: no external assets, no raw data, escaped metadata."""

from html import escape
import json

from .core import Report


CSS = """
:root{color-scheme:dark;--bg:#101515;--panel:#182020;--line:#2a3534;--muted:#a0afab;--text:#edf4f0;--mint:#b8f3d6;--amber:#f2c376;--red:#ffa3a0}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
button{font:inherit;cursor:pointer}button:focus-visible,a:focus-visible{outline:2px solid var(--mint);outline-offset:4px}
.shell{max-width:1320px;margin:auto;padding:0 48px}.top{display:flex;align-items:center;justify-content:space-between;padding:26px 0;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:12px;font-size:18px;font-weight:650;letter-spacing:-.5px}.mark{display:grid;place-items:center;width:34px;height:34px;border-radius:9px;background:var(--mint);color:var(--bg);font-weight:900;font-size:20px}
.top-right{display:flex;gap:18px;align-items:center}.label,.eyebrow{font:11px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;letter-spacing:1.5px;text-transform:uppercase}.label{color:var(--muted)}.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--mint);margin-right:8px}
.print{padding:7px 14px;border:1px solid var(--line);border-radius:7px;background:transparent;color:var(--text);font-size:12px}
.hero{padding:48px 0 30px;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:end}.eyebrow{color:var(--mint);margin:0 0 14px}h1{font-size:clamp(30px,4vw,49px);line-height:1.12;letter-spacing:-2px;font-weight:600;margin:0 0 17px}h1 span{color:var(--mint)}.sub{max-width:650px;color:var(--muted);margin:0;font-size:15px}.run-tag{padding:10px 14px;border:1px solid var(--line);border-radius:8px;color:var(--muted);font:12px ui-monospace,monospace;white-space:nowrap}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 30px}.metric{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:21px 23px}.metric .label{letter-spacing:1px}.value{font-size:35px;line-height:1.3;letter-spacing:-1px;font-weight:550;margin-top:9px}.metric-note{font-size:12px;color:var(--muted);margin-top:5px}.mint{color:var(--mint)}.amber{color:var(--amber)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 295px;gap:22px}.section-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:12px}h2{margin:0;font-size:18px;font-weight:600;letter-spacing:-.3px}.filters{display:flex;padding:3px;gap:3px;border:1px solid var(--line);border-radius:8px}.filters button{border:0;background:transparent;border-radius:5px;color:var(--muted);padding:4px 12px;font-size:12px}.filters button[aria-pressed=true]{background:#34433d;color:var(--text)}
.check{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 23px;margin-bottom:12px}.check-top{display:flex;align-items:center;justify-content:space-between;gap:12px}.check h3{font-size:15px;font-weight:600;margin:0;letter-spacing:-.15px}.pill{display:inline-block;font:10px/1.6 ui-monospace,monospace;text-transform:uppercase;letter-spacing:.6px;padding:3px 9px;border-radius:5px;white-space:nowrap}.pill.flag{background:#3f3023;color:var(--amber)}.pill.pass{background:#233c30;color:var(--mint)}.pill.skipped{background:#2b3332;color:var(--muted)}.pill.inconclusive{background:#3d303c;color:#e4b4df}.summary{color:var(--muted);font-size:13px;margin:9px 0 13px}.evidence{display:flex;flex-wrap:wrap;gap:7px}.evidence span{border:1px solid var(--line);background:#121a18;padding:4px 8px;border-radius:5px;font:11px/1.6 ui-monospace,monospace;overflow-wrap:anywhere}.evidence b{color:var(--mint);font-weight:500}.fix{border-top:1px solid var(--line);margin:15px 0 0;padding-top:12px;color:var(--muted);font-size:12px}.fix strong{color:var(--text);font-weight:550}.incomplete{color:#e4b4df;font-size:12px;margin-bottom:0}
.aside{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:22px;height:fit-content;margin-top:48px}.aside h2{font-size:15px;margin-bottom:19px}.context{margin-bottom:19px}.context .label{font-size:10px;letter-spacing:1px}.context p{margin:4px 0;font:12px/1.7 ui-monospace,monospace;overflow-wrap:anywhere}.rule{border-top:1px solid var(--line);padding-top:18px}.privacy{display:flex;gap:10px;align-items:flex-start;font-size:12px;color:var(--muted)}.privacy strong{display:block;color:var(--mint);font-weight:550;margin-bottom:4px}.privacy svg{flex-shrink:0;color:var(--mint);margin-top:2px}
.scope{border:1px solid var(--line);border-radius:12px;padding:19px 23px;margin:17px 0 32px;display:flex;gap:14px;color:var(--muted);font-size:12px}.scope b{color:var(--text);font-weight:550}.scope p{margin:0}footer{border-top:1px solid var(--line);padding:21px 0 28px;display:flex;justify-content:space-between;gap:15px;color:var(--muted);font:10px/1.6 ui-monospace,monospace;letter-spacing:.6px}a{color:var(--mint)}[hidden]{display:none!important}.empty{color:var(--muted);padding:30px;text-align:center;border:1px dashed var(--line);border-radius:12px}
@media(max-width:900px){.shell{padding:0 24px}.layout{grid-template-columns:1fr}.aside{margin-top:0}.hero{grid-template-columns:1fr}.run-tag{width:fit-content}.metrics{grid-template-columns:repeat(2,1fr)}.aside-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:0 20px}}
@media(max-width:520px){.shell{padding:0 16px}.top-right .label{display:none}.hero{padding:32px 0 24px}h1{letter-spacing:-1px}.metric{padding:16px}.value{font-size:29px}.check{padding:17px}.check-top{align-items:flex-start}.section-top{align-items:flex-start;flex-direction:column}.scope{padding:16px}.aside-grid{grid-template-columns:1fr}footer{flex-direction:column}}
@media print{:root{color-scheme:light;--bg:white;--panel:white;--line:#ccc;--muted:#555;--text:#111;--mint:#165d3a;--amber:#7a4300}body{font-size:12px}.shell{padding:0}.print,.filters{display:none}.hero{padding-top:20px}h1{font-size:30px}.metrics{gap:8px}.layout{grid-template-columns:1fr}.aside{margin-top:0}.check{break-inside:avoid}.check[hidden]{display:block!important}.pill,.evidence span{background:white!important;color:#111!important}.scope{break-inside:avoid}}
"""

SCRIPT = """
const filters = document.querySelectorAll('[data-filter]');
filters.forEach(button => button.addEventListener('click', () => {
  filters.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  let visible = 0;
  document.querySelectorAll('.check').forEach(card => {
    const show = button.dataset.filter === 'all' || ['flag', 'inconclusive'].includes(card.dataset.status);
    card.hidden = !show;
    if (show) visible++;
  });
  document.querySelector('.empty').hidden = visible !== 0;
}));
document.querySelector('.print').addEventListener('click', () => window.print());
"""


def _evidence_items(evidence: dict) -> str:
    pieces = []
    for name, value in evidence.items():
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                text = "; ".join(f"train #{item['train_record']} / test #{item['test_record']}" for item in value)
            else:
                text = ", ".join(str(item) for item in value) or "none"
        elif isinstance(value, bool):
            text = "yes" if value else "no"
        else:
            text = str(value)
        pieces.append(f"<span>{escape(name.replace('_', ' '))}: <b>{escape(text)}</b></span>")
    return "".join(pieces)


def render_html(report: Report) -> str:
    flagged = sum(check.status == "flag" for check in report.checks)
    inconclusive = sum(check.status == "inconclusive" for check in report.checks)
    requested = sum(check.status != "skipped" for check in report.checks)
    complete = sum(check.status != "skipped" and check.complete for check in report.checks)
    headings = {
        "review_required": "Your split deserves<br /><span>a closer look.</span>",
        "inconclusive": "Some checks need<br /><span>more information.</span>",
        "no_findings": "No findings in<br /><span>requested checks.</span>",
    }
    cards = []
    for check in report.checks:
        status = {"flag": "Review", "pass": "Passed", "skipped": "Not requested", "inconclusive": "Incomplete"}[check.status]
        fix = f'<p class="fix"><strong>Next step</strong> &nbsp;{escape(check.recommendation)}</p>' if check.recommendation else ""
        incomplete = '<p class="incomplete">Some records could not be assessed. See the evidence above.</p>' if check.status == "flag" and not check.complete else ""
        cards.append(f"""<article class="check" data-status="{check.status}">
<div class="check-top"><h3>{escape(check.title)}</h3><span class="pill {check.status}">{status}</span></div>
<p class="summary">{escape(check.summary)}</p><div class="evidence">{_evidence_items(check.evidence)}</div>{incomplete}{fix}</article>""")
    config = report.configuration
    def context(label: str, value: str) -> str:
        return f'<div class="context"><div class="label">{escape(label)}</div><p>{escape(value)}</p></div>'
    contexts = "".join([
        context("Training file", report.inputs["train"]["name"]),
        context("Holdout file", report.inputs["test"]["name"]),
        context("Target / entity / time", " / ".join(config[name] or "not set" for name in ("target", "group", "time"))),
        context("Compared features", ", ".join(config["features"])),
        context("Ignored columns", ", ".join(config["ignored"]) or "none"),
        context("Comparison", config["comparison"]),
    ])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;">
<title>Spliv — Split report</title><style>{CSS}</style></head>
<body><div class="shell">
<header class="top"><div class="brand"><span class="mark" aria-hidden="true">S</span>spliv<span class="label">/ 0.1</span></div>
<div class="top-right"><span class="label"><span class="dot"></span>Offline report</span><button class="print" type="button">Print / Save PDF</button></div></header>
<main><section class="hero"><div><p class="eyebrow">Train / test integrity</p><h1>{headings[report.verdict]}</h1>
<p class="sub">Evidence before confidence. Review split boundaries and exact sample matches before trusting your model metrics.</p></div>
<div class="run-tag">CSV IN &nbsp;→&nbsp; EVIDENCE OUT</div></section>
<section class="metrics" aria-label="Audit summary">
<div class="metric"><div class="label">Train records</div><div class="value">{report.inputs['train']['rows']:,}</div><div class="metric-note">All records scanned</div></div>
<div class="metric"><div class="label">Test records</div><div class="value">{report.inputs['test']['rows']:,}</div><div class="metric-note">All records scanned</div></div>
<div class="metric"><div class="label">Checks to review</div><div class="value amber">{flagged + inconclusive:02}</div><div class="metric-note">{flagged} flagged · {inconclusive} inconclusive</div></div>
<div class="metric"><div class="label">Completed checks</div><div class="value mint">{complete}<span style="color:var(--muted);font-size:22px"> / {requested}</span></div><div class="metric-note">Of the checks you requested</div></div>
</section>
<div class="layout"><section aria-label="Check results"><div class="section-top"><h2>Split diagnostics</h2>
<div class="filters" aria-label="Filter diagnostics"><button type="button" data-filter="all" aria-pressed="true">All checks</button><button type="button" data-filter="review" aria-pressed="false">Needs review</button></div></div>
{''.join(cards)}<p class="empty" hidden>No requested checks need review.</p></section>
<aside class="aside"><h2>Run context</h2><div class="aside-grid">{contexts}</div><div class="rule privacy">
<svg width="18" height="21" viewBox="0 0 18 21" fill="none" aria-hidden="true"><path d="M9 1L17 4V10C17 15 13 18 9 20C5 18 1 15 1 10V4L9 1Z" stroke="currentColor"/><path d="M5 10L8 13L13 7" stroke="currentColor"/></svg>
<div><strong>Your data stays local.</strong>No uploads, telemetry, external assets, or raw cell values in this report. Filenames and column labels are included.</div></div></aside></div>
<div class="scope"><span aria-hidden="true">↳</span><p><b>A check, not a guarantee.</b> These diagnostics identify exact matches and configured split conditions. They do not detect preprocessing fitted on test data, near-duplicates, transformed target proxies, or features unavailable at prediction time. Review findings in the context of your evaluation goal.</p></div>
</main><footer><span>SPLIV / EVIDENCE-FIRST SPLIT CHECKS</span><span>DATA RECORD NUMBERS START AT 1 · NO SAMPLING</span></footer>
</div><script>{SCRIPT}</script></body></html>"""


def render_json(report: Report) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
