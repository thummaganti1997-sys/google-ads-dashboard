import streamlit as st
import pandas as pd
from datetime import date, timedelta
from google.ads.googleads.client import GoogleAdsClient
from openai import OpenAI


# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="Google Ads AI Dashboard",
    layout="wide"
)

st.markdown("""
<style>

/* MAIN BACKGROUND */
.stApp {
    background: linear-gradient(
        135deg,
        #f8fbff 0%,
        #f4f7ff 50%,
        #faf7ff 100%
    );
}

/* MAIN TITLE */
h1 {
    color: #1e3a8a;
    font-weight: 800;
}

/* SECTION HEADINGS */
h2 {
    color: #312e81;
    font-weight: 700;
}

h3 {
    color: #4338ca;
}
/* PROFESSIONAL SECTION HEADINGS */
h2 {
    background: linear-gradient(
        90deg,
        rgba(79, 70, 229, 0.10),
        rgba(124, 58, 237, 0.04)
    );
    padding: 12px 16px;
    border-left: 5px solid #4f46e5;
    border-radius: 10px;
    margin-top: 20px;
}

/* METRIC CARDS */
[data-testid="stMetric"] {
    background: white;
    border-radius: 16px;
    padding: 18px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.06);
}
/* INDIVIDUAL KPI CARD COLORS */

div[data-testid="stMetric"]:nth-of-type(1) {
    border-top: 4px solid #2563eb;
}

div[data-testid="stMetric"]:nth-of-type(2) {
    border-top: 4px solid #16a34a;
}

div[data-testid="stMetric"]:nth-of-type(3) {
    border-top: 4px solid #f59e0b;
}

div[data-testid="stMetric"]:nth-of-type(4) {
    border-top: 4px solid #7c3aed;
}

div[data-testid="stMetric"]:nth-of-type(5) {
    border-top: 4px solid #0891b2;
}

div[data-testid="stMetric"]:nth-of-type(6) {
    border-top: 4px solid #ea580c;
}

div[data-testid="stMetric"]:nth-of-type(7) {
    border-top: 4px solid #dc2626;
}

div[data-testid="stMetric"]:nth-of-type(8) {
    border-top: 4px solid #0f766e;
}

/* METRIC LABEL */
[data-testid="stMetricLabel"] {
    color: #475569;
    font-weight: 600;
}

/* METRIC VALUE */
[data-testid="stMetricValue"] {
    color: #111827;
    font-weight: 800;
}

/* BUTTONS */
.stButton > button {
    background: linear-gradient(
        90deg,
        #4f46e5,
        #7c3aed
    );
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 22px;
    font-weight: 700;
}

.stButton > button:hover {
    background: linear-gradient(
        90deg,
        #4338ca,
        #6d28d9
    );
    color: white;
}

/* INPUT BOX */
.stTextInput input {
    border-radius: 10px;
    border: 1px solid #c7d2fe;
}

/* SELECT BOX */
[data-baseweb="select"] > div {
    border-radius: 10px;
}

/* DATAFRAME */
[data-testid="stDataFrame"] {
    background: white;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #e5e7eb;
}
/* PROFESSIONAL CHART CARDS */
[data-testid="stVegaLiteChart"],
[data-testid="stPlotlyChart"] {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 16px;
    padding: 12px;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
}

/* CHART SPACING */
[data-testid="stVegaLiteChart"],
[data-testid="stPlotlyChart"] {
    margin-top: 8px;
    margin-bottom: 18px;
}

/* ALERT BOXES */
[data-testid="stAlert"] {
    border-radius: 12px;
}
/* AI STYLE CARDS */
div[data-testid="stVerticalBlock"]:has(h2) {
    border-radius: 14px;
}

/* SPINNER */
[data-testid="stSpinner"] {
    background: #f5f3ff;
    border-radius: 12px;
    padding: 10px;
}

/* SUCCESS MESSAGES */
[data-testid="stAlert"] {
    box-shadow: 0 3px 10px rgba(79, 70, 229, 0.08);
}

/* BUTTON EFFECT */
.stButton > button {
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(79, 70, 229, 0.25);
}

/* DIVIDER */
hr {
    border: none;
    height: 1px;
    background: #dbeafe;
    margin-top: 28px;
    margin-bottom: 28px;
}

/* SIDEBAR */
[data-testid="stSidebar"] {
    background: linear-gradient(
        180deg,
        #172554,
        #312e81
    );
}

/* SIDEBAR TEXT */
[data-testid="stSidebar"] * {
    color: white;
}
/* DASHBOARD TOP BANNER */
.dashboard-banner {
    background: linear-gradient(
        90deg,
        #1e3a8a,
        #4f46e5,
        #7c3aed
    );
    padding: 24px 28px;
    border-radius: 18px;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(79, 70, 229, 0.20);
}

.dashboard-banner h1 {
    color: white !important;
    margin: 0;
    font-weight: 800;
}

.dashboard-banner p {
    color: #e0e7ff;
    margin-top: 7px;
    margin-bottom: 0;
    font-size: 16px;
}
/* SECTION SPACING */
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
}

/* CLEAN SECTION GAP */
h2 {
    margin-top: 30px !important;
    margin-bottom: 14px !important;
}

/* SUBHEADINGS */
h3 {
    margin-top: 18px !important;
    margin-bottom: 10px !important;
}

/* TABLE SPACING */
[data-testid="stDataFrame"] {
    margin-top: 8px;
    margin-bottom: 18px;
}
/* KPI CARD HOVER */
[data-testid="stMetric"] {
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.10);
}

/* KPI VALUE SIZE */
[data-testid="stMetricValue"] {
    font-size: 28px;
}

/* KPI LABEL SIZE */
[data-testid="stMetricLabel"] {
    font-size: 14px;
}
@media (max-width: 768px) {

    .block-container {
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
        padding-top: 1rem !important;
    }

    h1 {
        font-size: 1.8rem !important;
    }

    h2 {
        font-size: 1.45rem !important;
        line-height: 1.25 !important;
    }

    h3 {
        font-size: 1.15rem !important;
        line-height: 1.25 !important;
    }

    div[data-testid="stMetric"] {
        padding: 0.7rem !important;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
    }

    div[data-testid="stDataFrame"] {
        overflow-x: auto !important;
    }

    div.stButton > button {
        width: 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dashboard-banner">
    <h1>🤖 Google Ads AI Dashboard</h1>
    <p>Smart Performance • AI Insights • Budget Optimization</p>
</div>
""", unsafe_allow_html=True)

# ==================================================
# DATE RANGE
# ==================================================

date_options = [
    "Today",
    "Last 7 Days",
    "Last 30 Days",
    "Last 90 Days",
    "Last 6 Months",
    "Last 1 Year",
    "Custom Date Range"
]

# Default date range
if "date_option" not in st.session_state:
    st.session_state.date_option = "Today"

# AI requested date range varsa, apply it before creating widget
if "pending_ai_date_option" in st.session_state:
    pending_date = st.session_state.pending_ai_date_option

    if pending_date in date_options:
        st.session_state.date_option = pending_date

    del st.session_state.pending_ai_date_option

date_option = st.selectbox(
    "📅 Select Date Range",
    date_options,
    key="date_option"
)

today = date.today()

if date_option == "Today":
    date_filter_clause = "segments.date DURING TODAY"

elif date_option == "Last 7 Days":
    date_filter_clause = "segments.date DURING LAST_7_DAYS"

elif date_option == "Last 30 Days":
    date_filter_clause = "segments.date DURING LAST_30_DAYS"

elif date_option == "Last 90 Days":
    start_date = today - timedelta(days=89)

    date_filter_clause = (
        f"segments.date BETWEEN '{start_date:%Y-%m-%d}' "
        f"AND '{today:%Y-%m-%d}'"
    )

elif date_option == "Last 6 Months":
    start_date = today - timedelta(days=179)

    date_filter_clause = (
        f"segments.date BETWEEN '{start_date:%Y-%m-%d}' "
        f"AND '{today:%Y-%m-%d}'"
    )

elif date_option == "Last 1 Year":
    start_date = today - timedelta(days=364)

    date_filter_clause = (
        f"segments.date BETWEEN '{start_date:%Y-%m-%d}' "
        f"AND '{today:%Y-%m-%d}'"
    )

elif date_option == "Custom Date Range":
    custom_dates = st.date_input(
        "Select Start and End Date",
        value=(today - timedelta(days=30), today),
        max_value=today
    )

    if isinstance(custom_dates, (tuple, list)) and len(custom_dates) == 2:
        start_date, end_date = custom_dates

        if start_date > end_date:
            st.error("Start date cannot be after end date.")
            st.stop()

        date_filter_clause = (
            f"segments.date BETWEEN '{start_date:%Y-%m-%d}' "
            f"AND '{end_date:%Y-%m-%d}'"
        )

    else:
        st.warning("Please select both start and end dates.")
        st.stop()
# ==================================================
# GOOGLE ADS CONNECTION
# ==================================================

