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
Generate comprehensive comparison report from multiple Locust test results
"""

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime
import json


def extract_user_count(filename: str) -> int:
    """Extract user count from filename (e.g., Custom_5users_... -> 5)"""
    import re
    match = re.search(r'Custom_(\d+)users', filename)
    if match:
        return int(match.group(1))
    return 0


def generate_comparison_report(csv_files: list[str], output_html_path: str):
    """
    Generate HTML comparison report from multiple CSV stats files

    Args:
        csv_files: List of paths to Locust CSV stats files
        output_html_path: Path to output HTML file
    """
    # Read all CSV files
    all_data = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        user_count = extract_user_count(Path(csv_file).name)
        df['user_count'] = user_count
        df['file'] = Path(csv_file).name
        all_data.append(df)

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)

    # Sort by user count
    combined_df = combined_df.sort_values('user_count')

    # Get unique user counts
    user_counts = sorted(combined_df['user_count'].unique())

    # Prepare data for charts
    endpoints = {
        'Create Cart': 'POST /api/v1/carts (Create Cart)',
        'Add Item': 'POST /api/v1/carts/[cart_id]/lineItems (Add Item)',
        'Cancel Cart': 'POST /api/v1/carts/[cart_id]/cancel (Cancel Cart)',
        'Aggregated': 'Aggregated'
    }

    # Extract metrics for each endpoint and user count
    metrics_data = {}
    for endpoint_name, endpoint_full in endpoints.items():
        metrics_data[endpoint_name] = {
            'users': [],
            'avg_response': [],
            'median_response': [],
            'p95_response': [],
            'p99_response': [],
            'requests_per_sec': [],
            'total_requests': [],
            'failures': []
        }

        for user_count in user_counts:
            subset = combined_df[
                (combined_df['user_count'] == user_count) &
                (combined_df['Name'] == endpoint_full)
            ]

            if not subset.empty:
                row = subset.iloc[0]
                metrics_data[endpoint_name]['users'].append(int(user_count))
                metrics_data[endpoint_name]['avg_response'].append(float(row['Average Response Time']))
                metrics_data[endpoint_name]['median_response'].append(float(row['Median Response Time']))
                metrics_data[endpoint_name]['p95_response'].append(float(row['95%']))
                metrics_data[endpoint_name]['p99_response'].append(float(row['99%']))
                metrics_data[endpoint_name]['requests_per_sec'].append(float(row['Requests/s']))
                metrics_data[endpoint_name]['total_requests'].append(int(row['Request Count']))
                metrics_data[endpoint_name]['failures'].append(int(row['Failure Count']))

    # Convert to JSON for JavaScript
    metrics_json = json.dumps(metrics_data)

    # Generate summary statistics table
    summary_rows = []
    for user_count in user_counts:
        subset = combined_df[
            (combined_df['user_count'] == user_count) &
            (combined_df['Name'] == 'Aggregated')
        ]
        if not subset.empty:
            row = subset.iloc[0]
            summary_rows.append(f"""
                <tr>
                    <td>{user_count}</td>
                    <td>{int(row['Request Count'])}</td>
                    <td>{int(row['Failure Count'])}</td>
                    <td>{row['Requests/s']:.2f}</td>
                    <td>{int(row['Average Response Time'])}</td>
                    <td>{int(row['Median Response Time'])}</td>
                    <td>{int(row['95%'])}</td>
                    <td>{int(row['99%'])}</td>
                </tr>
            """)

    summary_table = "\n".join(summary_rows)

    # Generate detailed endpoint tables
    endpoint_tables = []
    for endpoint_name, endpoint_full in endpoints.items():
        if endpoint_name == 'Aggregated':
            continue

        rows = []
        for user_count in user_counts:
            subset = combined_df[
                (combined_df['user_count'] == user_count) &
                (combined_df['Name'] == endpoint_full)
            ]
            if not subset.empty:
                row = subset.iloc[0]
                rows.append(f"""
                    <tr>
                        <td>{user_count}</td>
                        <td>{int(row['Request Count'])}</td>
                        <td>{int(row['Failure Count'])}</td>
                        <td>{row['Requests/s']:.2f}</td>
                        <td>{int(row['Average Response Time'])}</td>
                        <td>{int(row['Median Response Time'])}</td>
                        <td>{int(row['95%'])}</td>
                        <td>{int(row['99%'])}</td>
                        <td>{int(row['Min Response Time'])}</td>
                        <td>{int(row['Max Response Time'])}</td>
                    </tr>
                """)

        if rows:
            endpoint_tables.append(f"""
                <h3>{endpoint_name}</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Users</th>
                            <th>Total Requests</th>
                            <th>Failures</th>
                            <th>Req/s</th>
                            <th>Avg (ms)</th>
                            <th>Median (ms)</th>
                            <th>95%ile (ms)</th>
                            <th>99%ile (ms)</th>
                            <th>Min (ms)</th>
                            <th>Max (ms)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(rows)}
                    </tbody>
                </table>
            """)

    endpoint_tables_html = "\n".join(endpoint_tables)

    # Generate HTML report
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Performance Test Comparison Report</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1600px;
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
            margin-top: 40px;
            border-bottom: 2px solid #ddd;
            padding-bottom: 8px;
        }}
        h3 {{
            color: #666;
            margin-top: 30px;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-card.success {{
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        }}
        .summary-label {{
            font-size: 12px;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .summary-value {{
            font-size: 28px;
            font-weight: bold;
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
            font-size: 14px;
        }}
        th, td {{
            padding: 12px 8px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .info-box {{
            background-color: #e3f2fd;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .timestamp {{
            color: #666;
            font-size: 14px;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Performance Test Comparison Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

        <div class="info-box">
            <strong>Test Configuration:</strong>
            <ul>
                <li>User counts tested: {', '.join(map(str, user_counts))}</li>
                <li>Test duration: 3 minutes each</li>
                <li>Items per cart: 20</li>
                <li>Item add interval: 3 seconds</li>
            </ul>
        </div>

        <h2>Overall Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Users</th>
                    <th>Total Requests</th>
                    <th>Failures</th>
                    <th>Req/s</th>
                    <th>Avg Response (ms)</th>
                    <th>Median (ms)</th>
                    <th>95%ile (ms)</th>
                    <th>99%ile (ms)</th>
                </tr>
            </thead>
            <tbody>
                {summary_table}
            </tbody>
        </table>

        <h2>Throughput Comparison</h2>
        <div class="chart-container">
            <div id="throughputChart"></div>
        </div>

        <h2>Response Time Comparison - Average</h2>
        <div class="chart-container">
            <div id="avgResponseChart"></div>
        </div>

        <h2>Response Time Comparison - Median</h2>
        <div class="chart-container">
            <div id="medianResponseChart"></div>
        </div>

        <h2>Response Time Comparison - 95th Percentile</h2>
        <div class="chart-container">
            <div id="p95ResponseChart"></div>
        </div>

        <h2>Response Time Comparison - 99th Percentile</h2>
        <div class="chart-container">
            <div id="p99ResponseChart"></div>
        </div>

        <h2>Detailed Endpoint Statistics</h2>
        {endpoint_tables_html}
    </div>

    <script>
        const metricsData = {metrics_json};

        // Throughput Chart
        const throughputTraces = [];
        const colors = {{
            'Create Cart': '#4CAF50',
            'Add Item': '#2196F3',
            'Cancel Cart': '#FF9800',
            'Aggregated': '#9C27B0'
        }};

        for (const [endpoint, data] of Object.entries(metricsData)) {{
            throughputTraces.push({{
                x: data.users,
                y: data.requests_per_sec,
                type: 'scatter',
                mode: 'lines+markers',
                name: endpoint,
                line: {{ color: colors[endpoint], width: 2 }},
                marker: {{ size: 8 }}
            }});
        }}

        const throughputLayout = {{
            title: 'Requests per Second by User Count',
            xaxis: {{ title: 'Number of Users' }},
            yaxis: {{ title: 'Requests/sec' }},
            height: 500,
            margin: {{ t: 60, b: 60, l: 80, r: 20 }},
            hovermode: 'x unified'
        }};

        Plotly.newPlot('throughputChart', throughputTraces, throughputLayout, {{responsive: true}});

        // Average Response Time Chart
        const avgResponseTraces = [];
        for (const [endpoint, data] of Object.entries(metricsData)) {{
            if (endpoint !== 'Aggregated') {{
                avgResponseTraces.push({{
                    x: data.users,
                    y: data.avg_response,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: endpoint,
                    line: {{ color: colors[endpoint], width: 2 }},
                    marker: {{ size: 8 }}
                }});
            }}
        }}

        const avgResponseLayout = {{
            title: 'Average Response Time by User Count',
            xaxis: {{ title: 'Number of Users' }},
            yaxis: {{ title: 'Response Time (ms)' }},
            height: 500,
            margin: {{ t: 60, b: 60, l: 80, r: 20 }},
            hovermode: 'x unified'
        }};

        Plotly.newPlot('avgResponseChart', avgResponseTraces, avgResponseLayout, {{responsive: true}});

        // Median Response Time Chart
        const medianResponseTraces = [];
        for (const [endpoint, data] of Object.entries(metricsData)) {{
            if (endpoint !== 'Aggregated') {{
                medianResponseTraces.push({{
                    x: data.users,
                    y: data.median_response,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: endpoint,
                    line: {{ color: colors[endpoint], width: 2 }},
                    marker: {{ size: 8 }}
                }});
            }}
        }}

        const medianResponseLayout = {{
            title: 'Median Response Time by User Count',
            xaxis: {{ title: 'Number of Users' }},
            yaxis: {{ title: 'Response Time (ms)' }},
            height: 500,
            margin: {{ t: 60, b: 60, l: 80, r: 20 }},
            hovermode: 'x unified'
        }};

        Plotly.newPlot('medianResponseChart', medianResponseTraces, medianResponseLayout, {{responsive: true}});

        // 95th Percentile Response Time Chart
        const p95ResponseTraces = [];
        for (const [endpoint, data] of Object.entries(metricsData)) {{
            if (endpoint !== 'Aggregated') {{
                p95ResponseTraces.push({{
                    x: data.users,
                    y: data.p95_response,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: endpoint,
                    line: {{ color: colors[endpoint], width: 2 }},
                    marker: {{ size: 8 }}
                }});
            }}
        }}

        const p95ResponseLayout = {{
            title: '95th Percentile Response Time by User Count',
            xaxis: {{ title: 'Number of Users' }},
            yaxis: {{ title: 'Response Time (ms)' }},
            height: 500,
            margin: {{ t: 60, b: 60, l: 80, r: 20 }},
            hovermode: 'x unified'
        }};

        Plotly.newPlot('p95ResponseChart', p95ResponseTraces, p95ResponseLayout, {{responsive: true}});

        // 99th Percentile Response Time Chart
        const p99ResponseTraces = [];
        for (const [endpoint, data] of Object.entries(metricsData)) {{
            if (endpoint !== 'Aggregated') {{
                p99ResponseTraces.push({{
                    x: data.users,
                    y: data.p99_response,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: endpoint,
                    line: {{ color: colors[endpoint], width: 2 }},
                    marker: {{ size: 8 }}
                }});
            }}
        }}

        const p99ResponseLayout = {{
            title: '99th Percentile Response Time by User Count',
            xaxis: {{ title: 'Number of Users' }},
            yaxis: {{ title: 'Response Time (ms)' }},
            height: 500,
            margin: {{ t: 60, b: 60, l: 80, r: 20 }},
            hovermode: 'x unified'
        }};

        Plotly.newPlot('p99ResponseChart', p99ResponseTraces, p99ResponseLayout, {{responsive: true}});
    </script>
</body>
</html>
"""

    # Write HTML file
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✓ Comparison report generated: {output_html_path}")


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python generate_comparison_report.py <output_html> <csv_file1> <csv_file2> ...")
        print("Example: python generate_comparison_report.py comparison.html results/*_stats.csv")
        sys.exit(1)

    output_html_path = sys.argv[1]
    csv_files = sys.argv[2:]

    # Filter out non-CSV files and verify they exist
    valid_csv_files = []
    for csv_file in csv_files:
        if Path(csv_file).exists() and csv_file.endswith('_stats.csv'):
            valid_csv_files.append(csv_file)
        else:
            print(f"Warning: Skipping invalid or non-existent file: {csv_file}")

    if len(valid_csv_files) < 2:
        print("Error: At least 2 valid CSV stats files are required for comparison")
        sys.exit(1)

    print(f"Comparing {len(valid_csv_files)} test results...")
    generate_comparison_report(valid_csv_files, output_html_path)


if __name__ == "__main__":
    main()
