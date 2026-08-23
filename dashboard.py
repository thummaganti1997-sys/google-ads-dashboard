import streamlit as st
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from openai import OpenAI

st.set_page_config(page_title="Google Ads AI Dashboard", layout="wide")

st.title("🤖 Google Ads AI Dashboard")

# ---------------- DATE FILTER ----------------

date_option = st.selectbox(
    "📅 Select Date Range",
    ["Today", "Last 7 Days", "Last 30 Days"]
)

date_range_map = {
    "Today": "TODAY",
    "Last 7 Days": "LAST_7_DAYS",
    "Last 30 Days": "LAST_30_DAYS"
}

date_range = date_range_map[date_option]

try:
    # ---------------- GOOGLE ADS CONNECTION ----------------

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

    # ---------------- CAMPAIGN QUERY ----------------

    query = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.cost_micros DESC
    """

    response = ga_service.search(
        customer_id=customer_id,
        query=query
    )

    data = []

    for row in response:
        data.append({
            "Campaign": row.campaign.name,
            "Status": row.campaign.status.name,
            "Impressions": row.metrics.impressions,
            "Clicks": row.metrics.clicks,
            "Cost (₹)": round(
                row.metrics.cost_micros / 1_000_000, 2
            ),
            "Conversions": round(
                row.metrics.conversions, 2
            )
        })

    st.success("Google Ads Connected Successfully! 🎉")

    if data:

        df = pd.DataFrame(data)

        # ---------------- SUMMARY METRICS ----------------

        total_impressions = df["Impressions"].sum()
        total_clicks = df["Clicks"].sum()
        total_cost = df["Cost (₹)"].sum()
        total_conversions = df["Conversions"].sum()

        ctr = (
            total_clicks / total_impressions * 100
            if total_impressions else 0
        )

        cpa = (
            total_cost / total_conversions
            if total_conversions else 0
        )

        col1, col2, col3, col4, col5, col6 = st.columns(6)

        col1.metric("Impressions", f"{total_impressions:,}")
        col2.metric("Clicks", f"{total_clicks:,}")
        col3.metric("Cost", f"₹{total_cost:,.2f}")
        col4.metric("Conversions", f"{total_conversions:.2f}")
        col5.metric("CTR", f"{ctr:.2f}%")
        col6.metric("CPA", f"₹{cpa:,.2f}")

        st.divider()

        # ---------------- CAMPAIGN FILTER ----------------

        campaigns = ["All Campaigns"] + list(
            df["Campaign"].unique()
        )

        selected_campaign = st.selectbox(
            "🎯 Select Campaign",
            campaigns
        )

        if selected_campaign != "All Campaigns":
            filtered_df = df[
                df["Campaign"] == selected_campaign
            ]
        else:
            filtered_df = df

        st.subheader("📊 Campaign Performance")

        st.dataframe(
            filtered_df,
            use_container_width=True
        )

        st.divider()

        # ---------------- DAILY DATA ----------------

        daily_query = f"""
            SELECT
                segments.date,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM customer
            WHERE segments.date DURING {date_range}
            ORDER BY segments.date
        """

        daily_response = ga_service.search(
            customer_id=customer_id,
            query=daily_query
        )

        daily_data = []

        for row in daily_response:
            daily_data.append({
                "Date": str(row.segments.date),
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "Cost": round(
                    row.metrics.cost_micros / 1_000_000, 2
                ),
                "Conversions": round(
                    row.metrics.conversions, 2
                )
            })

        if daily_data:

            daily_df = pd.DataFrame(daily_data)

            daily_df["Date"] = pd.to_datetime(
                daily_df["Date"]
            )

            st.subheader("📈 Daily Performance")

            chart1, chart2 = st.columns(2)

            with chart1:
                st.write("Clicks per Day")

                st.line_chart(
                    daily_df.set_index("Date")["Clicks"]
                )

            with chart2:
                st.write("Cost per Day")

                st.line_chart(
                    daily_df.set_index("Date")["Cost"]
                )

            st.write("Conversions per Day")

            st.line_chart(
                daily_df.set_index("Date")["Conversions"]
            )

        st.divider()

        # ---------------- AI CAMPAIGN ANALYSIS ----------------

        st.header("🤖 Ask AI About Your Campaign")

        question = st.text_input(
            "Ask a question about your Google Ads campaigns",
            placeholder="Example: Why is my CPA high?"
        )

        if st.button("Analyze with AI"):

            if question:

                openai_client = OpenAI(
                    api_key=st.secrets["openai"]["api_key"]
                )

                campaign_data = filtered_df.to_string(
                    index=False
                )

                prompt = f"""
You are a professional Google Ads expert.

Analyze the following Google Ads campaign data:

{campaign_data}

Overall metrics:
Impressions: {total_impressions}
Clicks: {total_clicks}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {ctr:.2f}%
CPA: ₹{cpa:.2f}

User question:
{question}

Give a clear answer with:
1. Performance analysis
2. Possible reasons
3. Specific recommendations
4. What should be changed first

Keep the answer practical and easy to understand.
"""

                with st.spinner("AI is analyzing your campaigns..."):

                    response = openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=prompt
                    )

                    st.subheader("🤖 AI Analysis")

                    st.write(response.output_text)

            else:
                st.warning("Please enter a question.")

    else:
        st.info(
            f"No campaign data found for {date_option}."
        )

except Exception as e:
    st.error("Dashboard error")
    st.exception(e)
