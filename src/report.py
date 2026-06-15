"""
src/report.py — Generate beautiful HTML daily sales report with charts
"""

import logging
import base64
import io
import pandas as pd
# pyrefly: ignore [missing-import]
import matplotlib
# pyrefly: ignore [missing-import]
import matplotlib.pyplot as plt
# pyrefly: ignore [missing-import]
import matplotlib.ticker as mticker
from datetime import datetime, date
from pathlib import Path
# pyrefly: ignore [missing-import]
from sqlalchemy.engine import Engine
# pyrefly: ignore [missing-import]
from sqlalchemy import text
# pyrefly: ignore [missing-import]
from jinja2 import Template

matplotlib.use("Agg")  # Non-interactive backend

logger = logging.getLogger(__name__)

# ─── Color Palette ────────────────────────────────────────────────────────────
COLORS = {
    "primary": "#6C63FF",
    "secondary": "#FF6584",
    "accent": "#43CBFF",
    "success": "#00C49A",
    "warning": "#FFB347",
    "dark": "#1A1A2E",
    "gray": "#4A5568",
    "light": "#F7FAFC",
}

CHART_PALETTE = [
    "#6C63FF", "#FF6584", "#43CBFF", "#00C49A",
    "#FFB347", "#A78BFA", "#F472B6", "#34D399"
]


