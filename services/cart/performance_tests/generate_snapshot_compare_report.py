# Copyright 2026 masa@kugel
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Snapshot A/B delta report (issue #156).

Reads a Locust ``*_compare_*_stats.csv`` produced by
``locustfile_snapshot_compare.py`` (rows tagged ``[legacy]`` / ``[stateless]``),
pairs the two paths per operation, and prints a legacy-vs-stateless delta table
(mean / p95 latency and average response size). Optionally writes an HTML copy.

Usage:
    pipenv run python generate_snapshot_compare_report.py <stats.csv> [out.html]
"""

import csv
import sys
from collections import defaultdict

LEGACY = "[legacy] "
STATELESS = "[stateless] "


def _f(row, key, default=0.0):
    try:
        return float(row.get(key, "") or default)
    except (ValueError, TypeError):
        return default


def load(path):
    """Return {operation: {'legacy': row, 'stateless': row}} keyed by the un-tagged op name."""
    paired = defaultdict(dict)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            name = row.get("Name", "")
            if name.startswith(LEGACY):
                paired[name[len(LEGACY):]]["legacy"] = row
            elif name.startswith(STATELESS):
                paired[name[len(STATELESS):]]["stateless"] = row
    return paired


def _delta_pct(legacy, stateless):
    if legacy == 0:
        return 0.0
    return (stateless - legacy) / legacy * 100.0


def build_rows(paired):
    out = []
    for op in sorted(paired):
        pair = paired[op]
        lg, st = pair.get("legacy"), pair.get("stateless")
        if not lg or not st:
            continue
        lg_mean, st_mean = _f(lg, "Average Response Time"), _f(st, "Average Response Time")
        lg_p95, st_p95 = _f(lg, "95%"), _f(st, "95%")
        lg_sz, st_sz = _f(lg, "Average Content Size"), _f(st, "Average Content Size")
        out.append({
            "op": op,
            "reqs": f"{int(_f(lg, 'Request Count'))}/{int(_f(st, 'Request Count'))}",
            "lg_mean": lg_mean, "st_mean": st_mean,
            "d_mean": st_mean - lg_mean, "d_mean_pct": _delta_pct(lg_mean, st_mean),
            "lg_p95": lg_p95, "st_p95": st_p95,
            "lg_sz": lg_sz, "st_sz": st_sz,
        })
    return out


def print_console(rows):
    print()
    print("Snapshot A/B comparison — legacy (no snapshot) vs stateless (carried)")
    print("Latency in ms (mean / p95); sz = avg RESPONSE bytes. Δ = stateless − legacy.")
    print("=" * 104)
    hdr = f"{'Operation':<26} {'reqs(L/S)':>10} {'mean L':>8} {'mean S':>8} {'Δmean':>8} {'Δ%':>7} {'p95 L':>7} {'p95 S':>7} {'sz L':>7} {'sz S':>7}"
    print(hdr)
    print("-" * 104)
    for r in rows:
        op = r["op"].replace("POST /api/v1/carts", "…").replace("/[cart_id]", "")
        print(
            f"{op:<26} {r['reqs']:>10} {r['lg_mean']:>8.0f} {r['st_mean']:>8.0f} "
            f"{r['d_mean']:>+8.0f} {r['d_mean_pct']:>+6.1f}% {r['lg_p95']:>7.0f} {r['st_p95']:>7.0f} "
            f"{r['lg_sz']:>7.0f} {r['st_sz']:>7.0f}"
        )
    print("=" * 104)
    print("Δmean > 0 → stateless slower; < 0 → stateless faster.")
    print("NOTE: in DUAL mode the legacy RESPONSE also carries a snapshot, so sz L≈sz S. The stateless")
    print("      path's extra cost is the REQUEST upload (growing snapshot), which Locust's response-size")
    print("      stat does NOT capture but which IS included in the latency above.")
    print()


def write_html(rows, path):
    cells = []
    for r in rows:
        cls = "slower" if r["d_mean"] > 0 else "faster"
        cells.append(
            f"<tr><td>{r['op']}</td><td>{r['reqs']}</td>"
            f"<td>{r['lg_mean']:.0f}</td><td>{r['st_mean']:.0f}</td>"
            f"<td class='{cls}'>{r['d_mean']:+.0f} ({r['d_mean_pct']:+.1f}%)</td>"
            f"<td>{r['lg_p95']:.0f}</td><td>{r['st_p95']:.0f}</td>"
            f"<td>{r['lg_sz']:.0f}</td><td>{r['st_sz']:.0f}</td></tr>"
        )
    html = f"""<!doctype html><meta charset="utf-8">
<title>Snapshot A/B comparison</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:2rem}}
 table{{border-collapse:collapse}} td,th{{border:1px solid #ccc;padding:.35rem .6rem;text-align:right}}
 td:first-child,th:first-child{{text-align:left}} .slower{{color:#b00}} .faster{{color:#080}}
 caption{{text-align:left;margin-bottom:.6rem;font-weight:bold}}
</style>
<table><caption>legacy (no snapshot) vs stateless (carried) — latency ms (mean/p95), size = avg response bytes</caption>
<tr><th>Operation</th><th>reqs L/S</th><th>mean L</th><th>mean S</th><th>Δmean</th>
<th>p95 L</th><th>p95 S</th><th>sz L</th><th>sz S</th></tr>
{''.join(cells)}
</table>"""
    with open(path, "w") as f:
        f.write(html)
    print(f"HTML report written: {path}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    rows = build_rows(load(sys.argv[1]))
    if not rows:
        print("No paired [legacy]/[stateless] rows found. Was this a --compare run?")
        sys.exit(1)
    print_console(rows)
    if len(sys.argv) >= 3:
        write_html(rows, sys.argv[2])


if __name__ == "__main__":
    main()
