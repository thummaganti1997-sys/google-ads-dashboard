import streamlit as st
from google.ads.googleads.client import GoogleAdsClient

st.set_page_config(page_title="Google Ads Dashboard", layout="wide")

st.title("Google Ads Dashboard")

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

    query = """
        SELECT
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions
        FROM campaign
        WHERE segments.date DURING LAST_30_DAYS
        ORDER BY metrics.cost_micros DESC
    """

    response = ga_service.search(
        customer_id=customer_id,
        query=query
    )

    st.success("Google Ads Connected Successfully! 🎉")

    data = []

    for row in response:
        data.append({
            "Campaign": row.campaign.name,
            "Status": row.campaign.status.name,
            "Impressions": row.metrics.impressions,
            "Clicks": row.metrics.clicks,
            "Cost (₹)": round(row.metrics.cost_micros / 1_000_000, 2),
            "Conversions": round(row.metrics.conversions, 2),
        })

    if data:
        total_impressions = sum(item["Impressions"] for item in data)
        total_clicks = sum(item["Clicks"] for item in data)
        total_cost = sum(item["Cost (₹)"] for item in data)
        total_conversions = sum(item["Conversions"] for item in data)

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
        col4.metric("Conversions", f"{total_conversions:,.2f}")
        col5.metric("CTR", f"{ctr:.2f}%")
        col6.metric("CPA", f"₹{cpa:.2f}")

        st.divider()

        st.subheader("Campaign Performance")

        st.dataframe(
            data,
            use_container_width=True
        )

    else:
        st.info("No campaign data found for the last 30 days.")

except Exception as e:
    st.error("Google Ads connection error")
    st.exception(e)
