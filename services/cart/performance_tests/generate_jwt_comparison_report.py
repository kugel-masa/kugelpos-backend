"""
Generate JWT vs API Key authentication performance comparison report.

Usage:
    python generate_jwt_comparison_report.py <output.html> <apikey_stats.csv> <jwt_stats.csv>
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import json


def generate_comparison_report(output_html: str, apikey_csv: str, jwt_csv: str):
    """Generate HTML comparison report from API key and JWT test results."""

    apikey_df = pd.read_csv(apikey_csv)
    jwt_df = pd.read_csv(jwt_csv)

    endpoints = {
        'Create Cart': 'POST /api/v1/carts (Create Cart)',
        'Add Item': 'POST /api/v1/carts/[cart_id]/lineItems (Add Item)',
        'Cancel Cart': 'POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)',
        'Aggregated': 'Aggregated'
    }

    # Build comparison data
    comparison = {}
    for name, full_name in endpoints.items():
        apikey_row = apikey_df[apikey_df['Name'] == full_name]
        jwt_row = jwt_df[jwt_df['Name'] == full_name]

        if apikey_row.empty or jwt_row.empty:
            continue

        ak = apikey_row.iloc[0]
        jw = jwt_row.iloc[0]

        ak_avg = float(ak['Average Response Time'])
        jw_avg = float(jw['Average Response Time'])
        improvement = ((ak_avg - jw_avg) / ak_avg * 100) if ak_avg > 0 else 0

        comparison[name] = {
            'apikey_avg': ak_avg,
            'jwt_avg': jw_avg,
            'improvement_pct': improvement,
            'apikey_median': float(ak['Median Response Time']),
            'jwt_median': float(jw['Median Response Time']),
            'apikey_p95': float(ak['95%']),
            'jwt_p95': float(jw['95%']),
            'apikey_p99': float(ak['99%']),
            'jwt_p99': float(jw['99%']),
            'apikey_rps': float(ak['Requests/s']),
            'jwt_rps': float(jw['Requests/s']),
            'apikey_requests': int(ak['Request Count']),
            'jwt_requests': int(jw['Request Count']),
            'apikey_failures': int(ak['Failure Count']),
            'jwt_failures': int(jw['Failure Count']),
            'apikey_min': float(ak['Min Response Time']),
            'jwt_min': float(jw['Min Response Time']),
            'apikey_max': float(ak['Max Response Time']),
            'jwt_max': float(jw['Max Response Time']),
        }

    # Summary cards
    agg = comparison.get('Aggregated', {})
    agg_improvement = agg.get('improvement_pct', 0)
    rps_improvement = ((agg.get('jwt_rps', 0) - agg.get('apikey_rps', 0)) / agg.get('apikey_rps', 1) * 100) if agg.get('apikey_rps', 0) > 0 else 0

    # Table rows
    table_rows = []
    for name in ['Create Cart', 'Add Item', 'Cancel Cart', 'Aggregated']:
        d = comparison.get(name)
        if not d:
            continue
        imp_color = '#4CAF50' if d['improvement_pct'] > 0 else '#f44336'
        imp_sign = '+' if d['improvement_pct'] > 0 else ''
        table_rows.append(f"""
            <tr {'style="font-weight:bold;background:#f0f0f0"' if name == 'Aggregated' else ''}>
                <td>{name}</td>
                <td>{d['apikey_avg']:.0f}</td>
                <td>{d['jwt_avg']:.0f}</td>
                <td style="color:{imp_color};font-weight:bold">{imp_sign}{d['improvement_pct']:.1f}%</td>
                <td>{d['apikey_median']:.0f}</td>
                <td>{d['jwt_median']:.0f}</td>
                <td>{d['apikey_p95']:.0f}</td>
                <td>{d['jwt_p95']:.0f}</td>
                <td>{d['apikey_p99']:.0f}</td>
                <td>{d['jwt_p99']:.0f}</td>
                <td>{d['apikey_rps']:.2f}</td>
                <td>{d['jwt_rps']:.2f}</td>
            </tr>
        """)

    comparison_json = json.dumps(comparison)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>JWT vs API Key Performance Comparison</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 40px; border-bottom: 2px solid #ddd; padding-bottom: 8px; }}
        .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px; margin: 20px 0; }}
        .card {{ padding: 20px; border-radius: 8px; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card.blue {{ background: linear-gradient(135deg, #667eea, #764ba2); }}
        .card.green {{ background: linear-gradient(135deg, #4CAF50, #45a049); }}
        .card.orange {{ background: linear-gradient(135deg, #FF9800, #F57C00); }}
        .card-label {{ font-size: 12px; opacity: 0.9; margin-bottom: 5px; }}
        .card-value {{ font-size: 32px; font-weight: bold; }}
        .card-sub {{ font-size: 13px; opacity: 0.8; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; }}
        th, td {{ padding: 10px 8px; text-align: right; border-bottom: 1px solid #ddd; }}
        th {{ background: #2196F3; color: white; }}
        td:first-child, th:first-child {{ text-align: left; }}
        tr:hover {{ background: #f5f5f5; }}
        .chart-box {{ margin: 30px 0; border: 1px solid #ddd; border-radius: 8px; padding: 20px; background: #fafafa; }}
        .info {{ background: #e3f2fd; border-left: 4px solid #2196F3; padding: 15px; margin: 20px 0; border-radius: 4px; }}
        .timestamp {{ color: #666; font-size: 14px; }}
    </style>
</head>
<body>
<div class="container">
    <h1>JWT vs API Key Authentication - Performance Comparison</h1>
    <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="info">
        <strong>What this measures:</strong>
        <ul>
            <li><b>API Key</b>: Each cart request sends X-API-KEY header + terminal_id query param. Cart service calls terminal service via HTTP to verify.</li>
            <li><b>JWT</b>: Each cart request sends Authorization: Bearer header. Cart service verifies JWT locally (no inter-service HTTP call).</li>
        </ul>
    </div>

    <div class="summary-grid">
        <div class="card {'green' if agg_improvement > 0 else 'orange'}">
            <div class="card-label">Average Response Time Improvement</div>
            <div class="card-value">{'+' if agg_improvement > 0 else ''}{agg_improvement:.1f}%</div>
            <div class="card-sub">API Key: {agg.get('apikey_avg', 0):.0f}ms → JWT: {agg.get('jwt_avg', 0):.0f}ms</div>
        </div>
        <div class="card {'green' if rps_improvement > 0 else 'orange'}">
            <div class="card-label">Throughput Improvement</div>
            <div class="card-value">{'+' if rps_improvement > 0 else ''}{rps_improvement:.1f}%</div>
            <div class="card-sub">API Key: {agg.get('apikey_rps', 0):.1f} → JWT: {agg.get('jwt_rps', 0):.1f} req/s</div>
        </div>
        <div class="card blue">
            <div class="card-label">Total Requests</div>
            <div class="card-value">{agg.get('jwt_requests', 0):,}</div>
            <div class="card-sub">API Key: {agg.get('apikey_requests', 0):,} / JWT: {agg.get('jwt_requests', 0):,}</div>
        </div>
        <div class="card blue">
            <div class="card-label">Failure Count</div>
            <div class="card-value">{agg.get('apikey_failures', 0) + agg.get('jwt_failures', 0)}</div>
            <div class="card-sub">API Key: {agg.get('apikey_failures', 0)} / JWT: {agg.get('jwt_failures', 0)}</div>
        </div>
    </div>

    <h2>Response Time Comparison (ms)</h2>
    <table>
        <thead>
            <tr>
                <th>Endpoint</th>
                <th>Avg (API Key)</th>
                <th>Avg (JWT)</th>
                <th>Improvement</th>
                <th>Med (API Key)</th>
                <th>Med (JWT)</th>
                <th>P95 (API Key)</th>
                <th>P95 (JWT)</th>
                <th>P99 (API Key)</th>
                <th>P99 (JWT)</th>
                <th>RPS (API Key)</th>
                <th>RPS (JWT)</th>
            </tr>
        </thead>
        <tbody>
            {''.join(table_rows)}
        </tbody>
    </table>

    <h2>Average Response Time Comparison</h2>
    <div class="chart-box"><div id="avgChart"></div></div>

    <h2>95th Percentile Response Time</h2>
    <div class="chart-box"><div id="p95Chart"></div></div>

    <h2>Throughput Comparison</h2>
    <div class="chart-box"><div id="rpsChart"></div></div>
</div>

<script>
    const data = {comparison_json};
    const endpoints = ['Create Cart', 'Add Item', 'Cancel Cart'];

    // Avg response chart
    Plotly.newPlot('avgChart', [
        {{ x: endpoints, y: endpoints.map(e => data[e]?.apikey_avg || 0), name: 'API Key', type: 'bar', marker: {{ color: '#FF9800' }} }},
        {{ x: endpoints, y: endpoints.map(e => data[e]?.jwt_avg || 0), name: 'JWT', type: 'bar', marker: {{ color: '#4CAF50' }} }}
    ], {{ barmode: 'group', title: 'Average Response Time (ms) - Lower is Better', yaxis: {{ title: 'ms' }}, height: 400 }}, {{responsive: true}});

    // P95 chart
    Plotly.newPlot('p95Chart', [
        {{ x: endpoints, y: endpoints.map(e => data[e]?.apikey_p95 || 0), name: 'API Key', type: 'bar', marker: {{ color: '#FF9800' }} }},
        {{ x: endpoints, y: endpoints.map(e => data[e]?.jwt_p95 || 0), name: 'JWT', type: 'bar', marker: {{ color: '#4CAF50' }} }}
    ], {{ barmode: 'group', title: '95th Percentile Response Time (ms) - Lower is Better', yaxis: {{ title: 'ms' }}, height: 400 }}, {{responsive: true}});

    // RPS chart
    Plotly.newPlot('rpsChart', [
        {{ x: endpoints, y: endpoints.map(e => data[e]?.apikey_rps || 0), name: 'API Key', type: 'bar', marker: {{ color: '#FF9800' }} }},
        {{ x: endpoints, y: endpoints.map(e => data[e]?.jwt_rps || 0), name: 'JWT', type: 'bar', marker: {{ color: '#4CAF50' }} }}
    ], {{ barmode: 'group', title: 'Requests per Second - Higher is Better', yaxis: {{ title: 'req/s' }}, height: 400 }}, {{responsive: true}});
</script>
</body>
</html>"""

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✓ JWT vs API Key comparison report: {output_html}")


def main():
    if len(sys.argv) != 4:
        print("Usage: python generate_jwt_comparison_report.py <output.html> <apikey_stats.csv> <jwt_stats.csv>")
        sys.exit(1)
    generate_comparison_report(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