try:

    credentials = {
        "developer_token": st.secrets["google_ads"]["developer_token"],
        "client_id": st.secrets["google_ads"]["client_id"],
        "client_secret": st.secrets["google_ads"]["client_secret"],
        "refresh_token": st.secrets["google_ads"]["refresh_token"],
        "use_proto_plus": True,
    }

    customer_id = st.secrets["google_ads"]["customer_id"].replace("-", "")

    client = GoogleAdsClient.load_from_dict(credentials)

    ga_service = client.get_service("GoogleAdsService")

    openai_client = OpenAI(
        api_key=st.secrets["openai"]["api_key"]
    )


    # ==================================================
    # CAMPAIGN DATA
    # ==================================================

    campaign_query = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
       WHERE {date_filter_clause}
        
        ORDER BY metrics.cost_micros DESC
    """

    campaign_response = ga_service.search(
        customer_id=customer_id,
        query=campaign_query
    )

    campaign_data = []

    for row in campaign_response:

        impressions = row.metrics.impressions
        clicks = row.metrics.clicks
        cost = row.metrics.cost_micros / 1_000_000
        conversions = row.metrics.conversions

        ctr = (
            clicks / impressions * 100
            if impressions else 0
        )

        cpc = (
            cost / clicks
            if clicks else 0
        )

        cpa = (
            cost / conversions
            if conversions else 0
        )

        conversion_rate = (
            conversions / clicks * 100
            if clicks else 0
        )

        campaign_data.append({
            "Campaign": row.campaign.name,
            "Status": row.campaign.status.name,
            "Impressions": impressions,
            "Clicks": clicks,
            "Cost (₹)": round(cost, 2),
            "Conversions": round(conversions, 2),
            "CTR %": round(ctr, 2),
            "Avg CPC (₹)": round(cpc, 2),
            "CPA (₹)": round(cpa, 2),
            "Conversion Rate %": round(conversion_rate, 2)
        })


    # ==================================================
    # CHECK DATA
    # ==================================================

    if not campaign_data:

        st.warning(
            f"No campaign data found for {date_option}."
        )

    else:

        df = pd.DataFrame(campaign_data)


        # ==================================================
        # SUMMARY METRICS
        # ==================================================

        total_impressions = df["Impressions"].sum()
        total_clicks = df["Clicks"].sum()
        total_cost = df["Cost (₹)"].sum()
        total_conversions = df["Conversions"].sum()

        overall_ctr = (
            total_clicks / total_impressions * 100
            if total_impressions else 0
        )

        overall_cpc = (
            total_cost / total_clicks
            if total_clicks else 0
        )

        overall_cpa = (
            total_cost / total_conversions
            if total_conversions else 0
        )

        overall_conversion_rate = (
            total_conversions / total_clicks * 100
            if total_clicks else 0
        )


        # ==================================================
        # TOP METRICS
        # ==================================================

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Impressions",
            f"{total_impressions:,}"
        )

        col2.metric(
            "Clicks",
            f"{total_clicks:,}"
        )

        col3.metric(
            "Cost",
            f"₹{total_cost:,.2f}"
        )

        col4.metric(
            "Conversions",
            f"{total_conversions:.2f}"
        )


        col5, col6, col7, col8 = st.columns(4)

        col5.metric(
            "CTR",
            f"{overall_ctr:.2f}%"
        )

        col6.metric(
            "Avg CPC",
            f"₹{overall_cpc:.2f}"
        )

        col7.metric(
            "CPA",
            f"₹{overall_cpa:.2f}"
        )

        col8.metric(
            "Conversion Rate",
            f"{overall_conversion_rate:.2f}%"
        )

        st.divider()


        # ==================================================
        # CAMPAIGN FILTER
        # ==================================================

        st.header("🎯 Campaign Filter")

        campaign_list = [
            "All Campaigns"
        ] + list(df["Campaign"].unique())

        selected_campaign = st.selectbox(
            "Select Campaign",
            campaign_list
        )

        if selected_campaign == "All Campaigns":

            filtered_df = df.copy()

        else:

            filtered_df = df[
                df["Campaign"] == selected_campaign
            ].copy()


                # ==================================================
        # CAMPAIGN PERFORMANCE
        # ==================================================

        st.header("📊 Campaign Performance")

        st.dataframe(
            filtered_df,
            width="stretch"
        )

        st.divider()


        # ==================================================
        # CAMPAIGN COMPARISON
        # ==================================================

        st.header("📈 Campaign Comparison")

        st.subheader("Conversions by Campaign")

        conversion_chart = filtered_df[
            ["Campaign", "Conversions"]
        ].set_index("Campaign")

        st.bar_chart(
            conversion_chart,
            width="stretch"
        )

        # ==================================================
        # SEARCH TERMS ANALYSIS
        # ==================================================

        search_query = f"""
            SELECT
                search_term_view.search_term,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM search_term_view
            WHERE {date_filter_clause}
            ORDER BY metrics.cost_micros DESC
            LIMIT 100
        """

        search_response = ga_service.search(
            customer_id=customer_id,
            query=search_query
        )

        search_data = []

        for row in search_response:
            search_impressions = int(row.metrics.impressions or 0)
            search_clicks = int(row.metrics.clicks or 0)
            search_cost = float(row.metrics.cost_micros or 0) / 1_000_000
            search_conversions = float(row.metrics.conversions or 0)

            search_ctr = (
                search_clicks / search_impressions * 100
                if search_impressions > 0
                else 0
            )

            search_cpc = (
                search_cost / search_clicks
                if search_clicks > 0
                else 0
            )

            search_cpa = (
                search_cost / search_conversions
                if search_conversions > 0
                else 0
            )

            search_data.append({
                "Search Term": row.search_term_view.search_term,
                "Campaign": row.campaign.name,
                "Impressions": search_impressions,
                "Clicks": search_clicks,
                "Cost (₹)": round(search_cost, 2),
                "Conversions": round(search_conversions, 2),
                "CTR %": round(search_ctr, 2),
                "Avg CPC (₹)": round(search_cpc, 2),
                "CPA (₹)": round(search_cpa, 2)
            })

        search_df = pd.DataFrame(
            search_data,
            columns=[
                "Search Term",
                "Campaign",
                "Impressions",
                "Clicks",
                "Cost (₹)",
                "Conversions",
                "CTR %",
                "Avg CPC (₹)",
                "CPA (₹)"
            ]
        )

        st.divider()
        st.header("🔍 Search Terms Analysis")

        if not search_df.empty:
            st.dataframe(
                search_df,
                width="stretch",
                hide_index=True
            )
        else:
            st.info(
                "No search term data available for the selected date range."
            )

        # ==================================================
        # DAILY PERFORMANCE
        # ==================================================

        st.divider()
        st.header("📅 Daily Performance")

        daily_query = f"""
            SELECT
                segments.date,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM customer
            WHERE {date_filter_clause}
            ORDER BY segments.date
        """

        daily_response = ga_service.search(
            customer_id=customer_id,
            query=daily_query
        )

        daily_data = []

        for row in daily_response:
            daily_impressions = int(row.metrics.impressions or 0)
            daily_clicks = int(row.metrics.clicks or 0)
            daily_cost = float(row.metrics.cost_micros or 0) / 1_000_000
            daily_conversions = float(row.metrics.conversions or 0)

            daily_ctr = (
                daily_clicks / daily_impressions * 100
                if daily_impressions > 0
                else 0
            )

            daily_cpc = (
                daily_cost / daily_clicks
                if daily_clicks > 0
                else 0
            )

            daily_cpa = (
                daily_cost / daily_conversions
                if daily_conversions > 0
                else 0
            )

            daily_data.append({
                "Date": str(row.segments.date),
                "Impressions": daily_impressions,
                "Clicks": daily_clicks,
                "Cost": round(daily_cost, 2),
                "Conversions": round(daily_conversions, 2),
                "CTR": round(daily_ctr, 2),
                "CPC": round(daily_cpc, 2),
                "CPA": round(daily_cpa, 2)
            })

        daily_df = pd.DataFrame(
            daily_data,
            columns=[
                "Date",
                "Impressions",
                "Clicks",
                "Cost",
                "Conversions",
                "CTR",
                "CPC",
                "CPA"
            ]
        )

        if not daily_df.empty:
            daily_df["Date"] = pd.to_datetime(
                daily_df["Date"],
                errors="coerce"
            )

            daily_df = (
                daily_df
                .dropna(subset=["Date"])
                .sort_values("Date")
                .set_index("Date")
            )

            st.subheader("Daily Performance Trend")

            st.line_chart(
                daily_df[["Clicks", "Conversions"]],
                width="stretch"
            )

            st.subheader("Daily Performance Table")

            st.dataframe(
                daily_df.reset_index(),
                width="stretch",
                hide_index=True
            )

        else:
            st.info(
                "No daily performance data available for the selected date range."
            )

        # ==================================================
        # POTENTIAL WASTE SPEND
        # ==================================================

        st.divider()

        st.header("💸 Potential Waste Spend")

        if not search_df.empty:

            waste_df = search_df[
                (search_df["Cost (₹)"] > 0)
                &
                (search_df["Conversions"] == 0)
            ].copy()

            if not waste_df.empty:

                waste_df = waste_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

                st.warning(
                    "These search terms have spend but 0 conversions."
                )

                st.dataframe(
                    waste_df,
                    width="stretch"
                )

            else:

                st.success(
                    "No major waste spend found."
                )

        else:

            st.info(
                "No search term data available."
            )

        # ==================================================
        # PERFORMANCE INSIGHTS
        # ==================================================

        st.divider()

        st.header("🏆 Performance Insights")

        if not filtered_df.empty:

            insights_df = filtered_df.copy()

            # Calculate CTR
            insights_df["CTR (%)"] = (
                insights_df["Clicks"]
                / insights_df["Impressions"].replace(0, 1)
                * 100
            )

            # Calculate CPA
            insights_df["CPA (₹)"] = insights_df.apply(
                lambda row:
                row["Cost (₹)"] / row["Conversions"]
                if row["Conversions"] > 0 else 0,
                axis=1
            )

            best_campaign = insights_df.loc[
                insights_df["Conversions"].idxmax()
            ]

            highest_spend = insights_df.loc[
                insights_df["Cost (₹)"].idxmax()
            ]

            highest_ctr = insights_df.loc[
                insights_df["CTR (%)"].idxmax()
            ]

            campaigns_with_conversions = insights_df[
                insights_df["Conversions"] > 0
            ]

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "🎯 Best Conversions",
                    best_campaign["Campaign"],
                    f'{best_campaign["Conversions"]:.0f} conversions'
                )

            with col2:
                st.metric(
                    "💰 Highest Spend",
                    highest_spend["Campaign"],
                    f'₹{highest_spend["Cost (₹)"]:,.2f}'
                )

            with col3:
                st.metric(
                    "📈 Highest CTR",
                    highest_ctr["Campaign"],
                    f'{highest_ctr["CTR (%)"]:.2f}%'
                )

            if not campaigns_with_conversions.empty:

                best_cpa = campaigns_with_conversions.loc[
                    campaigns_with_conversions["CPA (₹)"].idxmin()
                ]

                st.success(
                    f'🏆 Best CPA Campaign: '
                    f'{best_cpa["Campaign"]} | '
                    f'CPA: ₹{best_cpa["CPA (₹)"]:,.2f}'
                )

            else:

                st.info(
                    "No campaigns with conversions available for CPA analysis."
                )

        else:

            st.info(
                "No campaign data available."
            )
        # ==================================================
        # SMART ALERTS
        # ==================================================

        st.divider()
        st.header("🚨 Smart Alerts")

        alerts = []

        # High CPA Alert
        if overall_cpa > 2000:
            alerts.append(
                f"🔴 High CPA Alert: Your CPA is ₹{overall_cpa:,.2f}. "
                "Consider reducing spend on expensive keywords."
            )

        # Low CTR Alert
        if overall_ctr < 3:
            alerts.append(
                f"⚠️ Low CTR Alert: Your CTR is {overall_ctr:.2f}%. "
                "Improve ad copy and keyword relevance."
            )

        # Low Conversion Rate Alert
        if overall_conversion_rate < 2:
            alerts.append(
                f"⚠️ Low Conversion Rate: {overall_conversion_rate:.2f}%. "
                "Review landing page and search terms."
            )

        # High CPC Alert
        if overall_cpc > 60:
            alerts.append(
                f"💰 High CPC Alert: Average CPC is ₹{overall_cpc:.2f}. "
                "Focus on high-intent keywords."
            )

        # Waste Spend Alert
        if 'waste_df' in locals() and not waste_df.empty:

            total_waste = waste_df["Cost (₹)"].sum()

            if total_waste > 500:

                alerts.append(
                    f"🔴 Potential Waste Spend: ₹{total_waste:,.2f} spent "
                    "on search terms with 0 conversions."
                )


        # DISPLAY ALERTS

        if alerts:

            for alert in alerts:

                st.warning(alert)

        else:

            st.success(
                "🟢 Great! No major performance alerts detected."
            )
        # ==================================================
        # CAMPAIGN RECOMMENDATIONS
        # ==================================================

        st.divider()
        st.header("🎯 Campaign Recommendations")

        if not filtered_df.empty:

            recommendations = []

            for _, row in filtered_df.iterrows():

                campaign = row["Campaign"]
                cost = float(row["Cost (₹)"])
                conversions = float(row["Conversions"])
                clicks = float(row["Clicks"])
                impressions = float(row["Impressions"])

                ctr = (
                    clicks / impressions * 100
                    if impressions > 0
                    else 0
                )

                cpa = (
                    cost / conversions
                    if conversions > 0
                    else 0
                )

                if conversions == 0 and cost > 500:

                    status = "🔴 Review / Pause"
                    recommendation = (
                        "High spend with 0 conversions. "
                        "Review keywords and search terms."
                    )

                elif conversions > 0 and cpa > overall_cpa:

                    status = "⚠️ Optimize"
                    recommendation = (
                        f"CPA is ₹{cpa:,.2f}. "
                        "Reduce waste and improve keyword targeting."
                    )

                elif conversions > 0 and cpa <= overall_cpa:

                    status = "🟢 Scale"
                    recommendation = (
                        f"Good CPA of ₹{cpa:,.2f}. "
                        "Consider increasing budget."
                    )

                elif ctr > overall_ctr and conversions == 0:

                    status = "🟡 Check Landing Page"
                    recommendation = (
                        "Good CTR but no conversions. "
                        "Review landing page and conversion tracking."
                    )

                else:

                    status = "🟡 Monitor"
                    recommendation = (
                        "Continue monitoring campaign performance."
                    )

                recommendations.append({
                    "Campaign": campaign,
                    "Status": status,
                    "Recommendation": recommendation
                })

            if recommendations:

                recommendation_df = pd.DataFrame(recommendations)

                st.dataframe(
                    recommendation_df,
                    width="stretch",
                    hide_index=True
                )

            else:

                st.info(
                    "No campaign recommendations available."
                )

        else:

            st.info(
                "No campaign data available for recommendations."
            )
            
           # ==================================================
        # BUDGET OPTIMIZATION
        # ==================================================

        st.divider()
        st.header("💰 Budget Optimization Suggestions")

        if not filtered_df.empty:

            budget_suggestions = []

            for _, row in filtered_df.iterrows():

                campaign = row["Campaign"]
                cost = float(row["Cost (₹)"])
                conversions = float(row["Conversions"])

                cpa = (
                    cost / conversions
                    if conversions > 0 else 0
                )

                if conversions == 0 and cost > 500:

                    action = "🔴 Reduce / Stop"
                    suggestion = (
                        "Spend is high but there are no conversions. "
                        "Reduce budget and review search terms."
                    )

                elif conversions > 0 and cpa < overall_cpa * 0.8:

                    action = "🟢 Increase Budget"
                    suggestion = (
                        f"Strong performance with CPA ₹{cpa:,.2f}. "
                        "Consider increasing budget by 10–20%."
                    )

                elif conversions > 0 and cpa > overall_cpa * 1.2:

                    action = "🟠 Reduce Budget"
                    suggestion = (
                        f"CPA ₹{cpa:,.2f} is above average. "
                        "Optimize keywords before increasing spend."
                    )

                else:

                    action = "🟡 Maintain"
                    suggestion = (
                        "Performance is close to account average. "
                        "Keep budget stable and continue monitoring."
                    )

                budget_suggestions.append({
                    "Campaign": campaign,
                    "Cost (₹)": round(cost, 2),
                    "Conversions": round(conversions, 2),
                    "CPA (₹)": round(cpa, 2) if conversions > 0 else "N/A",
                    "Action": action,
                    "Suggestion": suggestion
                })


            budget_df = pd.DataFrame(budget_suggestions)

            st.dataframe(
                budget_df,
                width="stretch",
                hide_index=True
            )

        else:

            st.info(
                "No campaign data available for budget optimization."
            )
               

        # ==================================================
        # ADVANCED AI NEGATIVE KEYWORD INTELLIGENCE V2
        # TOKEN-EFFICIENT VERSION
        # ==================================================

        st.divider()
        st.header("🚫 Advanced AI Negative Keyword Intelligence")

        if "search_df" in locals() and not search_df.empty:

            required_columns = [
                "Search Term",
                "Clicks",
                "Cost (₹)",
                "Conversions"
            ]

            missing_columns = [
                col
                for col in required_columns
                if col not in search_df.columns
            ]

            if missing_columns:

                st.warning(
                    "Required search-term columns are missing: "
                    + ", ".join(missing_columns)
                )

            else:

                negative_candidates = search_df[
                    (search_df["Conversions"] == 0)
                    &
                    (search_df["Cost (₹)"] > 0)
                ].copy()

                negative_candidates = negative_candidates.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

                if not negative_candidates.empty:

                    candidate_count = len(negative_candidates)
                    candidate_spend = float(negative_candidates["Cost (₹)"].sum())
                    candidate_clicks = float(negative_candidates["Clicks"].sum())
                    top_candidate_spend = float(negative_candidates["Cost (₹)"].max())

                    neg_col1, neg_col2, neg_col3, neg_col4 = st.columns(4)

                    with neg_col1:
                        st.metric("Terms to Review", f"{candidate_count:,}")

                    with neg_col2:
                        st.metric("Spend Under Review", f"₹{candidate_spend:,.2f}")

                    with neg_col3:
                        st.metric("Clicks Under Review", f"{candidate_clicks:,.0f}")

                    with neg_col4:
                        st.metric("Highest Single-Term Spend", f"₹{top_candidate_spend:,.2f}")

                    st.subheader("🔍 Zero-Conversion Search Terms to Review")

                    display_columns = ["Search Term"]

                    if "Campaign" in negative_candidates.columns:
                        display_columns.append("Campaign")

                    display_columns.extend([
                        "Clicks",
                        "Cost (₹)",
                        "Conversions"
                    ])

                    st.dataframe(
                        negative_candidates[display_columns],
                        width="stretch",
                        hide_index=True
                    )

                    st.info(
                        "Dashboard shows the full selected-period search-term data. "
                        "AI analyzes only the Top 15 highest-spend terms to reduce "
                        "token usage and protect API credits."
                    )

                    if st.button(
                        "🧠 Run Advanced Negative Keyword Intelligence",
                        key="advanced_negative_keyword_v2_button"
                    ):

                        ai_columns = ["Search Term"]

                        if "Campaign" in negative_candidates.columns:
                            ai_columns.append("Campaign")

                        ai_columns.extend([
                            "Clicks",
                            "Cost (₹)",
                            "Conversions"
                        ])

                        ai_negative_candidates = (
                            negative_candidates[ai_columns]
                            .head(15)
                            .copy()
                        )

                        negative_context = ai_negative_candidates.to_string(index=False)

                        negative_prompt = f"""
        You are a senior Google Ads Search Term analyst.

        BUSINESS:
        Harekrishna Home Care Services

        LOCATION:
        Hyderabad

        VALID SERVICES:
        home care, elderly care, senior care, patient care,
        nursing, nurse at home, home nurse, caretaker,
        care taker, baby care, babysitter, nanny,
        maid, domestic help, housekeeping, housekeeper, cook.

        PROTECTED BRAND TERMS:
        hare krishna
        harekrishna
        hare krishna home care
        harekrishna home care
        hare krishna home care services
        harekrishna home care services

        IMPORTANT RULES:
        1. Never block the Harekrishna / Hare Krishna brand.
        2. Never make core service words negative merely because they have zero conversions.
        3. Zero conversions alone is NOT enough reason to block a term.
        4. If a valid service contains irrelevant intent, block only the irrelevant modifier.
        5. Job intent such as jobs, vacancy, salary, career, recruitment, resume may be negative when clearly irrelevant.
        6. Training intent such as course, training, institute, certification, exam may be negative when clearly irrelevant.
        7. Competitor-brand terms should normally be REVIEW, not automatically blocked.
        8. Relevant services belonging to another service category should be REVIEW with campaign routing, not blocked.
        9. Be conservative and protect qualified leads.
        10. Never invent performance data.

        Examples:
        maid jobs -> negative "jobs", NOT "maid"
        nurse salary -> negative "salary", NOT "nurse"
        caretaker vacancy -> negative "vacancy", NOT "caretaker"
        home care course -> negative "course", NOT "home care"

        SEARCH TERMS TO ANALYZE:
        These are only the Top 15 highest-spend zero-conversion search terms from the selected dashboard period.

        {negative_context}

        For each term classify:
        Intent: LEAD / BRAND / JOB / TRAINING / INFORMATIONAL / COMPETITOR / WRONG LOCATION / UNRELATED SERVICE / AMBIGUOUS
        Recommended Action: KEEP / REVIEW / ADD AS NEGATIVE
        Risk: PROTECTED / LOW RISK TO BLOCK / MEDIUM RISK / HIGH RISK TO BLOCK
        Suggested Match Type: Phrase / Exact

        Return a concise Markdown table with:
        Search Term | Campaign | Spend | Clicks | Intent | Recommended Action | Suggested Negative Keyword | Suggested Match Type | Confidence Score | Risk Level | Campaign Routing | Reason | Priority

        After the table provide only:
        1. Safe Negatives to Apply Now
        2. Protected Terms — Never Block
        3. Review Before Blocking
        4. Campaign Routing Opportunities
        5. Top 5 Actions

        Keep the answer concise. Do not invent savings.
        """

                        with st.spinner(
                            "AI is analyzing the Top 15 highest-spend search terms..."
                        ):
                            negative_ai_response = openai_client.responses.create(
                                model="gpt-5.4-mini",
                                input=negative_prompt,
                                max_output_tokens=2200
                            )

                        st.subheader("🤖 Advanced Negative Keyword Intelligence")
                        st.caption(
                            "AI analyzed only the Top 15 highest-spend terms. "
                            "The full search-term dataset remains available above."
                        )
                        st.write(negative_ai_response.output_text)

                else:
                    st.success(
                        "No search terms with spend and zero conversions "
                        "were found for the selected data."
                    )

        else:
            st.info("Search term data is not available.")

        # ==================================================
        # COMPETITOR SEARCH-TERM INTELLIGENCE
        # TOKEN-EFFICIENT AI VERSION
        # ==================================================

        st.divider()
        st.header("🏁 Competitor Intelligence")

        st.caption(
            "This section identifies competitor-style brand searches from "
            "your Google Ads search-term data. It is not Auction Insights."
        )

        if "search_df" in locals() and not search_df.empty:

            competitor_required_columns = [
                "Search Term",
                "Clicks",
                "Cost (₹)",
                "Conversions"
            ]

            competitor_missing_columns = [
                col
                for col in competitor_required_columns
                if col not in search_df.columns
            ]

            if competitor_missing_columns:

                st.warning(
                    "Required competitor-analysis columns are missing: "
                    + ", ".join(competitor_missing_columns)
                )

            else:

                competitor_source_df = search_df.copy()

                competitor_source_df = competitor_source_df[
                    competitor_source_df["Cost (₹)"] > 0
                ].copy()

                competitor_source_df = competitor_source_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

                if not competitor_source_df.empty:

                    comp_col1, comp_col2, comp_col3 = st.columns(3)

                    with comp_col1:
                        st.metric(
                            "Search Terms Available",
                            f"{len(competitor_source_df):,}"
                        )

                    with comp_col2:
                        st.metric(
                            "Spend Represented",
                            f"₹{float(competitor_source_df['Cost (₹)'].sum()):,.2f}"
                        )

                    with comp_col3:
                        st.metric(
                            "AI Terms Per Run",
                            "Top 15"
                        )

                    st.info(
                        "The dashboard keeps the full search-term dataset. "
                        "Competitor AI sends only the Top 15 highest-spend "
                        "search terms to OpenAI to control token usage."
                    )

                    if st.button(
                        "🧠 Run Competitor Intelligence",
                        key="competitor_intelligence_button_v1"
                    ):

                        competitor_ai_columns = ["Search Term"]

                        if "Campaign" in competitor_source_df.columns:
                            competitor_ai_columns.append("Campaign")

                        competitor_ai_columns.extend(
                            [
                                "Clicks",
                                "Cost (₹)",
                                "Conversions"
                            ]
                        )

                        competitor_ai_df = (
                            competitor_source_df[
                                competitor_ai_columns
                            ]
                            .head(15)
                            .copy()
                        )

                        competitor_context = (
                            competitor_ai_df
                            .to_string(index=False)
                        )

                        competitor_cache_key = (
                            f"{date_option}|{selected_campaign}|"
                            f"{competitor_context}"
                        )

                        if (
                            st.session_state.get(
                                "competitor_ai_cache_key"
                            ) == competitor_cache_key
                            and st.session_state.get(
                                "competitor_ai_cache_text"
                            )
                        ):

                            competitor_ai_text = st.session_state[
                                "competitor_ai_cache_text"
                            ]

                            st.success(
                                "Showing the saved result for the same "
                                "date range and campaign. No new AI call was used."
                            )

                        else:

                            competitor_prompt = f"""
