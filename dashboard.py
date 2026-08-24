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
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="dashboard-banner">
    <h1>🤖 Google Ads AI Dashboard</h1>
    <p>Smart Performance • AI Insights • Budget Optimization</p>
</div>
""", unsafe_allow_html=True)

# ==================================================
# DATE FILTER
# ==================================================

date_option = st.selectbox(
    "📅 Select Date Range",
    [
        "Today",
        "Last 7 Days",
        "Last 30 Days",
        "Last 90 Days",
       "Last 6 Months",
        "Last 1 Year",
       "Custom Date Range"
        
    ]
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

    if len(custom_dates) == 2:
        start_date, end_date = custom_dates

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
            use_container_width=True
        )

        st.divider()


        # ==================================================
        # CAMPAIGN COMPARISON
        # ==================================================

        st.header("📈 Campaign Comparison")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:

            st.subheader("Clicks by Campaign")

            click_chart = filtered_df[
                ["Campaign", "Clicks"]
            ].set_index("Campaign")

            st.bar_chart(
                click_chart,
                use_container_width=True
            )

            st.subheader("Conversions by Campaign")

            conversion_chart = filtered_df[
                ["Campaign", "Conversions"]
            ].set_index("Campaign")

            st.bar_chart(
                conversion_chart,
                use_container_width=True
            )


        with chart_col2:

            st.subheader("Cost by Campaign")

            cost_chart = filtered_df[
                ["Campaign", "Cost (₹)"]
            ].set_index("Campaign")

            st.bar_chart(
                cost_chart,
                use_container_width=True
            )

            st.subheader("Clicks vs Conversions")

            comparison_chart = filtered_df[
                [
                    "Campaign",
                    "Clicks",
                    "Conversions"
                ]
            ].set_index("Campaign")

            st.bar_chart(
                comparison_chart,
                use_container_width=True
            )


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
        )# ==================================================
# DAILY PERFORMANCE
# ==================================================
except Exception as e:
    st.error(f"Error: {e}")
st.divider()
st.header("📅 Daily Performance")

try:

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

        impressions = int(row.metrics.impressions or 0)
        clicks = int(row.metrics.clicks or 0)
        cost = float(row.metrics.cost_micros or 0) / 1_000_000
        conversions = float(row.metrics.conversions or 0)

        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpc = (cost / clicks) if clicks > 0 else 0
        cpa = (cost / conversions) if conversions > 0 else 0

        daily_data.append({
            "Date": str(row.segments.date),
            "Impressions": impressions,
            "Clicks": clicks,
            "Cost": round(cost, 2),
            "Conversions": round(conversions, 2),
            "CTR": round(ctr, 2),
            "CPC": round(cpc, 2),
            "CPA": round(cpa, 2)
        })

    if daily_data:

        daily_df = pd.DataFrame(daily_data)

        # Convert date correctly
        daily_df["Date"] = pd.to_datetime(
            daily_df["Date"],
            errors="coerce"
        )

        # Remove invalid dates
        daily_df = daily_df.dropna(subset=["Date"])

        # Sort dates correctly
        daily_df = daily_df.sort_values("Date")

        # Set Date as index
        daily_df = daily_df.set_index("Date")

        # --------------------------
        # ROW 1
        # --------------------------

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Clicks per Day")
            st.line_chart(
                daily_df["Clicks"],
                use_container_width=True
            )

        with col2:
            st.subheader("Cost per Day")
            st.line_chart(
                daily_df["Cost"],
                use_container_width=True
            )

        # --------------------------
        # ROW 2
        # --------------------------

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("CTR per Day")
            st.line_chart(
                daily_df["CTR"],
                use_container_width=True
            )

        with col4:
            st.subheader("CPC per Day")
            st.line_chart(
                daily_df["CPC"],
                use_container_width=True
            )

        # --------------------------
        # ROW 3
        # --------------------------

        col5, col6 = st.columns(2)

        with col5:
            st.subheader("Conversions per Day")
            st.line_chart(
                daily_df["Conversions"],
                use_container_width=True
            )

        with col6:
            st.subheader("CPA per Day")
            st.line_chart(
                daily_df["CPA"],
                use_container_width=True
            )

        # --------------------------
        # TABLE
        # --------------------------

        st.subheader("Daily Performance Table")

        st.dataframe(
            daily_df.reset_index(),
            use_container_width=True
        )

    else:

        st.warning(
            "No daily performance data available for the selected date range."
        )

except Exception as e:

    st.error(
        f"Daily Performance Error: {e}"
    )


st.divider()

st.header("🔍 Search Terms Analysis")

try:

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

        impressions = int(row.metrics.impressions or 0)
        clicks = int(row.metrics.clicks or 0)

        cost = (
            float(row.metrics.cost_micros or 0)
            / 1_000_000
        )

        conversions = float(
            row.metrics.conversions or 0
        )

        search_data.append({
            "Search Term": row.search_term_view.search_term,
            "Campaign": row.campaign.name,
            "Impressions": impressions,
            "Clicks": clicks,
            "Cost (₹)": round(cost, 2),
            "Conversions": round(conversions, 2)
        })

    if search_data:

        search_df = pd.DataFrame(search_data)

        st.dataframe(
            search_df,
            use_container_width=True
        )

    else:

        search_df = pd.DataFrame()

        st.info(
            "No search terms found for the selected date range."
        )

except Exception as e:

    search_df = pd.DataFrame()

    st.error(
        f"Search Terms Error: {e}"
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
            use_container_width=True
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
            use_container_width=True,
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
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No campaign data available for budget optimization."
    )
       
    # ------------------------------------------
    # PAUSE / REDUCE KEYWORDS
    # ------------------------------------------

    st.subheader(
        "🔴 Keywords Needing Attention"
    )

    attention_df = keyword_recommendation_df[
        keyword_recommendation_df["Action"].isin(
            [
                "🔴 Pause / Reduce",
                "🟠 Review"
            ]
        )
    ].copy()

    if not attention_df.empty:

        st.dataframe(
            attention_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "No keywords currently need major attention."
        )


    # ------------------------------------------
    # BEST KEYWORDS
    # ------------------------------------------

    st.subheader(
        "🟢 Recommended Keywords to Keep"
    )

    best_keyword_df = keyword_recommendation_df[
        keyword_recommendation_df["Action"]
        == "🟢 Keep / Increase"
    ].copy()

    if not best_keyword_df.empty:

        st.dataframe(
            best_keyword_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No strong winning keywords found yet."
        )




        # ------------------------------------------
        # WASTE KEYWORDS
        # ------------------------------------------

        st.subheader(
            "🚨 High Spend + Zero Conversion Keywords"
        )

      

    keyword_df["Status"] == "🔴 Waste"



    waste_keywords_df = waste_keywords_df.sort_values(
        "Cost (₹)",
        ascending=False
    )

    st.dataframe(
        waste_keywords_df,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# AI NEGATIVE KEYWORD RECOMMENDATIONS
# ==================================================

st.divider()
st.header("🚫 AI Negative Keyword Recommendations")

if "search_df" in locals() and not search_df.empty:

    negative_candidates = search_df[
        (search_df["Conversions"] == 0)
        &
        (search_df["Cost (₹)"] > 0)
    ].copy()

    if not negative_candidates.empty:

        negative_candidates = negative_candidates.sort_values(
            "Cost (₹)",
            ascending=False
        )

        st.dataframe(
            negative_candidates[
                [
                    "Search Term",
                    "Campaign",
                    "Clicks",
                    "Cost (₹)",
                    "Conversions"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

        if st.button(
            "Generate AI Negative Keyword Suggestions",
            key="negative_keyword_ai_button"
        ):

            negative_context = negative_candidates.head(
                30
            ).to_string(index=False)

            negative_prompt = f"""
