#!/usr/bin/env python3
"""
Financial Report Generator - Multi-File Support with Column Copy & Month Filters
- Copy columns with one click
- Click on months to filter transactions
- Upgraded modern dashboard design & improved date picker UI
"""

import csv
from datetime import datetime
from collections import defaultdict
import sys
import json
import glob
import os
from turtle import left

class InteractiveFinancialReport:
    def __init__(self, csv_file_paths, mapping_file=None):
        """
        Initialize with either a single file path or a list of file paths.
        Supports wildcards like '*.csv' or 'transactions_*.csv'
        """
        if isinstance(csv_file_paths, str):
            if '*' in csv_file_paths:
                self.csv_files = glob.glob(csv_file_paths)
            else:
                self.csv_files = [csv_file_paths]
        else:
            self.csv_files = csv_file_paths
        
        self.csv_files = sorted(self.csv_files)
        
        self.transactions = []
        self.merchant_totals = defaultdict(float)
        self.daily_totals = defaultdict(float)
        self.monthly_totals = defaultdict(float)
        self.category_totals = defaultdict(float)
        self.total_debits = 0.0
        self.total_credits = 0.0
        self.starting_balance = None
        self.ending_balance = None
        self.transaction_count = 0
        self.merchants = set()
        self.categories = set()
        self.file_sources = {}
        self.mapping_file = mapping_file
        self.merchant_categories = {}
        self.uncategorized_label = 'Uncategorized'

    def parse_date(self, date_str):
        """Parse date from YYYY-MM-DD format."""
        return datetime.strptime(date_str.strip(), '%Y-%m-%d')

    def _load_merchant_mapping(self):
        """Load the merchant -> category mapping CSV, if available."""
        candidates = []
        if self.mapping_file:
            candidates.append(self.mapping_file)
        if self.csv_files:
            candidates.append(os.path.join(os.path.dirname(os.path.abspath(self.csv_files[0])), 'merchant_mapping.csv'))
        candidates.append('merchant_mapping.csv')

        mapping_path = None
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                mapping_path = candidate
                break

        if not mapping_path:
            print("ℹ️  No merchant_mapping.csv found - transactions will be categorized as 'Uncategorized'.")
            return

        try:
            with open(mapping_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    merchant = (row.get('Merchant Name') or '').strip()
                    category = (row.get('Category') or '').strip()
                    if merchant and category:
                        self.merchant_categories[merchant] = category
                        count += 1
            print(f"🏷️  Loaded {count} merchant category mappings from {mapping_path}")
        except Exception as e:
            print(f"Warning: Could not load merchant mapping file {mapping_path}: {e}")

    def load_data(self):
        """Load and parse all CSV files."""
        if not self.csv_files:
            print("Error: No CSV files found.")
            return False
        
        print(f"📁 Found {len(self.csv_files)} CSV file(s):")
        for f in self.csv_files:
            print(f"   - {f}")
        print()
        
        self._load_merchant_mapping()
        
        total_loaded = 0
        for file_path in self.csv_files:
            try:
                loaded = self._load_single_file(file_path)
                total_loaded += loaded
                print(f"✅ Loaded {loaded} transactions from {os.path.basename(file_path)}")
            except Exception as e:
                print(f"❌ Error loading {file_path}: {e}")
        
        if total_loaded == 0:
            print("Error: No transactions loaded from any file.")
            return False
        
        if self.transactions:
            self.transactions.sort(key=lambda x: x['date'])
            
            oldest = self.transactions[0]
            if oldest['balance'] is not None:
                self.starting_balance = oldest['balance'] + oldest['debit'] - oldest['credit']
            else:
                self.starting_balance = 0.0
                running_balance = 0.0
                for tx in self.transactions:
                    running_balance += tx['credit'] - tx['debit']
                    if tx['balance'] is None:
                        tx['balance'] = running_balance
            
            self.ending_balance = self.transactions[-1]['balance']
            self.transaction_count = len(self.transactions)
            # print(f"\n📊 Total: {self.transaction_count} transactions loaded from {len(self.csv_files)} files")
            return True
    
    def _load_single_file(self, file_path):
        """Load a single CSV file."""
        loaded_count = 0
        with open(file_path, 'r') as file:
            reader = csv.reader(file)
            rows = list(reader)
            
            if not rows:
                return 0
            
            for row in rows:
                if len(row) < 5:
                    print(f"Warning: Skipping malformed row in {file_path}: {row}")
                    continue
                
                try:
                    date_str, merchant, debit_str, credit_str, balance_str = row
                    
                    date = self.parse_date(date_str)
                    merchant = merchant.strip()
                    debit = float(debit_str.strip()) if debit_str.strip() else 0.0
                    credit = float(credit_str.strip()) if credit_str.strip() else 0.0
                    balance = float(balance_str.strip()) if balance_str.strip() else None
                    
                    month_key = date.strftime('%Y-%m')
                    date_key = date.strftime('%Y-%m-%d')
                    category = self.merchant_categories.get(merchant, self.uncategorized_label)
                    
                    self.transactions.append({
                        'date': date,
                        'merchant': merchant,
                        'category': category,
                        'debit': debit,
                        'credit': credit,
                        'balance': balance,
                        'date_str': date_key,
                        'month': month_key,
                        'month_display': date.strftime('%B %Y'),
                        'source_file': os.path.basename(file_path)
                    })
                    
                    self.merchants.add(merchant)
                    self.categories.add(category)
                    
                    if debit > 0:
                        self.total_debits += debit
                        self.merchant_totals[merchant] += debit
                        self.daily_totals[date_key] += debit
                        self.monthly_totals[month_key] += debit
                        self.category_totals[category] += debit
                    
                    if credit > 0:
                        self.total_credits += credit
                    
                    loaded_count += 1
                    
                except Exception as e:
                    print(f"Warning: Error parsing row in {file_path}: {e}")
                    continue
        
        return loaded_count
    
    def generate_html(self, output_file=None):
        """Generate interactive HTML report with copy and month filters."""
        if not self.transactions:
            print("No transactions to report.")
            return
        
        if output_file is None:
            output_file = f"interactive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        all_transactions = []
        for tx in self.transactions:
            all_transactions.append({
                'date': tx['date'].strftime('%Y-%m-%d'),
                'date_display': tx['date'].strftime('%b %d, %Y'),
                'merchant': tx['merchant'],
                'category': tx.get('category', self.uncategorized_label),
                'debit': round(tx['debit'], 2),
                'credit': round(tx['credit'], 2),
                'balance': round(tx['balance'], 2) if tx['balance'] is not None else None,
                'source': tx.get('source_file', 'Unknown'),
                'month': tx['month'],
                'month_display': tx['month_display']
            })
        
        merchants_list = sorted(list(self.merchants))
        categories_list = sorted(list(self.categories))
        
        dates = [tx['date'] for tx in self.transactions]
        min_date = min(dates).strftime('%Y-%m-%d')
        max_date = max(dates).strftime('%Y-%m-%d')
        
        merchant_data = sorted(self.merchant_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        category_data = sorted(self.category_totals.items(), key=lambda x: x[1], reverse=True)
        
        monthly_data = sorted(self.monthly_totals.items(), key=lambda x: x[0])
        months_list = []
        for month_key, total in monthly_data:
            year, month = month_key.split('-')
            date_obj = datetime(int(year), int(month), 1)
            display = date_obj.strftime('%b %Y')
            months_list.append({
                'key': month_key,
                'display': display,
                'total': round(total, 2)
            })
        
        html_content = self._build_html(
            all_transactions, 
            merchants_list, 
            min_date, 
            max_date, 
            merchant_data,
            self.csv_files,
            months_list,
            categories_list,
            category_data
        )
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"\n✅ Interactive HTML report generated: {output_file}")
        return output_file
    
    def _build_html(self, all_transactions, merchants_list, min_date, max_date, merchant_data, csv_files, months_list, categories_list, category_data):
        """Build the HTML content."""
        total_debits_str = f"${self.total_debits:,.2f}"
        total_credits_str = f"${self.total_credits:,.2f}"
        net_change = self.total_credits - self.total_debits
        net_change_str = f"${net_change:,.2f}"
        net_change_class = 'negative' if net_change < 0 else 'positive'
        
        merchant_options = ''.join([f'<option value="{m}">{m}</option>' for m in merchants_list])
        category_options = ''.join([f'<option value="{c}">{c}</option>' for c in categories_list])
        
        file_count = len(csv_files)
        file_list = ', '.join([os.path.basename(f) for f in csv_files[:5]])
        if len(csv_files) > 5:
            file_list += f' and {len(csv_files) - 5} more'
        
        month_buttons = ''
        for month in months_list:
            month_buttons += f'''
                <button class="month-btn" onclick="filterByMonth('{month['key']}')" title="Total: ${month['total']:,.2f}">
                    <span class="m-name">{month['display']}</span>
                    <span class="m-total">${month['total']:,.0f}</span>
                </button>
            '''
        
        transactions_json = json.dumps(all_transactions)
        
        html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Financial Intelligence Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        :root {{
            --bg-main: #f8fafc;
            --panel-bg: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --primary-light: #eef2ff;
            --success: #10b981;
            --danger: #ef4444;
            --border: #e2e8f0;
            --radius-lg: 16px;
            --radius-md: 10px;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.05);
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, sans-serif; }}
        body {{ background-color: var(--bg-main); color: var(--text-main); padding: 40px 20px; }}
        .container {{ max-width: 1440px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }}
        
        /* Dashboard Header */
        .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #311042 100%); color: white; padding: 32px; border-radius: var(--radius-lg); box-shadow: var(--shadow-lg); position: relative; overflow: hidden; }}
        .header h1 {{ font-size: 28px; font-weight: 800; letter-spacing: -0.5px; margin-bottom: 6px; display: flex; align-items: center; gap: 10px; }}
        .header .subtitle {{ opacity: 0.7; font-size: 14px; font-weight: 400; }}
        .header .file-info {{ margin-top: 16px; padding: 8px 14px; background: rgba(255,255,255,0.08); border-radius: var(--radius-md); font-size: 13px; display: inline-flex; align-items: center; gap: 6px; border: 1px solid rgba(255,255,255,0.1); color: #e2e8f0; }}
        
        /* Grid Layout Framework */
        .main-layout {{ display: grid; grid-template-columns: 320px 1fr; gap: 24px; align-items: start; }}
        .sidebar {{ display: flex; flex-direction: column; gap: 24px; position: sticky; top: 24px; }}
        .content-area {{ display: flex; flex-direction: column; gap: 24px; }}

        /* Panel Wrapper style */
        .panel {{ background: var(--panel-bg); border-radius: var(--radius-lg); padding: 24px; border: 1px solid var(--border); box-shadow: var(--shadow-sm); }}
        .panel-title {{ font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted); margin-bottom: 16px; display: flex; align-items: center; justify-content: space-between; }}

        /* Unified Custom Date Widget */
        .date-widget {{ display: flex; flex-direction: column; gap: 12px; background: #fafafa; padding: 14px; border-radius: var(--radius-md); border: 1px solid var(--border); }}
        .date-inputs {{ display: flex; align-items: center; gap: 8px; }}
        .date-inputs input[type="date"] {{ width: 100%; padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; font-size: 13px; color: var(--text-main); background: white; font-weight: 500; outline: none; transition: border 0.2s; }}
        .date-inputs input[type="date"]:focus {{ border-color: var(--primary); }}
        .date-separator {{ font-size: 12px; color: var(--text-muted); font-weight: 600; }}
        .date-presets {{ display: flex; flex-wrap: wrap; gap: 6px; }}
        .preset-tag {{ font-size: 11px; font-weight: 600; background: white; border: 1px solid var(--border); padding: 4px 8px; border-radius: 4px; cursor: pointer; color: var(--text-muted); transition: all 0.15s; }}
        .preset-tag:hover {{ border-color: var(--primary); color: var(--primary); background: var(--primary-light); }}

        /* Filters Elements */
        .filter-field {{ display: flex; flex-direction: column; gap: 6px; margin-bottom: 16px; }}
        .filter-field label {{ font-size: 12px; font-weight: 600; color: var(--text-main); }}
        .filter-field select, .filter-field input[type="text"] {{ width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: var(--radius-md); font-size: 14px; color: var(--text-main); background-color: white; outline: none; }}
        .filter-field select:focus, .filter-field input:focus {{ border-color: var(--primary); box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }}
        
        .sidebar-actions {{ display: grid; grid-template-columns: 2fr 1fr; gap: 8px; margin-top: 8px; }}
        .btn {{ padding: 10px 16px; border-radius: var(--radius-md); border: none; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-flex; align-items: center; justify-content: center; gap: 6px; }}
        .btn-primary {{ background: var(--primary); color: white; }}
        .btn-primary:hover {{ background: var(--primary-hover); }}
        .btn-secondary {{ background: #f1f5f9; color: var(--text-muted); }}
        .btn-secondary:hover {{ background: #e2e8f0; color: var(--text-main); }}

        /* Top Timeline / Horizontal Slider */
        .timeline-container {{ display: flex; flex-direction: column; gap: 10px; background: white; padding: 18px 24px; border-radius: var(--radius-lg); border: 1px solid var(--border); box-shadow: var(--shadow-sm); }}
        .month-buttons {{ display: flex; gap: 8px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: thin; }}
        .month-btn {{ flex: 0 0 auto; padding: 8px 14px; border: 1px solid var(--border); border-radius: var(--radius-md); background: white; cursor: pointer; display: flex; flex-direction: column; align-items: flex-start; gap: 2px; min-width: 90px; transition: all 0.2s; }}
        .month-btn .m-name {{ font-size: 12px; font-weight: 700; color: var(--text-main); }}
        .month-btn .m-total {{ font-size: 11px; color: var(--text-muted); }}
        .month-btn:hover {{ border-color: var(--primary); background: var(--primary-light); }}
        .month-btn.active {{ background: var(--primary); border-color: var(--primary); }}
        .month-btn.active .m-name, .month-btn.active .m-total {{ color: white; }}

        /* Stats Blocks */
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
        .stat-card {{ background: white; padding: 20px 24px; border-radius: var(--radius-lg); border: 1px solid var(--border); box-shadow: var(--shadow-sm); display: flex; flex-direction: column; gap: 4px; }}
        .stat-card .label {{ font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }}
        .stat-card .value {{ font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
        .stat-card .value.negative {{ color: var(--danger); }}
        .stat-card .value.positive {{ color: var(--success); }}
        
        /* Charts Dynamic Row */
        .charts-row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }}
        .chart-card {{ display: flex; flex-direction: column; }}
        .chart-wrap {{ position: relative; height: 260px; width: 100%; margin: auto; }}
        .click-hint {{ text-align: center; font-size: 11px; color: var(--text-muted); margin-top: 12px; font-style: italic; }}

        /* Main Data Table View */
        .table-card {{ background: white; border-radius: var(--radius-lg); border: 1px solid var(--border); box-shadow: var(--shadow-sm); overflow: hidden; }}
        .table-header-box {{ padding: 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }}
        .table-header-box h3 {{ font-size: 16px; font-weight: 700; }}
        .table-wrapper {{ overflow-x: auto; }}
        
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 14px; }}
        th {{ background: #f8fafc; padding: 14px 20px; font-weight: 600; color: var(--text-muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); cursor: pointer; user-select: none; }}
        th:hover {{ color: var(--primary); background-color: #f1f5f9; }}
        td {{ padding: 14px 20px; border-bottom: 1px solid #f1f5f9; color: #334155; vertical-align: middle; }}
        tr:hover td {{ background-color: #f8fafc; }}
        
        .copy-col-btn {{ opacity: 0.3; font-size: 11px; margin-left: 4px; transition: opacity 0.2s; }}
        .sort-arrow {{ margin-left: 6px; color: var(--primary); font-size: 10px; }}
        th:hover .copy-col-btn {{ opacity: 1; }}
        
        /* Badges styling */
        .badge {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .badge-debit {{ background: #fef2f2; color: var(--danger); }}
        .badge-credit {{ background: #ecfdf5; color: var(--success); }}
        .badge-cat {{ background: #f5f3ff; color: #6d28d9; }}
        .badge-src {{ background: #f0fdf4; color: #166534; font-size: 11px; font-weight: 500; border: 1px solid #bbf7d0; }}

        /* Indicator Notice */
        .drill-notice {{ background: #fffbeb; border: 1px solid #fef3c7; border-left: 4px solid #f59e0b; padding: 14px 20px; border-radius: var(--radius-md); display: none; justify-content: space-between; align-items: center; font-size: 14px; color: #78350f; }}
        
        .toast {{ position: fixed; bottom: 30px; right: 30px; background: #0f172a; color: white; padding: 12px 24px; border-radius: var(--radius-md); font-size: 14px; font-weight: 500; opacity: 0; pointer-events: none; transition: opacity 0.2s; z-index: 9999; box-shadow: var(--shadow-lg); }}
        .toast.show {{ opacity: 1; }}
        
        @media (max-width: 1100px) {{
            .main-layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ position: static; }}
            .charts-row {{ grid-template-columns: 1fr; }}
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Financial Analytics Intelligence</h1>
            <div class="subtitle">Report Ecosystem Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
            <div class="file-info">Parsed Pipeline: {file_count} dataset archives ({file_list})</div>
        </div>

        <div class="timeline-container">
            <div style="font-size: 12px; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Quick Month Timeline</div>
            <div class="month-buttons">
                <button class="month-btn" onclick="clearMonthFilter()" style="border-color: var(--danger); color: var(--danger); font-weight: 700;">
                    <span class="m-name">ALL TIME</span>
                    <span class="m-total">Reset view</span>
                </button>
                {month_buttons}
            </div>
        </div>

        <div class="drill-notice" id="drillIndicator">
            <div>🔍 Currently isolated focus: <strong id="drillFilterText">None</strong></div>
            <button class="btn btn-secondary" onclick="clearDrill()" style="padding: 4px 10px; font-size: 12px;">Reset Scope</button>
        </div>

        <div class="main-layout">
            <!-- Sidebar Panel Configurations -->
            <div class="sidebar">
                <div class="panel">
                    <div class="panel-title">Report Control Filters</div>
                    
                    <!-- Upgraded Date Ranger Component Container -->
                    <div class="filter-field">
                        <label>Date Range Window</label>
                        <div class="date-widget">
                            <div class="date-inputs">
                                <input type="date" id="startDate" value="{min_date}" onchange="applyFilters()">
                                <span class="date-separator">to</span>
                                <input type="date" id="endDate" value="{max_date}" onchange="applyFilters()">
                            </div>
                            <div class="date-presets">
                                <span class="preset-tag" onclick="setDatePreset('all')">All Time</span>
                                <span class="preset-tag" onclick="setDatePreset('7')">Last 7 Days</span>
                                <span class="preset-tag" onclick="setDatePreset('wtd')">WTD</span>
                                <span class="preset-tag" onclick="setDatePreset('mtd')">MTD</span>
                                <span class="preset-tag" onclick="setDatePreset('30')">Last 30 Days</span>
                                <span class="preset-tag" onclick="setDatePreset('ytd')">YTD</span>
                            </div>
                        </div>
                    </div>

                    <div class="filter-field">
                        <label>Merchant Focus</label>
                        <select id="merchantFilter" onchange="applyFilters()">
                            <option value="">All Identified Merchants</option>
                            {merchant_options}
                        </select>
                    </div>

                    <div class="filter-field">
                        <label>Category Group</label>
                        <select id="categoryFilter" onchange="applyFilters()">
                            <option value="">All Categories</option>
                            {category_options}
                        </select>
                    </div>

                    <div class="filter-field">
                        <label>Transaction Scope Type</label>
                        <select id="typeFilter" onchange="applyFilters()">
                            <option value="all">All Transits</option>
                            <option value="debit">Debits / Outflow Only</option>
                            <option value="credit">Credits / Inflows Only</option>
                        </select>
                    </div>

                    <div class="filter-field">
                        <label>Global Fuzzy Search</label>
                        <input type="text" id="searchFilter" placeholder="Type merchant names..." oninput="applyFilters()">
                    </div>

                    <div class="sidebar-actions">
                        <button class="btn btn-primary" onclick="applyFilters()">Filter</button>
                        <button class="btn btn-secondary" onclick="resetFilters()">Reset</button>
                    </div>
                </div>
            </div>

            <!-- Dashboard Analytics Core Grid -->
            <div class="content-area">
                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="label">Gross Outflow (Debits)</span>
                        <div class="value negative" id="statSpending">{total_debits_str}</div>
                    </div>
                    <div class="stat-card">
                        <span class="label">Gross Inflow (Credits)</span>
                        <div class="value positive" id="statCredits">{total_credits_str}</div>
                    </div>
                    <div class="stat-card">
                        <span class="label">Net Delta Position</span>
                        <div class="value {net_change_class}" id="statNetChange">{net_change_str}</div>
                    </div>
                    <div class="stat-card">
                        <span class="label">Line Count Volume</span>
                        <div class="value" style="color: var(--text-main)" id="statCount">{self.transaction_count}</div>
                    </div>
                </div>

                <div class="charts-row">
                    <div class="panel chart-card">
                        <div class="panel-title">Top 10 Outlays</div>
                        <div class="chart-wrap"><canvas id="merchantChart"></canvas></div>
                        <div class="click-hint">Click arc segment to snap filter slice</div>
                    </div>
                    <div class="panel chart-card">
                        <div class="panel-title">Allocation Profiles</div>
                        <div class="chart-wrap"><canvas id="categoryChart"></canvas></div>
                        <div class="click-hint">Click arc segment to isolate category</div>
                    </div>
                    <div class="panel chart-card">
                        <div class="panel-title">Daily Velocity Trend</div>
                        <div class="chart-wrap"><canvas id="dailyChart"></canvas></div>
                        <div class="click-hint">Select bars to zoom temporal distribution</div>
                    </div>
                </div>

                <div class="table-card">
                    <div class="table-header-box">
                        <h3>Transaction Audit Journal</h3>
                        <button class="btn btn-secondary" onclick="copyAllData()" style="padding: 6px 12px; font-size: 13px;">
                            📋 Copy Dataset Table
                        </button>
                    </div>
                    <div class="table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th onclick="sortTable('date')">Timestamp <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('date')">📋</span></th>
                                    <th onclick="sortTable('merchant')">Beneficiary Counterparty <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('merchant')">📋</span></th>
                                    <th onclick="sortTable('category')">Operational Classification <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('category')">📋</span></th>
                                    <th onclick="sortTable('debit')">Debit Outbound (-) <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('debit')">📋</span></th>
                                    <th onclick="sortTable('credit')">Credit Inbound (+) <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('credit')">📋</span></th>
                                    <th onclick="sortTable('balance')">Derived Ledger Balance <span class="sort-arrow"></span> <span class="copy-col-btn" onclick="event.stopPropagation(); copyColumn('balance')">📋</span></th>
                                    <th>Source Node</th>
                                </tr>
                            </thead>
                            <tbody id="transactionBody"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const allTransactions = {transactions_json};
        const minDateInitial = "{min_date}";
        const maxDateInitial = "{max_date}";
        
        let merchantChart, dailyChart, categoryChart;
        let sortColumn = 'date';
        let sortAscending = false;
        let drillFilter = null;
        let monthFilter = null;

        function showToast(msg) {{
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.classList.add('show');
            setTimeout(() => t.classList.remove('show'), 2500);
        }}

        function setDatePreset(preset) {{
            const startInput = document.getElementById('startDate');
            const endInput = document.getElementById('endDate');
            
            // Establish our anchor "today" as the maximum date available in the dataset
            let anchorDate = new Date(maxDateInitial + 'T00:00:00');
            let start = new Date(maxDateInitial + 'T00:00:00');
            
            if (preset === 'all') {{
                startInput.value = minDateInitial;
                endInput.value = maxDateInitial;
            }} else if (preset === '7') {{
                start.setDate(anchorDate.getDate() - 7);
                startInput.value = start.toISOString().split('T')[0];
                endInput.value = maxDateInitial;
            }} else if (preset === 'wtd') {{
                // Calculate days since Sunday (0) to get start of the current week
                let dayOfWeek = anchorDate.getDay();
                start.setDate(anchorDate.getDate() - dayOfWeek);
                startInput.value = start.toISOString().split('T')[0];
                endInput.value = maxDateInitial;
            }} else if (preset === 'mtd') {{
                // Set to the 1st day of the current anchor month
                start.setDate(1);
                startInput.value = start.toISOString().split('T')[0];
                endInput.value = maxDateInitial;
            }} else if (preset === '30') {{
                start.setDate(anchorDate.getDate() - 30);
                startInput.value = start.toISOString().split('T')[0];
                endInput.value = maxDateInitial;
            }} else if (preset === 'ytd') {{
                startInput.value = anchorDate.getFullYear() + "-01-01";
                endInput.value = maxDateInitial;
            }}
            applyFilters();
        }}

        function filterTransactions(data) {{
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const merchant = document.getElementById('merchantFilter').value;
            const category = document.getElementById('categoryFilter').value;
            const type = document.getElementById('typeFilter').value;
            const search = document.getElementById('searchFilter').value.toLowerCase();
            
            return data.filter(t => {{
                if (monthFilter && t.month !== monthFilter) return false;
                if (startDate && t.date < startDate) return false;
                if (endDate && t.date > endDate) return false;
                if (merchant && t.merchant !== merchant) return false;
                if (category && t.category !== category) return false;
                
                if (drillFilter) {{
                    if (drillFilter.type === 'merchant' && t.merchant !== drillFilter.value) return false;
                    if (drillFilter.type === 'date' && t.date !== drillFilter.value) return false;
                    if (drillFilter.type === 'category' && t.category !== drillFilter.value) return false;
                }}
                
                if (type === 'debit' && t.debit === 0) return false;
                if (type === 'credit' && t.credit === 0) return false;
                if (search && !t.merchant.toLowerCase().includes(search) && !t.category.toLowerCase().includes(search)) return false;
                return true;
            }});
        }}

        function filterByMonth(monthKey) {{
            monthFilter = monthKey;
            document.querySelectorAll('.month-btn').forEach(btn => btn.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            document.getElementById('drillFilterText').textContent = 'Month Metric Boundary (' + monthKey + ')';
            document.getElementById('drillIndicator').style.display = 'flex';
            applyFilters();
        }}

        function clearMonthFilter() {{
            monthFilter = null;
            document.querySelectorAll('.month-btn').forEach(btn => btn.classList.remove('active'));
            if (!drillFilter) document.getElementById('drillIndicator').style.display = 'none';
            applyFilters();
        }}

        function initCharts(data) {{
            const filteredData = filterTransactions(data);
            
            // Merchant aggregation
            const merchantTotals = {{}};
            filteredData.forEach(t => {{ if (t.debit > 0) merchantTotals[t.merchant] = (merchantTotals[t.merchant] || 0) + t.debit; }});
            const sortedMerchants = Object.entries(merchantTotals).sort((a,b) => b[1]-a[1]).slice(0, 10);
            
            // Category aggregation
            const categoryTotals = {{}};
            filteredData.forEach(t => {{ if (t.debit > 0) categoryTotals[t.category] = (categoryTotals[t.category] || 0) + t.debit; }});
            const sortedCategories = Object.entries(categoryTotals).sort((a,b) => b[1]-a[1]);

            // Daily distribution
            const dailyTotals = {{}};
            filteredData.forEach(t => {{ if (t.debit > 0) dailyTotals[t.date] = (dailyTotals[t.date] || 0) + t.debit; }});
            const dailyLabels = Object.keys(dailyTotals).sort();
            const dailyValues = dailyLabels.map(d => dailyTotals[d]);

            if (merchantChart) merchantChart.destroy();
            if (categoryChart) categoryChart.destroy();
            if (dailyChart) dailyChart.destroy();

            const chartConfig = {{
                plugins: {{ legend: {{ display: false }} }},
                maintainAspectRatio: false,
                responsive: true
            }};

            // Render Merchant Chart
            merchantChart = new Chart(document.getElementById('merchantChart').getContext('2d'), {{
                type: 'doughnut',
                data: {{
                    labels: sortedMerchants.map(m => m[0]),
                    datasets: [{{
                        data: sortedMerchants.map(m => m[1]),
                        backgroundColor: ['#4f46e5', '#818cf8', '#c7d2fe', '#a855f7', '#d8b4fe', '#f43f5e', '#fda4af', '#10b981', '#34d399', '#cbd5e1']
                    }}]
                }},
                options: {{
                    ...chartConfig,
                    onClick: (e, el) => {{
                        if(el.length > 0) {{
                            const idx = el[0].index;
                            drillByMerchant(merchantChart.data.labels[idx]);
                        }}
                    }}
                }}
            }});

            // Render Category Chart
            categoryChart = new Chart(document.getElementById('categoryChart').getContext('2d'), {{
                type: 'polarArea',
                data: {{
                    labels: sortedCategories.map(c => c[0]),
                    datasets: [{{
                        data: sortedCategories.map(c => c[1]),
                        backgroundColor: ['#6366f1', '#a855f7', '#ec4899', '#f43f5e', '#10b981', '#f59e0b', '#64748b']
                    }}]
                }},
                options: {{
                    ...chartConfig,
                    onClick: (e, el) => {{
                        if(el.length > 0) {{
                            const idx = el[0].index;
                            drillByCategory(categoryChart.data.labels[idx]);
                        }}
                    }}
                }}
            }});

            // Render Daily Timeline Line/Bar Chart
            dailyChart = new Chart(document.getElementById('dailyChart').getContext('2d'), {{
                type: 'bar',
                data: {{
                    labels: dailyLabels,
                    datasets: [{{
                        data: dailyValues,
                        backgroundColor: 'rgba(79, 70, 229, 0.75)',
                        borderRadius: 4
                    }}]
                }},
                options: {{
                    ...chartConfig,
                    scales: {{ x: {{ grid: {{ display: false }} }}, y: {{ beginAtZero: true }} }},
                    onClick: (e, el) => {{
                        if(el.length > 0) {{
                            const idx = el[0].index;
                            drillByDate(dailyChart.data.labels[idx]);
                        }}
                    }}
                }}
            }});
        }}

        function drillByMerchant(merchant) {{
            drillFilter = {{type: 'merchant', value: merchant}};
            document.getElementById('drillFilterText').textContent = 'Entity counterparty (' + merchant + ')';
            document.getElementById('drillIndicator').style.display = 'flex';
            applyFilters();
            showToast('Scope pinned to merchant matrix');
        }}

        function drillByCategory(cat) {{
            drillFilter = {{type: 'category', value: cat}};
            document.getElementById('drillFilterText').textContent = 'Operational Category (' + cat + ')';
            document.getElementById('drillIndicator').style.display = 'flex';
            applyFilters();
            showToast('Scope pinned to isolated accounting silo');
        }}

        function drillByDate(dt) {{
            drillFilter = {{type: 'date', value: dt}};
            document.getElementById('drillFilterText').textContent = 'Identified Ledger Date Target (' + dt + ')';
            document.getElementById('drillIndicator').style.display = 'flex';
            applyFilters();
            showToast('Scope focused onto specific timestamp anchor');
        }}

        function clearDrill() {{
            drillFilter = null;
            if(!monthFilter) document.getElementById('drillIndicator').style.display = 'none';
            applyFilters();
        }}

        function copyColumn(columnName) {{
            const filtered = filterTransactions(allTransactions);
            let data = filtered.map(t => {{
                if (columnName === 'debit' || columnName === 'credit' || columnName === 'balance') {{
                    return t[columnName] ? t[columnName].toFixed(2) : '0.00';
                }}
                return t[columnName];
            }});
            navigator.clipboard.writeText(data.join('\\n')).then(() => {{
                showToast('Copied array structural column records into system layout.');
            }});
        }}

        function copyAllData() {{
            const filtered = filterTransactions(allTransactions);
            if(filtered.length === 0) return;
            let output = 'Date\\tMerchant\\tCategory\\tDebit\\tCredit\\tBalance\\n';
            filtered.forEach(t => {{
                output += `${{t.date}}\\t${{t.merchant}}\\t${{t.category}}\\t${{t.debit}}\\t${{t.credit}}\\t${{t.balance}}\\n`;
            }});
            navigator.clipboard.writeText(output).then(() => showToast('Full filtered data workspace compiled to clipboard buffer.'));
        }}

        function renderTable(data) {{
            const tbody = document.getElementById('transactionBody');
            if (data.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:40px; color:var(--text-muted)">Empty metrics matched filter arguments</td></tr>';
                return;
            }}
            
            tbody.innerHTML = data.slice(0, 150).map(t => `
                <tr>
                    <td style="font-weight:500;">${{t.date_display}}</td>
                    <td style="font-weight:700; color:var(--text-main);">${{t.merchant}}</td>
                    <td><span class="badge badge-cat">${{t.category}}</span></td>
                    <td style="font-weight:700;" class="${{t.debit > 0 ? 'badge-debit' : ''}}">${{t.debit > 0 ? '-$' + t.debit.toFixed(2) : '—'}}</td>
                    <td style="font-weight:700;" class="${{t.credit > 0 ? 'badge-credit' : ''}}">${{t.credit > 0 ? '+$' + t.credit.toFixed(2) : '—'}}</td>
                    <td style="font-weight:600; color:#475569;">${{t.balance !== null ? '$' + t.balance.toFixed(2) : '—'}}</td>
                    <td><span class="badge badge-src">${{t.source}}</span></td>
                </tr>
            `).join('');
        }}
        function sortTable(column) {{
            if (sortColumn === column) {{
                sortAscending = !sortAscending; // Toggle direction if same column
            }} else {{
                sortColumn = column;
                sortAscending = true; // Default to ascending for new columns
            }}
            applyFilters(); // Re-render with new sort
        }}

        function applyFilters() {{
            const filtered = filterTransactions(allTransactions);
            
            // Sort the filtered data before rendering
            filtered.sort((a, b) => {{
                let valA = a[sortColumn];
                let valB = b[sortColumn];
                
                // Handle nulls (e.g., if balance is missing)
                if (valA === null || valA === undefined) valA = -Infinity;
                if (valB === null || valB === undefined) valB = -Infinity;

                // Handle strings vs numbers
                if (typeof valA === 'string') {{
                    valA = valA.toLowerCase();
                    valB = valB.toLowerCase();
                }}

                if (valA < valB) return sortAscending ? -1 : 1;
                if (valA > valB) return sortAscending ? 1 : -1;
                return 0;
            }});

            // Calculate and update stats
            let totalDebits = 0, totalCredits = 0;
            filtered.forEach(t => {{ totalDebits += t.debit; totalCredits += t.credit; }});
            
            document.getElementById('statSpending').textContent = '$' + totalDebits.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            document.getElementById('statCredits').textContent = '$' + totalCredits.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            
            const netDelta = totalCredits - totalDebits;
            const netEl = document.getElementById('statNetChange');
            netEl.textContent = (netDelta >= 0 ? '+' : '') + '$' + netDelta.toLocaleString(undefined, {{minimumFractionDigits: 2, maximumFractionDigits: 2}});
            netEl.className = 'value ' + (netDelta < 0 ? 'negative' : 'positive');
            
            document.getElementById('statCount').textContent = filtered.length;
            
            // Render table and charts
            renderTable(filtered);
            initCharts(filtered);

            // 3c: Update sort arrows in headers
            document.querySelectorAll('.sort-arrow').forEach(span => span.textContent = '');
            document.querySelectorAll('th[onclick]').forEach(th => {{
                const match = th.getAttribute('onclick').match(/'([^']+)'/);
                if (match && match[1] === sortColumn) {{
                    th.querySelector('.sort-arrow').textContent = sortAscending ? '▲' : '▼';
                }}
            }});
        }}

        function resetFilters() {{
            drillFilter = null;
            monthFilter = null;
            document.getElementById('startDate').value = minDateInitial;
            document.getElementById('endDate').value = maxDateInitial;
            document.getElementById('merchantFilter').value = '';
            document.getElementById('categoryFilter').value = '';
            document.getElementById('typeFilter').value = 'all';
            document.getElementById('searchFilter').value = '';
            document.getElementById('drillIndicator').style.display = 'none';
            document.querySelectorAll('.month-btn').forEach(btn => btn.classList.remove('active'));
            applyFilters();
            showToast('Ecosystem telemetry parameters zeroed out');
        }}

        document.addEventListener('DOMContentLoaded', applyFilters);
    </script>
</body>
</html>'''
        return html

def main():
    if len(sys.argv) < 2:
        print("Usage: python interactive_report.py <csv_file_paths>")
        sys.exit(1)
    
    args = sys.argv[1:]
    mapping_file = None
    if '--mapping' in args:
        idx = args.index('--mapping')
        if idx + 1 < len(args):
            mapping_file = args[idx + 1]
            del args[idx:idx + 2]
            
    all_files = []
    for pattern in args:
        if '*' in pattern:
            all_files.extend(glob.glob(pattern))
        else:
            all_files.append(pattern)
            
    all_files = sorted(list(set(all_files)))
    report = InteractiveFinancialReport(all_files, mapping_file=mapping_file)
    if report.load_data():
        report.generate_html()

if __name__ == "__main__":
    main()