def _fig_to_base64(fig) -> str:
    """Convert a matplotlib figure to base64 string for embedding in HTML."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=COLORS["dark"], edgecolor="none")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return img_b64


def _set_dark_style(ax, fig):
    """Apply dark theme to matplotlib axes."""
    fig.patch.set_facecolor(COLORS["dark"])
    ax.set_facecolor("#16213E")
    ax.tick_params(colors="#CBD5E0", labelsize=9)
    ax.xaxis.label.set_color("#CBD5E0")
    ax.yaxis.label.set_color("#CBD5E0")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#2D3748")
    ax.grid(axis="y", color="#2D3748", linestyle="--", linewidth=0.5, alpha=0.7)


class ReportGenerator:
    """Pulls data from the DB and renders a complete HTML report."""

    def __init__(self, engine: Engine, reports_dir: Path):
        self.engine = engine
        self.reports_dir = reports_dir

    # ─── Data Fetchers ────────────────────────────────────────────────────────

    def _query(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def get_summary_stats(self) -> dict:
        """Top-level KPIs for the report header."""
        sql = """
            SELECT
                SUM(total_net_revenue)          AS total_revenue,
                SUM(total_orders)               AS total_orders,
                SUM(total_units_sold)           AS total_units,
                AVG(avg_order_value)            AS avg_order_value,
                SUM(total_discount_amount)      AS total_discounts,
                COUNT(DISTINCT report_date)     AS days_in_report
            FROM daily_sales_summary
        """
        df = self._query(sql)
        row = df.iloc[0]
        return {
            "total_revenue": f"₹{row['total_revenue']:,.0f}" if row['total_revenue'] else "₹0",
            "total_orders": f"{int(row['total_orders'] or 0):,}",
            "total_units": f"{int(row['total_units'] or 0):,}",
            "avg_order_value": f"₹{row['avg_order_value']:,.0f}" if row['avg_order_value'] else "₹0",
            "total_discounts": f"₹{row['total_discounts']:,.0f}" if row['total_discounts'] else "₹0",
            "days_in_report": int(row["days_in_report"] or 0),
        }

    def get_recent_daily(self, days: int = 30) -> pd.DataFrame:
        sql = f"""
            SELECT report_date, total_net_revenue, total_orders, avg_order_value
            FROM daily_sales_summary
            ORDER BY report_date DESC
            LIMIT {days}
        """
        df = self._query(sql)
        return df.sort_values("report_date")

    def get_revenue_by_category(self) -> pd.DataFrame:
        sql = """
            SELECT p.category, ROUND(SUM(o.net_revenue)::numeric, 2) AS revenue
            FROM fact_orders o
            JOIN dim_products p ON o.product_id = p.product_id
            WHERE o.status = 'completed'
            GROUP BY p.category
            ORDER BY revenue DESC
            LIMIT 8
        """
        return self._query(sql)

    def get_revenue_by_channel(self) -> pd.DataFrame:
        sql = """
            SELECT channel, ROUND(SUM(net_revenue)::numeric, 2) AS revenue,
                   COUNT(*) AS orders
            FROM fact_orders
            WHERE status = 'completed'
            GROUP BY channel
            ORDER BY revenue DESC
        """
        return self._query(sql)

    def get_top_products(self, n: int = 10) -> pd.DataFrame:
        sql = f"""
            SELECT p.name, p.brand, p.category,
                   SUM(o.quantity) AS units_sold,
                   ROUND(SUM(o.net_revenue)::numeric, 2) AS revenue
            FROM fact_orders o
            JOIN dim_products p ON o.product_id = p.product_id
            WHERE o.status = 'completed'
            GROUP BY p.name, p.brand, p.category
            ORDER BY revenue DESC
            LIMIT {n}
        """
        return self._query(sql)

    def get_revenue_by_country(self) -> pd.DataFrame:
        sql = """
            SELECT c.country, ROUND(SUM(o.net_revenue)::numeric, 2) AS revenue,
                   COUNT(DISTINCT o.order_id) AS orders
            FROM fact_orders o
            JOIN dim_customers c ON o.customer_id = c.customer_id
            WHERE o.status = 'completed'
            GROUP BY c.country
            ORDER BY revenue DESC
            LIMIT 8
        """
        return self._query(sql)

    def get_order_status_breakdown(self) -> pd.DataFrame:
        sql = """
            SELECT status, COUNT(*) AS count
            FROM fact_orders
            GROUP BY status
            ORDER BY count DESC
        """
        return self._query(sql)

    def get_return_reasons(self) -> pd.DataFrame:
        sql = """
            SELECT reason, COUNT(*) AS count,
                   ROUND(SUM(refund_amount)::numeric, 2) AS total_refund
            FROM fact_returns
            GROUP BY reason
            ORDER BY count DESC
        """
        return self._query(sql)

    # ─── Chart Generators ─────────────────────────────────────────────────────

    def chart_revenue_trend(self, df: pd.DataFrame) -> str:
        fig, ax = plt.subplots(figsize=(10, 3.5))
        _set_dark_style(ax, fig)
        dates = pd.to_datetime(df["report_date"])
        revenue = df["total_net_revenue"].astype(float)
        ax.fill_between(dates, revenue, alpha=0.15, color=COLORS["primary"])
        ax.plot(dates, revenue, color=COLORS["primary"], linewidth=2.5, marker="o",
                markersize=3, markerfacecolor=COLORS["accent"])
        ax.set_title("Daily Net Revenue (Last 30 Days)", fontsize=12, fontweight="bold", pad=12)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x/1000:.0f}K"))
        ax.set_xlabel("")
        plt.xticks(rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return _fig_to_base64(fig)

    def chart_category_revenue(self, df: pd.DataFrame) -> str:
        fig, ax = plt.subplots(figsize=(6, 4))
        _set_dark_style(ax, fig)
        bars = ax.barh(df["category"], df["revenue"].astype(float),
                       color=CHART_PALETTE[:len(df)], edgecolor="none", height=0.6)
        ax.set_title("Revenue by Category", fontsize=11, fontweight="bold", pad=10)
        ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x/1000:.0f}K"))
        ax.invert_yaxis()
        for bar, val in zip(bars, df["revenue"].astype(float)):
            ax.text(bar.get_width() + 500, bar.get_y() + bar.get_height() / 2,
                    f"₹{val/1000:.1f}K", va="center", color="#CBD5E0", fontsize=8)
        plt.tight_layout()
        return _fig_to_base64(fig)

    def chart_channel_pie(self, df: pd.DataFrame) -> str:
        fig, ax = plt.subplots(figsize=(5, 4))
        fig.patch.set_facecolor(COLORS["dark"])
        ax.set_facecolor(COLORS["dark"])
        wedges, texts, autotexts = ax.pie(
            df["revenue"].astype(float),
            labels=df["channel"],
            autopct="%1.1f%%",
            colors=CHART_PALETTE[:len(df)],
            startangle=140,
            wedgeprops={"edgecolor": COLORS["dark"], "linewidth": 2},
        )
        for text in texts:
            text.set_color("#CBD5E0")
            text.set_fontsize(9)
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(8)
            autotext.set_fontweight("bold")
        ax.set_title("Revenue by Channel", fontsize=11, fontweight="bold", color="white", pad=10)
        plt.tight_layout()
        return _fig_to_base64(fig)

    def chart_daily_orders(self, df: pd.DataFrame) -> str:
        fig, ax = plt.subplots(figsize=(10, 2.8))
        _set_dark_style(ax, fig)
        dates = pd.to_datetime(df["report_date"])
        orders = df["total_orders"].astype(int)
        ax.bar(dates, orders, color=COLORS["success"], alpha=0.85, edgecolor="none", width=0.8)
        ax.set_title("Daily Orders Volume", fontsize=11, fontweight="bold", pad=10)
        plt.xticks(rotation=30, ha="right", fontsize=7)
        plt.tight_layout()
        return _fig_to_base64(fig)

    def chart_country_revenue(self, df: pd.DataFrame) -> str:
        fig, ax = plt.subplots(figsize=(6, 3.5))
        _set_dark_style(ax, fig)
        bars = ax.bar(df["country"], df["revenue"].astype(float),
                      color=CHART_PALETTE[:len(df)], edgecolor="none")
        ax.set_title("Revenue by Country", fontsize=11, fontweight="bold", pad=10)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x/1000:.0f}K"))
        plt.xticks(rotation=30, ha="right", fontsize=8)
        plt.tight_layout()
        return _fig_to_base64(fig)

    # ─── HTML Template ────────────────────────────────────────────────────────

    def _html_template(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
    <title>E-Commerce Daily Sales Report — {{ report_date }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --bg: #0F0F1A;
            --surface: #1A1A2E;
            --card: #16213E;
            --border: #2D3748;
            --primary: #6C63FF;
            --secondary: #FF6584;
            --accent: #43CBFF;
            --success: #00C49A;
            --warning: #FFB347;
            --text: #E2E8F0;
            --muted: #718096;
            --font: 'Inter', sans-serif;
        }
        body { background: var(--bg); color: var(--text); font-family: var(--font); line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }

        /* Header */
        .header {
            background: linear-gradient(135deg, #0F0F1A 0%, #1A1A2E 50%, #16213E 100%);
            border-bottom: 1px solid var(--border);
            padding: 40px 0 32px;
            position: relative;
            overflow: hidden;
        }
        .header::before {
            content: '';
            position: absolute; inset: 0;
            background: radial-gradient(ellipse at 70% 50%, rgba(108,99,255,0.15) 0%, transparent 70%);
        }
        .header-inner { position: relative; z-index: 1; }
        .brand { font-size: 13px; font-weight: 600; letter-spacing: 3px; text-transform: uppercase;
                 color: var(--primary); margin-bottom: 8px; }
        .title { font-size: 32px; font-weight: 700; color: white; margin-bottom: 6px; }
        .subtitle { font-size: 14px; color: var(--muted); }
        .badge {
            display: inline-block; padding: 4px 12px; border-radius: 20px;
            font-size: 11px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase;
            background: rgba(108,99,255,0.2); color: var(--primary); border: 1px solid rgba(108,99,255,0.3);
            margin-top: 12px;
        }

        /* KPI Cards */
        .section { padding: 32px 0; }
        .section-title {
            font-size: 18px; font-weight: 600; color: white;
            margin-bottom: 20px; display: flex; align-items: center; gap: 8px;
        }
        .section-title::after {
            content: ''; flex: 1; height: 1px; background: var(--border);
        }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
        .kpi-card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
        }
        .kpi-card:hover { transform: translateY(-2px); border-color: var(--primary); }
        .kpi-card::before {
            content: '';
            position: absolute; top: 0; left: 0; right: 0; height: 3px;
            background: linear-gradient(90deg, var(--kpi-color, var(--primary)), transparent);
        }
        .kpi-label { font-size: 11px; font-weight: 600; letter-spacing: 1px;
                     text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
        .kpi-value { font-size: 26px; font-weight: 700; color: white; }
        .kpi-icon { position: absolute; top: 16px; right: 16px; font-size: 24px; opacity: 0.3; }

        /* Charts */
        .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .chart-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 16px; padding: 20px; overflow: hidden;
        }
        .chart-card.full { grid-column: 1 / -1; }
        .chart-card img { width: 100%; height: auto; border-radius: 8px; display: block; }

        /* Tables */
        .table-card {
            background: var(--card); border: 1px solid var(--border);
            border-radius: 16px; overflow: hidden;
        }
        .table-card table { width: 100%; border-collapse: collapse; }
        .table-card th {
            background: var(--surface); padding: 12px 16px;
            text-align: left; font-size: 11px; font-weight: 600;
            letter-spacing: 1px; text-transform: uppercase; color: var(--muted);
            border-bottom: 1px solid var(--border);
        }
        .table-card td {
            padding: 12px 16px; font-size: 13px; color: var(--text);
            border-bottom: 1px solid rgba(45,55,72,0.5);
        }
        .table-card tr:last-child td { border-bottom: none; }
        .table-card tr:hover td { background: rgba(108,99,255,0.05); }
        .rank { font-weight: 700; color: var(--primary); }
        .tag {
            display: inline-block; padding: 2px 8px; border-radius: 20px;
            font-size: 10px; font-weight: 600; text-transform: uppercase;
        }
        .tag-completed { background: rgba(0,196,154,0.15); color: var(--success); }
        .tag-pending    { background: rgba(255,179,71,0.15); color: var(--warning); }
        .tag-cancelled  { background: rgba(255,101,132,0.15); color: var(--secondary); }
        .tag-refunded   { background: rgba(67,203,255,0.15); color: var(--accent); }

        /* Footer */
        .footer {
            border-top: 1px solid var(--border); padding: 24px 0;
            text-align: center; color: var(--muted); font-size: 12px;
        }
        .footer span { color: var(--primary); }
    </style>
</head>
<body>

<div class="header">
  <div class="container">
    <div class="header-inner">
      <div class="title">Daily Sales Report</div>
      <div class="subtitle">E-Commerce Data Pipeline · Automated Intelligence Report</div>
      <div class="badge">📅 Generated: {{ report_date }}</div>
    </div>
  </div>
</div>

<div class="container">

  <!-- KPI Section -->
  <div class="section">
    <div class="section-title">📊 Key Performance Indicators</div>
    <div class="kpi-grid">
      <div class="kpi-card" style="--kpi-color: #6C63FF">
        <div class="kpi-icon">💰</div>
        <div class="kpi-label">Total Net Revenue</div>
        <div class="kpi-value">{{ stats.total_revenue }}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: #00C49A">
        <div class="kpi-icon">🛒</div>
        <div class="kpi-label">Total Orders</div>
        <div class="kpi-value">{{ stats.total_orders }}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: #43CBFF">
        <div class="kpi-icon">📦</div>
        <div class="kpi-label">Units Sold</div>
        <div class="kpi-value">{{ stats.total_units }}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: #FFB347">
        <div class="kpi-icon">🎯</div>
        <div class="kpi-label">Avg Order Value</div>
        <div class="kpi-value">{{ stats.avg_order_value }}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: #FF6584">
        <div class="kpi-icon">🏷️</div>
        <div class="kpi-label">Total Discounts</div>
        <div class="kpi-value">{{ stats.total_discounts }}</div>
      </div>
      <div class="kpi-card" style="--kpi-color: #A78BFA">
        <div class="kpi-icon">📅</div>
        <div class="kpi-label">Days Tracked</div>
        <div class="kpi-value">{{ stats.days_in_report }}</div>
      </div>
    </div>
  </div>

  <!-- Revenue Trend -->
  <div class="section">
    <div class="section-title">📈 Revenue & Orders Trend</div>
    <div class="charts-grid">
      <div class="chart-card full">
        <img src="data:image/png;base64,{{ chart_trend }}" alt="Revenue Trend"/>
      </div>
      <div class="chart-card full">
        <img src="data:image/png;base64,{{ chart_orders }}" alt="Daily Orders"/>
      </div>
    </div>
  </div>

  <!-- Category & Channel -->
  <div class="section">
    <div class="section-title">🏷️ Category & Channel Breakdown</div>
    <div class="charts-grid">
      <div class="chart-card">
        <img src="data:image/png;base64,{{ chart_category }}" alt="Category Revenue"/>
      </div>
      <div class="chart-card">
        <img src="data:image/png;base64,{{ chart_channel }}" alt="Channel Revenue"/>
      </div>
      <div class="chart-card full">
        <img src="data:image/png;base64,{{ chart_country }}" alt="Country Revenue"/>
      </div>
    </div>
  </div>

  <!-- Top Products Table -->
  <div class="section">
    <div class="section-title">🏆 Top 10 Products by Revenue</div>
    <div class="table-card">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Product Name</th>
            <th>Brand</th>
            <th>Category</th>
            <th>Units Sold</th>
            <th>Revenue</th>
          </tr>
        </thead>
        <tbody>
          {% for row in top_products %}
          <tr>
            <td class="rank">{{ loop.index }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.brand }}</td>
            <td>{{ row.category }}</td>
            <td>{{ row.units_sold }}</td>
            <td><strong>₹{{ "{:,.0f}".format(row.revenue) }}</strong></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Order Status & Returns -->
  <div class="section">
    <div class="section-title">📋 Order Status & Returns Analysis</div>
    <div class="charts-grid">
      <div class="table-card">
        <table>
          <thead>
            <tr><th>Status</th><th>Orders</th></tr>
          </thead>
          <tbody>
            {% for row in order_status %}
            <tr>
              <td><span class="tag tag-{{ row.status }}">{{ row.status }}</span></td>
              <td>{{ row.count }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr><th>Return Reason</th><th>Count</th><th>Refund Total</th></tr>
          </thead>
          <tbody>
            {% for row in return_reasons %}
            <tr>
              <td>{{ row.reason }}</td>
              <td>{{ row.count }}</td>
              <td>₹{{ "{:,.0f}".format(row.total_refund) }}</td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  <div class="container">
    Generated by <span>E-Commerce Data Pipeline</span> ·
    {{ report_date }} ·
    Powered by Python, Pandas &amp; PostgreSQL
  </div>
</div>

</body>
</html>"""

    # ─── Main Report Entry Point ──────────────────────────────────────────────

    def generate(self) -> Path:
        """Generate the full HTML report and save it to disk."""
        logger.info("=" * 60)
        logger.info("📄  REPORT PHASE — Generating Daily Sales Report")
        logger.info("=" * 60)

        stats = self.get_summary_stats()
        daily_df = self.get_recent_daily(30)
        category_df = self.get_revenue_by_category()
        channel_df = self.get_revenue_by_channel()
        products_df = self.get_top_products(10)
        country_df = self.get_revenue_by_country()
        status_df = self.get_order_status_breakdown()
        returns_df = self.get_return_reasons()

        logger.info("  🎨 Rendering charts...")
        chart_trend = self.chart_revenue_trend(daily_df) if not daily_df.empty else ""
        chart_category = self.chart_category_revenue(category_df) if not category_df.empty else ""
        chart_channel = self.chart_channel_pie(channel_df) if not channel_df.empty else ""
        chart_orders = self.chart_daily_orders(daily_df) if not daily_df.empty else ""
        chart_country = self.chart_country_revenue(country_df) if not country_df.empty else ""

        report_date = datetime.now().strftime("%Y-%m-%d %H:%M")
        template = Template(self._html_template())
        html = template.render(
            report_date=report_date,
            stats=stats,
            chart_trend=chart_trend,
            chart_category=chart_category,
            chart_channel=chart_channel,
            chart_orders=chart_orders,
            chart_country=chart_country,
            top_products=products_df.to_dict("records"),
            order_status=status_df.to_dict("records"),
            return_reasons=returns_df.to_dict("records"),
        )

        filename = f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = self.reports_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Also save as "latest"
        latest_path = self.reports_dir / "latest_report.html"
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"  ✅ Report saved: {output_path}")
        logger.info(f"  🔗 Latest report: {latest_path}")
        return output_path