You are a senior Google Ads search-term optimization specialist.

Business:
Home care services.

Search terms with spend and zero conversions:

{negative_context}

Analyze carefully.

For each relevant search term, decide:

1. KEEP
2. REVIEW
3. ADD AS NEGATIVE

Return a clear table with:

Search Term
Spend
Clicks
Recommended Action
Suggested Negative Keyword
Suggested Match Type
Reason
Priority

Important rules:

- Do not recommend negative keywords only because they have zero conversions.
- Protect high-intent home care, patient care, nursing care, elderly care and caretaker searches.
- Recommend negatives mainly for irrelevant intent such as jobs, salary, course, training, free, hospital-only intent, unrelated locations, directories, competitors, informational searches, or unrelated services.
- Avoid blocking valuable customer searches.
- Clearly explain why each term should or should not be blocked.
"""

            with st.spinner(
                "AI is checking negative keyword opportunities..."
            ):

                negative_ai_response = (
                    openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=negative_prompt
                    )
                )

            st.subheader(
                "🤖 AI Negative Keyword Analysis"
            )

            st.write(
                negative_ai_response.output_text
            )

    else:

        st.success(
            "No zero-conversion search terms with spend found."
        )

else:

    st.info(
        "Search term data is not available."
    )

# ==================================================
# BEFORE VS AFTER PERFORMANCE
# ==================================================

st.divider()
st.header("📊 Before vs After Performance")

if "daily_df" in locals() and not daily_df.empty:

    compare_df = daily_df.copy()

    if "Date" not in compare_df.columns:
        compare_df = compare_df.reset_index()

    if "Date" not in compare_df.columns:
        compare_df = compare_df.rename(
            columns={compare_df.columns[0]: "Date"}
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

    if len(compare_df) >= 2:

        middle = len(compare_df) // 2

        before_df = compare_df.iloc[:middle].copy()
        after_df = compare_df.iloc[middle:].copy()

        before_start = before_df["Date"].iloc[0].strftime("%d %b %Y")
        before_end = before_df["Date"].iloc[-1].strftime("%d %b %Y")

        after_start = after_df["Date"].iloc[0].strftime("%d %b %Y")
        after_end = after_df["Date"].iloc[-1].strftime("%d %b %Y")

        st.caption(
            f"📅 Before: {before_start} → {before_end} | "
            f"After: {after_start} → {after_end}"
        )

        def period_summary(data):

            impressions = float(data["Impressions"].sum())
            clicks = float(data["Clicks"].sum())
            cost = float(data["Cost"].sum())
            conversions = float(data["Conversions"].sum())

            ctr = (
                clicks / impressions * 100
                if impressions > 0
                else 0
            )

            cpc = (
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
                "CPC": cpc,
                "CPA": cpa,
                "Conversion Rate": conversion_rate
            }

        before = period_summary(before_df)
        after = period_summary(after_df)

        comparison_data = pd.DataFrame({
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
                round(before["Impressions"], 0),
                round(before["Clicks"], 0),
                round(before["Cost"], 2),
                round(before["Conversions"], 2),
                round(before["CTR"], 2),
                round(before["CPC"], 2),
                round(before["CPA"], 2),
                round(before["Conversion Rate"], 2)
            ],
            "After": [
                round(after["Impressions"], 0),
                round(after["Clicks"], 0),
                round(after["Cost"], 2),
                round(after["Conversions"], 2),
                round(after["CTR"], 2),
                round(after["CPC"], 2),
                round(after["CPA"], 2),
                round(after["Conversion Rate"], 2)
            ]
        })

        st.dataframe(
            comparison_data,
            use_container_width=True,
            hide_index=True
        )

        if st.button(
            "🤖 Analyze Before vs After",
            key="before_after_ai_button"
        ):

            comparison_prompt = f"""