You are a senior Google Ads competitor search-term analyst.

BUSINESS:
Harekrishna Home Care Services

PRIMARY MARKET:
Hyderabad

VALID BUSINESS SERVICES:
home care, elderly care, senior care, patient care,
nursing, nurse at home, home nurse, caretaker,
care taker, baby care, babysitter, nanny,
maid, domestic help, housekeeping, housekeeper, cook.

OWN BRAND — NEVER CLASSIFY AS A COMPETITOR:
hare krishna
harekrishna
hare krishna home care
harekrishna home care
hare krishna home care services
harekrishna home care services

IMPORTANT RULES:
1. Identify a competitor only when the supplied search term clearly
   contains another business, agency, hospital, platform or brand name.
2. Never invent competitor names that are not present in the supplied data.
3. Do not classify generic searches such as "home care services near me",
   "nurse near me", "caretaker hyderabad" or other service queries as competitors.
4. Own Harekrishna / Hare Krishna brand searches are OWN BRAND, never competitor.
5. Competitor searches should normally be REVIEW, not automatically blocked.
6. Zero conversions alone is not enough reason to block a competitor term.
7. If a competitor term converted, clearly highlight that it may be valuable traffic.
8. If a competitor term has spend and zero conversions, recommend REVIEW first.
9. Do not invent conversion quality, revenue, impression share or competitor market share.
10. Use only the data below.

