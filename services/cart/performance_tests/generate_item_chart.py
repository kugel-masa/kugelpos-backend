# Copyright 2025 masa@kugel
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
Generate HTML report with Add Item performance chart from Locust CSV output
"""

import sys
import pandas as pd
from pathlib import Path


def generate_item_chart(csv_stats_path: str, output_html_path: str):
    """
    Generate HTML report with Add Item performance chart

    Args:
        csv_stats_path: Path to Locust CSV stats file
        output_html_path: Path to output HTML file
    """
    # Read CSV data
    df = pd.read_csv(csv_stats_path)

    # Filter for Add Item requests only
    add_item_df = df[df['Name'] == 'POST /api/v1/carts/[cart_id]/lineItems (Add Item)']

    if add_item_df.empty:
        print("Warning: No Add Item data found in CSV")
        return

    # Extract metrics
    stats = add_item_df.iloc[0]

    # Generate HTML with chart
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Add Item Performance Report</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #555;
            margin-top: 30px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-card.success {{
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        }}
        .metric-card.error {{
            background: linear-gradient(135deg, #f44336 0%, #da190b 100%);
        }}
        .metric-label {{
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 28px;
            font-weight: bold;
        }}
        .metric-unit {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .chart-container {{
            margin: 30px 0;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            background-color: #fafafa;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Add Item Performance Report</h1>
        <p>Endpoint: <code>POST /api/v1/carts/[cart_id]/lineItems</code></p>

        <h2>Key Metrics</h2>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-label">Total Requests</div>
                <div class="metric-value">{int(stats['Request Count'])}</div>
            </div>
            <div class="metric-card success">
                <div class="metric-label">Success Rate</div>
                <div class="metric-value">{100 - (stats['Failure Count'] / stats['Request Count'] * 100):.1f}<span class="metric-unit">%</span></div>
            </div>
            <div class="metric-card error">
                <div class="metric-label">Failures</div>
                <div class="metric-value">{int(stats['Failure Count'])}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Requests/sec</div>
                <div class="metric-value">{stats['Requests/s']:.2f}</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Response Time</div>
                <div class="metric-value">{int(stats['Average Response Time'])}<span class="metric-unit">ms</span></div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Median Response Time</div>
                <div class="metric-value">{int(stats['Median Response Time'])}<span class="metric-unit">ms</span></div>
            </div>
        </div>

        <h2>Response Time Distribution</h2>
        <div class="chart-container">
            <div id="responseTimeChart"></div>
        </div>

        <h2>Response Time Percentiles</h2>
        <div class="chart-container">
            <div id="percentilesChart"></div>
        </div>

        <h2>Detailed Statistics</h2>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Total Requests</td>
                <td>{int(stats['Request Count'])}</td>
            </tr>
            <tr>
                <td>Failures</td>
                <td>{int(stats['Failure Count'])}</td>
            </tr>
            <tr>
                <td>Success Rate</td>
                <td>{100 - (stats['Failure Count'] / stats['Request Count'] * 100):.2f}%</td>
            </tr>
            <tr>
                <td>Requests per second</td>
                <td>{stats['Requests/s']:.2f}</td>
            </tr>
            <tr>
                <td>Failures per second</td>
                <td>{stats['Failures/s']:.2f}</td>
            </tr>
            <tr>
                <td>Average Response Time</td>
                <td>{int(stats['Average Response Time'])} ms</td>
            </tr>
            <tr>
                <td>Min Response Time</td>
                <td>{int(stats['Min Response Time'])} ms</td>
            </tr>
            <tr>
                <td>Max Response Time</td>
                <td>{int(stats['Max Response Time'])} ms</td>
            </tr>
            <tr>
                <td>Median Response Time (50%ile)</td>
                <td>{int(stats['Median Response Time'])} ms</td>
            </tr>
            <tr>
                <td>95th Percentile</td>
                <td>{int(stats['95%'])} ms</td>
            </tr>
            <tr>
                <td>99th Percentile</td>
                <td>{int(stats['99%'])} ms</td>
            </tr>
            <tr>
                <td>Average Content Size</td>
                <td>{int(stats['Average Content Size'])} bytes</td>
            </tr>
        </table>
    </div>

    <script>
        // Response Time Distribution Chart
        var responseTimeData = [{{
            x: ['Min', 'Average', 'Median', '95%ile', '99%ile', 'Max'],
            y: [{int(stats['Min Response Time'])}, {int(stats['Average Response Time'])},
                {int(stats['Median Response Time'])}, {int(stats['95%'])},
                {int(stats['99%'])}, {int(stats['Max Response Time'])}],
            type: 'bar',
            marker: {{
                color: ['#4CAF50', '#2196F3', '#FFC107', '#FF9800', '#FF5722', '#F44336']
            }},
            text: [{int(stats['Min Response Time'])}, {int(stats['Average Response Time'])},
                   {int(stats['Median Response Time'])}, {int(stats['95%'])},
                   {int(stats['99%'])}, {int(stats['Max Response Time'])}],
            textposition: 'outside',
        }}];

        var responseTimeLayout = {{
            title: 'Response Time Metrics (ms)',
            yaxis: {{
                title: 'Response Time (ms)'
            }},
            height: 400,
            margin: {{ t: 40, b: 40, l: 60, r: 20 }}
        }};

        Plotly.newPlot('responseTimeChart', responseTimeData, responseTimeLayout, {{responsive: true}});

        // Percentiles Chart
        var percentilesData = [{{
            x: ['50%', '66%', '75%', '80%', '90%', '95%', '98%', '99%', '99.9%', '99.99%', '100%'],
            y: [{int(stats['Median Response Time'])}, {int(stats['66%'])}, {int(stats['75%'])},
                {int(stats['80%'])}, {int(stats['90%'])}, {int(stats['95%'])},
                {int(stats['98%'])}, {int(stats['99%'])}, {int(stats['99.9%'])},
                {int(stats['99.99%'])}, {int(stats['100%'])}],
            type: 'scatter',
            mode: 'lines+markers',
            marker: {{
                color: '#2196F3',
                size: 8
            }},
            line: {{
                color: '#2196F3',
                width: 2
            }}
        }}];

        var percentilesLayout = {{
            title: 'Response Time Percentiles',
            xaxis: {{
                title: 'Percentile'
            }},
            yaxis: {{
                title: 'Response Time (ms)'
            }},
            height: 400,
            margin: {{ t: 40, b: 60, l: 60, r: 20 }}
        }};

        Plotly.newPlot('percentilesChart', percentilesData, percentilesLayout, {{responsive: true}});
    </script>
</body>
</html>
"""

    # Write HTML file
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Add Item chart generated: {output_html_path}")


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: python generate_item_chart.py <csv_stats_file> <output_html>")
        print("Example: python generate_item_chart.py results/Pattern_1_stats.csv results/Pattern_1_add_item.html")
        sys.exit(1)

    csv_stats_path = sys.argv[1]
    output_html_path = sys.argv[2]

    if not Path(csv_stats_path).exists():
        print(f"Error: CSV file not found: {csv_stats_path}")
        sys.exit(1)

    generate_item_chart(csv_stats_path, output_html_path)


if __name__ == "__main__":
    main()