You are a senior Google Ads performance analyst.

BEFORE PERIOD:
{before_start} to {before_end}

{before}

AFTER PERIOD:
{after_start} to {after_end}

{after}

Explain:
1. What improved
2. What became worse
3. Spend change
4. Click change
5. CTR change
6. CPC change
7. Conversion change
8. CPA change
9. Whether performance improved
10. Top 5 actions to take next

Be practical and concise.
"""

            with st.spinner(
                "AI is comparing performance..."
            ):

                comparison_ai_response = (
                    openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=comparison_prompt
                    )
                )

            st.subheader(
                "🤖 Before vs After AI Analysis"
            )

            st.write(
                comparison_ai_response.output_text
            )

    else:

        st.info(
            "Not enough daily data to create a Before vs After comparison."
        )

else:

    st.info(
        "Daily performance data is not available."
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
        use_container_width=True,
        hide_index=True
    )

else:

    st.success(
        "🟢 No major actions required right now."
    )
    # ==================================================
# ONE-CLICK AI DAILY REPORT
# ==================================================

st.divider()
st.header("📋 One-Click AI Daily Report")
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
    "Generate Today's AI Report",
    key="daily_ai_report_button"
):

    waste_amount = 0

    if "waste_df" in locals() and not waste_df.empty:
        waste_amount = float(
            waste_df["Cost (₹)"].sum()
        )

    campaign_summary = (
        filtered_df.to_string(index=False)
        if "filtered_df" in locals()
        else "No campaign data available."
    )

    priority_summary = (
        priority_df.to_string(index=False)
        if "priority_df" in locals()
        else "No priority action data available."
    )

    daily_report_prompt = f"""