SEARCH-TERM DATA TO ANALYZE:
These are only the Top 15 highest-spend search terms for this AI run.

{competitor_context}

Return a concise Markdown table with these columns:
Search Term | Campaign | Spend | Clicks | Conversions | Type | Competitor / Brand Detected | Recommended Action | Risk | Reason

Type must be one of:
OWN BRAND / COMPETITOR / GENERIC SERVICE / AMBIGUOUS / UNRELATED

Recommended Action must be one of:
KEEP / REVIEW / CONSIDER NEGATIVE

After the table provide only:
1. Competitors Detected
2. Competitor Terms That Converted
3. Competitor Terms With Spend + Zero Conversions
4. Own Brand Terms Protected
5. Top 3 Competitor Actions

If no real competitor brand is visible in the supplied data, say clearly:
"No clear competitor brand detected in the Top 15 terms."

Keep the answer concise and do not invent data.
"""

                            try:

                                with st.spinner(
                                    "AI is checking competitor-style search terms..."
                                ):

                                    competitor_ai_response = (
                                        openai_client.responses.create(
                                            model="gpt-5.4-mini",
                                            input=competitor_prompt,
                                            max_output_tokens=1600
                                        )
                                    )

                                competitor_ai_text = (
                                    competitor_ai_response.output_text
                                )

                                st.session_state[
                                    "competitor_ai_cache_key"
                                ] = competitor_cache_key

                                st.session_state[
                                    "competitor_ai_cache_text"
                                ] = competitor_ai_text

                            except Exception as competitor_ai_error:

                                competitor_ai_text = None

                                st.error(
                                    "Competitor AI could not run right now. "
                                    "If this is a rate-limit or credit issue, "
                                    "wait or add API credit and try again once."
                                )

                                st.caption(
                                    f"Technical detail: {competitor_ai_error}"
                                )

                        if competitor_ai_text:

                            st.subheader(
                                "🤖 Competitor Search-Term Analysis"
                            )

                            st.caption(
                                "AI analyzed only the Top 15 highest-spend "
                                "search terms. Full search-term data remains "
                                "available in the dashboard."
                            )

                            st.write(competitor_ai_text)

                else:

                    st.info(
                        "No search terms with spend are available for "
                        "competitor analysis."
                    )

        else:

            st.info(
                "Search term data is not available for competitor analysis."
            )

        # ==================================================
        # AI PRIORITY ACTION CENTER
        # ==================================================

        st.divider()
        st.header("🎯 AI Priority Action Center")

        priority_actions = []

        # HIGH CPA
        if overall_cpa > 2000 and total_conversions > 0:

            priority_actions.append({
                "Priority": "🔴 HIGH",
                "Area": "CPA",
                "Problem": f"CPA is high at ₹{overall_cpa:,.2f}",
                "Action": "Reduce waste spend and focus budget on converting campaigns."
            })


        # ZERO / LOW CONVERSIONS
        if total_conversions == 0:

            priority_actions.append({
                "Priority": "🔴 HIGH",
                "Area": "Conversions",
                "Problem": "No conversions recorded.",
                "Action": "Check conversion tracking, search terms, keywords and landing page."
            })

        elif overall_conversion_rate < 2:

            priority_actions.append({
                "Priority": "🟠 MEDIUM",
                "Area": "Conversion Rate",
                "Problem": f"Conversion rate is only {overall_conversion_rate:.2f}%",
                "Action": "Improve landing page relevance and focus on high-intent keywords."
            })


        # HIGH CPC
        if overall_cpc > 60:

            priority_actions.append({
                "Priority": "🟠 MEDIUM",
                "Area": "CPC",
                "Problem": f"Average CPC is ₹{overall_cpc:.2f}",
                "Action": "Review expensive keywords, match types and search terms."
            })


        # WASTE SPEND
        if "waste_df" in locals() and not waste_df.empty:

            waste_amount = waste_df["Cost (₹)"].sum()

            if waste_amount > 500:

                priority_actions.append({
                    "Priority": "🔴 HIGH",
                    "Area": "Waste Spend",
                    "Problem": f"₹{waste_amount:,.2f} spent with zero conversions.",
                    "Action": "Review these search terms and add irrelevant terms as negatives."
                })


        # GOOD CTR
        if overall_ctr >= 8:

            priority_actions.append({
                "Priority": "🟢 GOOD",
                "Area": "CTR",
                "Problem": f"CTR is strong at {overall_ctr:.2f}%",
                "Action": "Keep strong ads running and focus on conversion quality."
            })


        if priority_actions:

            priority_df = pd.DataFrame(
                priority_actions
            )

            priority_order = {
                "🔴 HIGH": 1,
                "🟠 MEDIUM": 2,
                "🟢 GOOD": 3
            }

            priority_df["Order"] = (
                priority_df["Priority"]
                .map(priority_order)
            )

            priority_df = (
                priority_df
                .sort_values("Order")
                .drop(columns=["Order"])
            )

            st.dataframe(
                priority_df,
                width="stretch",
                hide_index=True
            )

        else:

            st.success(
                "🟢 No major actions required right now."
            )
         
        # ==================================================
        # # ONE-CLICK AI PERFORMANCE REPORT
        # ==================================================

        st.divider()
        st.header("📋 One-Click AI Performance Report")

        if date_option == "Today":
            report_period = "Today's"

        elif date_option == "Custom Date Range":
            report_period = (
                f"{start_date.strftime('%d %b %Y')} → "
                f"{end_date.strftime('%d %b %Y')}"
            )

        else:
            report_period = date_option


        if st.button(
            "Generate AI Performance Report",
            key="one_click_ai_report_generate_button_v2"
        ):

            if "priority_df" in locals() and not priority_df.empty:
                priority_context = priority_df.to_string(index=False)
            else:
                priority_context = "No priority actions currently available."

            daily_report_prompt = f"""
        You are a senior Google Ads performance analyst.

        REPORT PERIOD:
        {report_period}

        OVERALL PERFORMANCE:

        Impressions: {total_impressions}
        Clicks: {total_clicks}
        Cost: ₹{total_cost:.2f}
        Conversions: {total_conversions:.2f}
        CTR: {overall_ctr:.2f}%
        Average CPC: ₹{overall_cpc:.2f}
        CPA: ₹{overall_cpa:.2f}
        Conversion Rate: {overall_conversion_rate:.2f}%

        CAMPAIGN DATA:

        {filtered_df.to_string(index=False)}

        PRIORITY ACTIONS:

        {priority_context}

        Create a professional Google Ads performance report.

        Include:

        1. Executive Summary
        2. What Is Working Well
        3. Problems Detected
        4. Waste Spend Analysis
        5. Campaign Performance
        6. Budget Recommendations
        7. Conversion Improvement Opportunities
        8. Top Priority Actions
        9. Final Recommendation

        Be practical, clear and concise.
        """

            with st.spinner(
                "AI is generating your performance report..."
            ):

                daily_ai_response = openai_client.responses.create(
                    model="gpt-5.4-mini",
                    input=daily_report_prompt
                )

            st.subheader(
                f"🤖 {report_period} AI Performance Report"
            )

            st.write(
                daily_ai_response.output_text
            )


        # ==================================================
        # FINAL AI RECOMMENDATIONS SUMMARY
        # ==================================================

        st.divider()
        st.header("📌 Final AI Recommendations Summary")

        summary_actions = []

        if total_conversions == 0:
            summary_actions.append(
                "🔴 Check conversion tracking and landing page immediately."
            )

        if overall_cpc > 60:
            summary_actions.append(
                f"🟠 Avg CPC is high at ₹{overall_cpc:.2f}. Review expensive keywords."
            )

        if overall_cpa > 2000 and total_conversions > 0:
            summary_actions.append(
                f"🔴 CPA is high at ₹{overall_cpa:.2f}. Reduce waste and optimize targeting."
            )

        if "waste_df" in locals() and not waste_df.empty:
            waste_amount = waste_df["Cost (₹)"].sum()

            summary_actions.append(
                f"🔴 Review ₹{waste_amount:,.2f} potential waste spend."
            )

        if overall_ctr >= 8:
            summary_actions.append(
                f"🟢 CTR is strong at {overall_ctr:.2f}%. Keep high-performing ads running."
            )

        if summary_actions:
            for i, action in enumerate(
                summary_actions[:5],
                start=1
            ):
                st.write(
                    f"**{i}. {action}**"
                )
        else:
            st.success(
                "🟢 Account performance looks stable. Continue monitoring."
            )

        # ==================================================
        # ACCOUNT HEALTH SCORE
        # ==================================================

        st.divider()
        st.header("🧠 Account Health Score")

        # Use the currently selected campaign/date-range data
        health_impressions = float(filtered_df["Impressions"].sum()) if "Impressions" in filtered_df.columns else 0
        health_clicks = float(filtered_df["Clicks"].sum()) if "Clicks" in filtered_df.columns else 0
        health_cost = float(filtered_df["Cost (₹)"].sum()) if "Cost (₹)" in filtered_df.columns else 0
        health_conversions = float(filtered_df["Conversions"].sum()) if "Conversions" in filtered_df.columns else 0

        health_ctr = (
            (health_clicks / health_impressions) * 100
            if health_impressions > 0 else 0
        )

        health_cpc = (
            health_cost / health_clicks
            if health_clicks > 0 else 0
        )

        health_cpa = (
            health_cost / health_conversions
            if health_conversions > 0 else 0
        )

        health_conversion_rate = (
            (health_conversions / health_clicks) * 100
            if health_clicks > 0 else 0
        )

        health_score = 100
        health_notes = []

        # CTR
        if health_ctr < 3:
            health_score -= 20
            health_notes.append(f"🔴 CTR is low at {health_ctr:.2f}%.")
        elif health_ctr < 6:
            health_score -= 10
            health_notes.append(f"🟠 CTR needs improvement at {health_ctr:.2f}%.")
        else:
            health_notes.append(f"🟢 CTR is healthy at {health_ctr:.2f}%.")

        # CPC
        if health_cpc > 60:
            health_score -= 15
            health_notes.append(f"🔴 CPC is high at ₹{health_cpc:.2f}.")
        elif health_cpc > 40:
            health_score -= 8
            health_notes.append(f"🟠 CPC is moderately high at ₹{health_cpc:.2f}.")
        else:
            health_notes.append(f"🟢 CPC is under control at ₹{health_cpc:.2f}.")

        # Conversion Rate
        if health_conversion_rate < 2:
            health_score -= 20
            health_notes.append(
                f"🔴 Conversion Rate is low at {health_conversion_rate:.2f}%."
            )
        elif health_conversion_rate < 5:
            health_score -= 10
            health_notes.append(
                f"🟠 Conversion Rate needs improvement at {health_conversion_rate:.2f}%."
            )
        else:
            health_notes.append(
                f"🟢 Conversion Rate is healthy at {health_conversion_rate:.2f}%."
            )

        # CPA
        if health_conversions > 0:
            if health_cpa > 2000:
                health_score -= 20
                health_notes.append(f"🔴 CPA is high at ₹{health_cpa:.2f}.")
            elif health_cpa > 1000:
                health_score -= 10
                health_notes.append(f"🟠 CPA needs monitoring at ₹{health_cpa:.2f}.")
            else:
                health_notes.append(f"🟢 CPA is healthy at ₹{health_cpa:.2f}.")
        else:
            health_score -= 20
            health_notes.append("🔴 No conversions recorded for the selected data.")

        # Waste spend
        if "waste_df" in locals() and not waste_df.empty:
            waste_amount = float(waste_df["Cost (₹)"].sum())

            waste_ratio = (
                (waste_amount / health_cost) * 100
                if health_cost > 0 else 0
            )

            if waste_ratio > 25:
                health_score -= 20
                health_notes.append(
                    f"🔴 Waste spend is high at {waste_ratio:.1f}% of selected spend."
                )
            elif waste_ratio > 10:
                health_score -= 10
                health_notes.append(
                    f"🟠 Waste spend is {waste_ratio:.1f}% of selected spend."
                )
            else:
                health_notes.append(
                    f"🟢 Waste spend is under control at {waste_ratio:.1f}%."
                )

        health_score = max(0, min(100, health_score))

        if health_score >= 80:
            health_status = "🟢 Excellent"
        elif health_score >= 60:
            health_status = "🟡 Good"
        elif health_score >= 40:
            health_status = "🟠 Needs Attention"
        else:
            health_status = "🔴 Critical"

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Account Health Score",
                f"{health_score}/100"
            )

        with col2:
            st.metric(
                "Health Status",
                health_status
            )

        st.progress(health_score / 100)

        for note in health_notes:
            st.write(note)
        # ==================================================
        # WASTE RISK + BUDGET REALLOCATION INTELLIGENCE
        # ==================================================

        st.divider()
        st.header("🚨 Waste Risk & Budget Intelligence")

        selected_spend = (
            float(filtered_df["Cost (₹)"].sum())
            if "Cost (₹)" in filtered_df.columns
            else 0
        )

        selected_conversions = (
            float(filtered_df["Conversions"].sum())
            if "Conversions" in filtered_df.columns
            else 0
        )

        selected_cpa = (
            selected_spend / selected_conversions
            if selected_conversions > 0
            else 0
        )

        waste_amount = 0.0

        if "waste_df" in locals() and not waste_df.empty:
            if "Cost (₹)" in waste_df.columns:
                waste_amount = float(waste_df["Cost (₹)"].sum())

        waste_ratio = (
            (waste_amount / selected_spend) * 100
            if selected_spend > 0
            else 0
        )

        # -----------------------------
        # WASTE RISK SCORE
        # -----------------------------

        if waste_ratio >= 30:
            waste_risk_score = 90
            waste_risk_status = "🔴 Critical"
        elif waste_ratio >= 20:
            waste_risk_score = 75
            waste_risk_status = "🟠 High"
        elif waste_ratio >= 10:
            waste_risk_score = 50
            waste_risk_status = "🟡 Moderate"
        elif waste_ratio > 0:
            waste_risk_score = 25
            waste_risk_status = "🟢 Low"
        else:
            waste_risk_score = 0
            waste_risk_status = "🟢 Very Low"

        risk_col1, risk_col2, risk_col3 = st.columns(3)

        with risk_col1:
            st.metric(
                "Waste Risk Score",
                f"{waste_risk_score}/100"
            )

        with risk_col2:
            st.metric(
                "Waste Risk",
                waste_risk_status
            )

        with risk_col3:
            st.metric(
                "Potential Waste Spend",
                f"₹{waste_amount:,.2f}"
            )

        st.progress(waste_risk_score / 100)

        st.write(
            f"Potential waste represents **{waste_ratio:.1f}%** "
            f"of selected spend."
        )

        # -----------------------------
        # BUDGET INTELLIGENCE
        # -----------------------------

        st.subheader("💰 Budget Reallocation Suggestions")

        budget_actions = []

        # Critical / high waste = do NOT increase budget
        if waste_ratio >= 20:
            budget_actions.append(
                "🔴 **Do not increase total budget yet.** "
                "Waste spend is too high. Reduce irrelevant traffic first."
            )

            budget_actions.append(
                "🚫 **Priority:** Review search terms and add negative keywords "
                "before scaling any campaign."
            )

            if selected_cpa > 1500:
                budget_actions.append(
                    f"🟠 **CPA is high at ₹{selected_cpa:,.2f}.** "
                    "Improve conversion efficiency before increasing spend."
                )

        elif waste_ratio >= 10:
            budget_actions.append(
                "🟡 **Hold major budget increases.** "
                "Clean search terms and reduce waste first."
            )

        else:
            # Only recommend scaling when waste is controlled
            if not filtered_df.empty:
                budget_df = filtered_df.copy()

                if (
                    "Cost (₹)" in budget_df.columns
                    and "Conversions" in budget_df.columns
                ):

                    budget_df["AI CPA"] = budget_df.apply(
                        lambda row:
                            row["Cost (₹)"] / row["Conversions"]
                            if row["Conversions"] > 0
                            else float("inf"),
                        axis=1
                    )

                    converting_df = budget_df[
                        budget_df["Conversions"] > 0
                    ].copy()

                    if not converting_df.empty:
                        best_campaign = converting_df.loc[
                            converting_df["AI CPA"].idxmin()
                        ]

                        best_campaign_name = (
                            best_campaign["Campaign"]
                            if "Campaign" in converting_df.columns
                            else "Best-performing campaign"
                        )

                        budget_actions.append(
                            "🟢 **Increase carefully:** "
                            f"{best_campaign_name} has the strongest CPA "
                            f"at ₹{best_campaign['AI CPA']:,.2f}."
                        )

        # Zero-conversion spend check
        if not filtered_df.empty:
            if (
                "Cost (₹)" in filtered_df.columns
                and "Conversions" in filtered_df.columns
            ):
                zero_conversion_df = filtered_df[
                    (filtered_df["Cost (₹)"] > 0)
                    & (filtered_df["Conversions"] == 0)
                ].copy()

                if not zero_conversion_df.empty:
                    highest_waste_campaign = zero_conversion_df.loc[
                        zero_conversion_df["Cost (₹)"].idxmax()
                    ]

                    zero_campaign_name = (
                        highest_waste_campaign["Campaign"]
                        if "Campaign" in zero_conversion_df.columns
                        else "Zero-conversion campaign"
                    )

                    budget_actions.append(
                        "🔴 **Reduce or pause for review:** "
                        f"{zero_campaign_name} spent "
                        f"₹{highest_waste_campaign['Cost (₹)']:,.2f} "
                        "with zero conversions."
                    )

        if not budget_actions:
            budget_actions.append(
                "🟢 Current budget distribution looks stable. "
                "Continue monitoring CPA, conversion rate, and waste spend."
            )

        for i, action in enumerate(
            budget_actions[:5],
            start=1
        ):
            st.write(
                f"**{i}. {action}**"
            )

        # -----------------------------
        # TOP 5 ACTIONS NOW
        # -----------------------------

        st.subheader("🎯 Top 5 Actions Now")

        top_actions = []

        if waste_ratio >= 10:
            top_actions.append(
                "Review search terms and add negative keywords."
            )

        if selected_cpa > 1500:
            top_actions.append(
                "Reduce high-CPA traffic before increasing budget."
            )

        if "health_ctr" in locals() and health_ctr < 3:
            top_actions.append(
                "Improve ad copy and keyword relevance to raise CTR."
            )

        if "health_conversion_rate" in locals() and health_conversion_rate < 5:
            top_actions.append(
                "Improve landing page and lead conversion flow."
            )

        if selected_conversions > 0:
            top_actions.append(
                "Protect campaigns producing real conversions."
            )

        if not top_actions:
            top_actions.append(
                "Continue monitoring performance and scale gradually."
            )

        for i, action in enumerate(
            top_actions[:5],
            start=1
        ):
            st.write(
                f"**{i}. {action}**"
            )
        # ==================================================
        # BEFORE VS AFTER PERFORMANCE INTELLIGENCE
        # ==================================================

        st.divider()
        st.header("📊 Before vs After Performance Intelligence")


        def baf_numeric_series(data, possible_names):

            for column_name in possible_names:

                if column_name in data.columns:

                    return pd.to_numeric(
                        data[column_name],
                        errors="coerce"
                    ).fillna(0)

            return pd.Series(
                0.0,
                index=data.index
            )


        def baf_summary(data):

            impressions = float(
                baf_numeric_series(
                    data,
                    ["Impressions"]
                ).sum()
            )

            clicks = float(
                baf_numeric_series(
                    data,
                    ["Clicks"]
                ).sum()
            )

            cost = float(
                baf_numeric_series(
                    data,
                    [
                        "Cost",
                        "Cost (₹)",
                        "Spend",
                        "Spend (₹)"
                    ]
                ).sum()
            )

            conversions = float(
                baf_numeric_series(
                    data,
                    ["Conversions"]
                ).sum()
            )

            ctr = (
                clicks / impressions * 100
                if impressions > 0
                else 0
            )

            avg_cpc = (
                cost / clicks
                if clicks > 0
                else 0
            )

            cpa = (
                cost / conversions
                if conversions > 0
                else 0
            )

            conversion_rate = (
                conversions / clicks * 100
                if clicks > 0
                else 0
            )

            return {
                "Impressions": impressions,
                "Clicks": clicks,
                "Cost": cost,
                "Conversions": conversions,
                "CTR": ctr,
                "Avg CPC": avg_cpc,
                "CPA": cpa,
                "Conversion Rate": conversion_rate
            }


        def baf_pct_change(before_value, after_value):

            if before_value == 0:

                if after_value == 0:
                    return 0

                return 100

            return (
                (after_value - before_value)
                / before_value
            ) * 100


        if "daily_df" in locals() and not daily_df.empty:

            compare_df = daily_df.copy()

            if "Date" not in compare_df.columns:
                compare_df = compare_df.reset_index()

            if "Date" not in compare_df.columns:
                compare_df = compare_df.rename(
                    columns={
                        compare_df.columns[0]: "Date"
                    }
                )

            compare_df["Date"] = pd.to_datetime(
                compare_df["Date"],
                errors="coerce"
            )

            compare_df = (
                compare_df
                .dropna(subset=["Date"])
                .sort_values("Date")
                .reset_index(drop=True)
            )

            # ==============================================
            # SELECTED PERIOD BOUNDARIES
            # ==============================================

            if date_option == "Last 30 Days":

                period_end_date = pd.Timestamp(
                    today - timedelta(days=1)
                )

                period_start_date = (
                    period_end_date
                    - pd.Timedelta(days=29)
                )

            elif date_option == "Custom Date Range":

                period_start_date = pd.Timestamp(
                    start_date
                )

                period_end_date = pd.Timestamp(
                    end_date
                )

            else:

                period_start_date = (
                    compare_df["Date"]
                    .min()
                    .normalize()
                )

                period_end_date = (
                    compare_df["Date"]
                    .max()
                    .normalize()
                )

            total_days = (
                period_end_date
                - period_start_date
            ).days + 1

            if total_days >= 2:

                before_days = total_days // 2

                before_start_date = period_start_date

                before_end_date = (
                    before_start_date
                    + pd.Timedelta(
                        days=before_days - 1
                    )
                )

                after_start_date = (
                    before_end_date
                    + pd.Timedelta(days=1)
                )

                after_end_date = period_end_date

                after_days = (
                    after_end_date
                    - after_start_date
                ).days + 1

                before_df = compare_df[
                    (compare_df["Date"] >= before_start_date)
                    &
                    (compare_df["Date"] <= before_end_date)
                ].copy()

                after_df = compare_df[
                    (compare_df["Date"] >= after_start_date)
                    &
                    (compare_df["Date"] <= after_end_date)
                ].copy()

                before_metrics = baf_summary(
                    before_df
                )

                after_metrics = baf_summary(
                    after_df
                )

                before_start_text = (
                    before_start_date.strftime(
                        "%d %b %Y"
                    )
                )

                before_end_text = (
                    before_end_date.strftime(
                        "%d %b %Y"
                    )
                )

                after_start_text = (
                    after_start_date.strftime(
                        "%d %b %Y"
                    )
                )

                after_end_text = (
                    after_end_date.strftime(
                        "%d %b %Y"
                    )
                )

                st.caption(
                    f"📅 Before ({before_days} days): "
                    f"{before_start_text} → {before_end_text} | "
                    f"After ({after_days} days): "
                    f"{after_start_text} → {after_end_text}"
                )

                # ==========================================
                # CHANGES
                # ==========================================

                impressions_change = baf_pct_change(
                    before_metrics["Impressions"],
                    after_metrics["Impressions"]
                )

                clicks_change = baf_pct_change(
                    before_metrics["Clicks"],
                    after_metrics["Clicks"]
                )

                cost_change = baf_pct_change(
                    before_metrics["Cost"],
                    after_metrics["Cost"]
                )

                conversions_change = baf_pct_change(
                    before_metrics["Conversions"],
                    after_metrics["Conversions"]
                )

                ctr_change = baf_pct_change(
                    before_metrics["CTR"],
                    after_metrics["CTR"]
                )

                cpc_change = baf_pct_change(
                    before_metrics["Avg CPC"],
                    after_metrics["Avg CPC"]
                )

                cpa_change = baf_pct_change(
                    before_metrics["CPA"],
                    after_metrics["CPA"]
                )

                conversion_rate_change = baf_pct_change(
                    before_metrics["Conversion Rate"],
                    after_metrics["Conversion Rate"]
                )

                comparison_table = pd.DataFrame({

                    "Metric": [
                        "Impressions",
                        "Clicks",
                        "Cost (₹)",
                        "Conversions",
                        "CTR (%)",
                        "Avg CPC (₹)",
                        "CPA (₹)",
                        "Conversion Rate (%)"
                    ],

                    "Before": [
                        f"{before_metrics['Impressions']:,.0f}",
                        f"{before_metrics['Clicks']:,.0f}",
                        f"₹{before_metrics['Cost']:,.2f}",
                        f"{before_metrics['Conversions']:,.2f}",
                        f"{before_metrics['CTR']:.2f}%",
                        f"₹{before_metrics['Avg CPC']:,.2f}",
                        f"₹{before_metrics['CPA']:,.2f}",
                        f"{before_metrics['Conversion Rate']:.2f}%"
                    ],

                    "After": [
                        f"{after_metrics['Impressions']:,.0f}",
                        f"{after_metrics['Clicks']:,.0f}",
                        f"₹{after_metrics['Cost']:,.2f}",
                        f"{after_metrics['Conversions']:,.2f}",
                        f"{after_metrics['CTR']:.2f}%",
                        f"₹{after_metrics['Avg CPC']:,.2f}",
                        f"₹{after_metrics['CPA']:,.2f}",
                        f"{after_metrics['Conversion Rate']:.2f}%"
                    ],

                    "Change": [
                        f"{impressions_change:+.1f}%",
                        f"{clicks_change:+.1f}%",
                        f"{cost_change:+.1f}%",
                        f"{conversions_change:+.1f}%",
                        f"{ctr_change:+.1f}%",
                        f"{cpc_change:+.1f}%",
                        f"{cpa_change:+.1f}%",
                        f"{conversion_rate_change:+.1f}%"
                    ]
                })

                st.dataframe(
                    comparison_table,
                    width="stretch",
                    hide_index=True
                )

                # ==========================================
                # BALANCED PERFORMANCE SCORE
                # ==========================================

                intelligence_score = 50
                intelligence_notes = []

                # Conversions
                if conversions_change >= 20:

                    intelligence_score += 20

                    intelligence_notes.append(
                        f"🟢 Conversions improved strongly by "
                        f"{conversions_change:.1f}%."
                    )

                elif conversions_change >= 10:

                    intelligence_score += 15

                    intelligence_notes.append(
                        f"🟢 Conversions improved by "
                        f"{conversions_change:.1f}%."
                    )

                elif conversions_change <= -20:

                    intelligence_score -= 20

                    intelligence_notes.append(
                        f"🔴 Conversions declined strongly by "
                        f"{abs(conversions_change):.1f}%."
                    )

                elif conversions_change <= -10:

                    intelligence_score -= 15

                    intelligence_notes.append(
                        f"🔴 Conversions declined by "
                        f"{abs(conversions_change):.1f}%."
                    )

                # CPA
                if cpa_change <= -10:

                    intelligence_score += 15

                    intelligence_notes.append(
                        f"🟢 CPA improved by "
                        f"{abs(cpa_change):.1f}%."
                    )

                elif cpa_change >= 25:

                    intelligence_score -= 15

                    intelligence_notes.append(
                        f"🔴 CPA increased significantly by "
                        f"{cpa_change:.1f}%."
                    )

                elif cpa_change >= 10:

                    intelligence_score -= 10

                    intelligence_notes.append(
                        f"🟠 CPA increased by "
                        f"{cpa_change:.1f}%."
                    )

                # CTR
                if ctr_change >= 10:

                    intelligence_score += 10

                    intelligence_notes.append(
                        f"🟢 CTR improved by "
                        f"{ctr_change:.1f}%."
                    )

                elif ctr_change <= -20:

                    intelligence_score -= 10

                    intelligence_notes.append(
                        f"🔴 CTR declined significantly by "
                        f"{abs(ctr_change):.1f}%."
                    )

                elif ctr_change <= -10:

                    intelligence_score -= 5

                    intelligence_notes.append(
                        f"🟠 CTR declined by "
                        f"{abs(ctr_change):.1f}%."
                    )

                # Conversion Rate
                if conversion_rate_change >= 10:

                    intelligence_score += 10

                    intelligence_notes.append(
                        f"🟢 Conversion Rate improved by "
                        f"{conversion_rate_change:.1f}%."
                    )

                elif conversion_rate_change <= -15:

                    intelligence_score -= 10

                    intelligence_notes.append(
                        f"🔴 Conversion Rate declined by "
                        f"{abs(conversion_rate_change):.1f}%."
                    )

                elif conversion_rate_change <= -5:

                    intelligence_score -= 5

                    intelligence_notes.append(
                        f"🟠 Conversion Rate declined by "
                        f"{abs(conversion_rate_change):.1f}%."
                    )

                intelligence_score = max(
                    0,
                    min(
                        100,
                        intelligence_score
                    )
                )

                # ==========================================
                # STATUS
                # ==========================================

                if intelligence_score >= 75:

                    intelligence_status = (
                        "🟢 Strong Improvement"
                    )

                elif intelligence_score >= 55:

                    intelligence_status = (
                        "🟡 Stable / Improving"
                    )

                elif intelligence_score >= 35:

                    intelligence_status = (
                        "🟠 Needs Attention"
                    )

                else:

                    intelligence_status = (
                        "🔴 Performance Declining"
                    )

                score_col1, score_col2 = st.columns(2)

                with score_col1:

                    st.metric(
                        "Performance Intelligence Score",
                        f"{intelligence_score}/100"
                    )

                with score_col2:

                    st.metric(
                        "Performance Trend",
                        intelligence_status
                    )

                st.progress(
                    intelligence_score / 100
                )

                # ==========================================
                # INTERPRETATION
                # ==========================================

                st.subheader(
                    "🧠 Performance Interpretation"
                )

                if intelligence_notes:

                    for note in intelligence_notes:
                        st.write(note)

                else:

                    st.write(
                        "🟡 Performance is relatively stable "
                        "between both periods."
                    )

                # ==========================================
                # RECOMMENDATION - MATCH SCORE
                # ==========================================

                st.subheader(
                    "🎯 Recommended Next Move"
                )

                if intelligence_score >= 75:

                    st.success(
                        "Overall performance improved strongly. "
                        "Protect winning campaigns and increase "
                        "budget gradually while monitoring CPA."
                    )

                elif intelligence_score >= 55:

                    st.info(
                        "Performance is generally stable or improving. "
                        "Continue optimizing search terms and scale "
                        "only campaigns with healthy CPA."
                    )

                elif intelligence_score >= 35:

                    st.warning(
                        "Performance is mixed and needs attention. "
                        "Conversions may be improving, but efficiency "
                        "metrics such as CTR, CPA or Conversion Rate "
                        "need optimization before major budget increases."
                    )

                else:

                    st.error(
                        "Overall performance is declining. "
                        "Reduce waste, review search terms, bids, "
                        "ad relevance and landing-page quality "
                        "before increasing budget."
                    )

            else:

                st.info(
                    "At least 2 days of data are required "
                    "for Before vs After comparison."
                )

        else:

            st.info(
                "Daily performance data is not available."
            )    
        # ==================================================
        # ASK AI
        # ==================================================

        st.divider()
        st.header("🤖 Ask AI About Your Campaign")

        # ==================================================
        # CHAT HISTORY
        # ==================================================

        if "ai_chat_history" not in st.session_state:
            st.session_state.ai_chat_history = []

        if date_option == "Custom Date Range":
            current_ai_period = (
                f"{date_option}:"
                f"{start_date:%Y-%m-%d}:"
                f"{end_date:%Y-%m-%d}"
            )
        else:
            current_ai_period = date_option

        if "ai_chat_period" not in st.session_state:
            st.session_state.ai_chat_period = current_ai_period

        elif st.session_state.ai_chat_period != current_ai_period:
            st.session_state.ai_chat_history = []
            st.session_state.ai_chat_period = current_ai_period

        if st.button(
            "🗑️ Clear AI Chat",
            key="clear_ai_chat_button"
        ):
            st.session_state.ai_chat_history = []
            st.rerun()

        for message in st.session_state.ai_chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # ==================================================
        # QUESTION BOX
        # ==================================================

        question = st.text_input(
            "Ask a question about your campaigns",
            placeholder="Example: గత 30 రోజుల్లో performance ఎలా ఉంది?",
            key="ask_ai_question"
        )

        pending_ai_question = st.session_state.pop(
            "pending_ai_question",
            None
        )

        analyze_clicked = st.button(
            "Analyze with AI",
            key="ask_ai_analyze_button"
        )

        if pending_ai_question:
            question = pending_ai_question

        # ==================================================
        # ANALYZE
        # ==================================================

        if analyze_clicked or pending_ai_question:

            if question and question.strip():

                question = question.strip()
                question_lower = question.lower()

                # ==================================================
                # DETECT DATE RANGE
                # ==================================================

                requested_date_option = None

                if any(
                    phrase in question_lower
                    for phrase in [
                        "today",
                        "ఈ రోజు",
                        "ఈరోజు"
                    ]
                ):
                    requested_date_option = "Today"

                elif any(
                    phrase in question_lower
                    for phrase in [
                        "last 7 days",
                        "గత 7 రోజులు",
                        "గత 7 రోజుల్లో",
                        "7 days"
                    ]
                ):
                    requested_date_option = "Last 7 Days"

                elif any(
                    phrase in question_lower
                    for phrase in [
                        "last 30 days",
                        "గత 30 రోజులు",
                        "గత 30 రోజుల్లో",
                        "30 days"
                    ]
                ):
                    requested_date_option = "Last 30 Days"

                elif any(
                    phrase in question_lower
                    for phrase in [
                        "last 90 days",
                        "గత 90 రోజులు",
                        "గత 90 రోజుల్లో",
                        "90 days"
                    ]
                ):
                    requested_date_option = "Last 90 Days"

                elif any(
                    phrase in question_lower
                    for phrase in [
                        "last 6 months",
                        "గత 6 నెలలు",
                        "గత 6 నెలల్లో",
                        "6 months"
                    ]
                ):
                    requested_date_option = "Last 6 Months"

                elif any(
                    phrase in question_lower
                    for phrase in [
                        "last 1 year",
                        "last year",
                        "గత 1 సంవత్సరం",
                        "గత సంవత్సరం",
                        "1 year"
                    ]
                ):
                    requested_date_option = "Last 1 Year"

                # ==================================================
                # AUTO DATE CHANGE + SAME QUESTION
                # ==================================================

                if (
                    requested_date_option
                    and requested_date_option != date_option
                ):
                    st.session_state.pending_ai_date_option = (
                        requested_date_option
                    )

                    st.session_state.pending_ai_question = question
                    st.session_state.ai_chat_history = []

                    st.rerun()

                # Save user message only after correct date data loads
                st.session_state.ai_chat_history.append(
                    {
                        "role": "user",
                        "content": question
                    }
                )

                # ==================================================
                # SEARCH TERMS CONTEXT
                # ==================================================

                if "search_df" in locals() and not search_df.empty:

                    search_terms_for_ai = search_df.copy()

                    required_columns = {
                        "Search Term",
                        "Campaign",
                        "Clicks",
                        "Cost (₹)",
                        "Conversions"
                    }

                    if required_columns.issubset(
                        search_terms_for_ai.columns
                    ):
                        search_terms_for_ai = (
                            search_terms_for_ai
                            .groupby(
                                ["Search Term", "Campaign"],
                                as_index=False
                            )
                            .agg(
                                {
                                    "Clicks": "sum",
                                    "Cost (₹)": "sum",
                                    "Conversions": "sum"
                                }
                            )
                            .sort_values(
                                "Cost (₹)",
                                ascending=False
                            )
                            .head(100)
                        )

                    else:
                        search_terms_for_ai = (
                            search_terms_for_ai.head(100)
                        )

                    search_terms_context = (
                        search_terms_for_ai.to_string(
                            index=False
                        )
                    )

                    search_terms_available = True

                else:
                    search_terms_context = (
                        "No Search Terms data is available "
                        "for the selected date range."
                    )

                    search_terms_available = False

                # ==================================================
                # BEFORE VS AFTER CONTEXT
                # ==================================================

                if (
                    "comparison_data" in locals()
                    and not comparison_data.empty
                ):
                    before_after_context = (
                        comparison_data.to_string(index=False)
                    )
                else:
                    before_after_context = (
                        "No Before vs After comparison data is available."
                    )

                # ==================================================
                # NEGATIVE KEYWORD QUESTION
                # ==================================================

                negative_keyword_question = any(
                    phrase in question_lower
                    for phrase in [
                        "negative keyword",
                        "negative keywords",
                        "నెగటివ్",
                        "నెగెటివ్"
                    ]
                )

                if (
                    negative_keyword_question
                    and not search_terms_available
                ):

                    telugu_question = any(
                        "\u0c00" <= char <= "\u0c7f"
                        for char in question
                    )

                    if telugu_question:
                        assistant_text = (
                            f"Selected date range **{date_option}** లో "
                            "Search Terms data అందుబాటులో లేదు. "
                            "కాబట్టి actual Search Terms ఆధారంగా "
                            "negative keywords‌ను confirm చేయలేను. "
                            "నేను ఊహించి negative keywords suggest చేయను."
                        )
                    else:
                        assistant_text = (
                            f"No Search Terms data is available for "
                            f"**{date_option}**. I cannot confirm "
                            "negative keywords without actual Search Terms data, "
                            "and I will not invent suggestions."
                        )

                else:

                    # ==================================================
                    # AI PROMPT
                    # ==================================================

                    prompt = f"""
        You are a professional Google Ads AI analyst.

        IMPORTANT LANGUAGE RULES:
        - Detect the language used in the user's question.
        - If the question is in Telugu, answer in Telugu.
        - If the question is in English, answer in English.
        - If the user mixes Telugu and English, reply naturally in the same style.
        - Keep Google Ads technical terms such as CTR, CPC, CPA, Keywords and Conversions in English when useful.

        IMPORTANT DATA RULES:
        - Use ONLY the Google Ads data supplied below.
        - Never invent metrics.
        - Never invent Search Terms.
        - Never invent negative keywords.
        - The selected date range is the authoritative period for the supplied data.
        - Answer only for that period.
        - Do not present campaign-vs-account performance as Before vs After.
        - Use BEFORE VS AFTER DATA only when actual comparison data is available.

        ADVERTISER SERVICES:
        - Home Care
        - Patient Care
        - Elderly Care
        - Nursing Care
        - Baby Care
        - Babysitter
        - Nanny
        - Caretaker
        - Caregiver

        NEGATIVE KEYWORD RULES:
        - Use ONLY actual terms from SEARCH TERMS DATA.
        - Zero conversions alone is NOT enough reason to make a term negative.
        - Never classify a Search Term with Conversions greater than 0 as ADD AS NEGATIVE.
        - Never recommend an offered service category as an account-level negative.
        - Caretaker agency, caregiver agency and similar service-provider intent are relevant.
        - ICU care at home, dressing nurse, bedside care and medical support at home must be REVIEW or MOVE TO CORRECT CAMPAIGN unless clearly irrelevant.
        - Baby Care, Babysitter or Nanny intent in a non-Baby-Care campaign = MOVE TO CORRECT CAMPAIGN.
        - Nursing Care intent in a non-Nursing-Care campaign = MOVE TO CORRECT CAMPAIGN.
        - Patient Care intent in a non-Patient-Care campaign = MOVE TO CORRECT CAMPAIGN.
        - Elderly Care intent in a non-Elderly-Care campaign = MOVE TO CORRECT CAMPAIGN.
        - Search Terms targeting a city outside the intended location = REVIEW - GEO MISMATCH.
        - Relevant high-intent terms = KEEP.
        - Uncertain terms = REVIEW.
        - ADD AS NEGATIVE only when intent is clearly outside ALL advertiser services.
        - Never show the same Search Term more than once.
        - Duplicate Search Terms have been combined where possible.
        - A Search Term can appear in only ONE final category.
        - Doctor-at-home / doctor visit intent is outside the advertiser's listed services and may be ADD AS NEGATIVE when clearly doctor-service intent.
        - Old-age-home / residential facility intent is different from Elderly Care at Home and may be ADD AS NEGATIVE when clearly facility intent.

        Classification priority:
        1. KEEP if relevant and converted
        2. MOVE TO CORRECT CAMPAIGN if it belongs to another offered service
        3. REVIEW if uncertain or geo mismatch
        4. ADD AS NEGATIVE only if clearly irrelevant

        For negative keyword analysis return exactly:
        1. ADD AS NEGATIVE
        2. MOVE TO CORRECT CAMPAIGN
        3. REVIEW
        4. KEEP

        RESPONSE STYLE:
        - Answer the user's exact question first.
        - Be practical and concise.
        - Use ₹ for money.
        - Use clear markdown tables where useful.
        - Highlight CTR, CPC, CPA, Cost and Conversions where relevant.
        - Explain problems clearly.
        - Finish with 3 priority actions.
        - Show the 4-section negative keyword analysis ONLY when the USER QUESTION specifically asks about negative keywords or search-term classification.
        - For general performance questions, do NOT include ADD AS NEGATIVE / MOVE TO CORRECT CAMPAIGN / REVIEW / KEEP sections.
        - For general performance questions, focus on Overall Performance, Campaign Performance, Key Problems, Opportunities and 3 Priority Actions.

        SELECTED DATE RANGE:
        {date_option}

        DATE FILTER:
        {date_filter_clause}

        CAMPAIGN DATA:
        {filtered_df.to_string(index=False)}

        SEARCH TERMS DATA:
        {search_terms_context}

        BEFORE VS AFTER DATA:
        {before_after_context}

        OVERALL METRICS:
        Impressions: {total_impressions}
        Clicks: {total_clicks}
        Cost: ₹{total_cost:.2f}
        Conversions: {total_conversions:.2f}
        CTR: {overall_ctr:.2f}%
        Average CPC: ₹{overall_cpc:.2f}
        CPA: ₹{overall_cpa:.2f}
        Conversion Rate: {overall_conversion_rate:.2f}%

        USER QUESTION:
        {question}

        Answer the USER QUESTION using only the supplied data.
        """

                    # ==================================================
                    # OPENAI
                    # ==================================================

                    with st.spinner("AI is analyzing..."):

                        ai_response = openai_client.responses.create(
                            model="gpt-5.4-mini",
                            input=prompt
                        )

                    assistant_text = ai_response.output_text

                # ==================================================
                # SAVE RESPONSE
                # ==================================================

                st.session_state.ai_chat_history.append(
                    {
                        "role": "assistant",
                        "content": assistant_text
                    }
                )

                # ==================================================
                # SHOW CURRENT ANSWER
                # ==================================================

                st.markdown("### 🤖 Google Ads AI")

                with st.chat_message("user"):
                    st.markdown(question)

                with st.chat_message("assistant"):
                    st.markdown(assistant_text)

            else:
                st.warning("Please enter a question.")

except Exception as e:
    st.error(f"Dashboard Error: {e}")
