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
        st.dataframe(data, use_container_width=True)
    else:
        st.info("No campaign data found for the last 30 days.")

except Exception as e:
    st.error("Google Ads connection error")
    st.exception(e)