You are a senior Google Ads performance manager.

Create a professional daily performance report for a home care services Google Ads account.

ACCOUNT SUMMARY

Impressions: {total_impressions}
Clicks: {total_clicks}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {overall_ctr:.2f}%
Average CPC: ₹{overall_cpc:.2f}
CPA: ₹{overall_cpa:.2f}
Conversion Rate: {overall_conversion_rate:.2f}%

Potential Waste Spend:
₹{waste_amount:.2f}

CAMPAIGN DATA:

{campaign_summary}

PRIORITY ACTIONS:

{priority_summary}

Create the report with these sections:

1. Executive Summary
2. What Is Working Well
3. Main Problems
4. Waste Spend Findings
5. Campaigns to Increase or Maintain
6. Campaigns to Reduce or Review
7. Keyword/Search Term Actions
8. Budget Recommendation
9. Conversion Improvement Actions
10. Top 5 Actions for Today

Be concise, practical, and action-oriented.
Do not recommend pausing relevant high-intent keywords only because they have zero conversions.
"""

    with st.spinner(
        "AI is preparing today's performance report..."
    ):

        daily_report_response = (
            openai_client.responses.create(
                model="gpt-5.4-mini",
                input=daily_report_prompt
            )
        )

   st.subheader(f"🤖 {report_period} AI Performance Report")

    st.write(
        daily_report_response.output_text
    )
st.divider()
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
# ASK AI
# ==================================================

st.header("🤖 Ask AI About Your Campaign")

question = st.text_input(
    "Ask a question about your campaigns",
    placeholder="Example: Why am I getting clicks but no conversions?"
)

if st.button("Analyze with AI"):

    if question:

        prompt = f"""
You are a professional Google Ads expert.

Campaign data:

{filtered_df.to_string(index=False)}

Overall metrics:

Impressions: {total_impressions}
Clicks: {total_clicks}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {overall_ctr:.2f}%
CPC: ₹{overall_cpc:.2f}
CPA: ₹{overall_cpa:.2f}
Conversion Rate: {overall_conversion_rate:.2f}%

User question:
{question}

Give:
1. Clear analysis
2. Problems
3. Recommendations
4. Priority action plan

Be practical and concise.
"""

        with st.spinner("AI is analyzing..."):

            ai_response = openai_client.responses.create(
                model="gpt-5.4-mini",
                input=prompt
            )

        st.subheader("🤖 AI Analysis")

        st.write(
            ai_response.output_text
        )

    else:

        st.warning(
            "Please enter a question."
        )
