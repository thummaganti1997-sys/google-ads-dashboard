import streamlit as st
import pandas as pd
from google.ads.googleads.client import GoogleAdsClient
from openai import OpenAI


# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="Google Ads AI Dashboard",
    layout="wide"
)

st.title("🤖 Google Ads AI Dashboard")


# ==================================================
# DATE FILTER
# ==================================================

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

    # ==================================================
    # GOOGLE ADS CONNECTION
    # ==================================================

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
        WHERE segments.date DURING {date_range}
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
            "Conversion Rate %": round(
                conversion_rate,
                2
            )
        })


    st.success("Google Ads Connected Successfully! 🎉")


    if campaign_data:

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
        # AI PERFORMANCE ALERTS
        # ==================================================

        st.header("🔔 Performance Alerts")

        alerts = []

        if total_conversions == 0 and total_cost > 0:
            alerts.append(
                f"🔴 You spent ₹{total_cost:,.2f} but recorded 0 conversions. Check conversion tracking and lead quality."
            )

        if overall_ctr < 3:
            alerts.append(
                f"🟡 CTR is low at {overall_ctr:.2f}%. Review ads and keywords."
            )

        elif overall_ctr >= 8:
            alerts.append(
                f"🟢 CTR is strong at {overall_ctr:.2f}%."
            )

        if overall_cpc > 50:
            alerts.append(
                f"🟡 Average CPC is ₹{overall_cpc:.2f}. Review expensive keywords and search terms."
            )

        waste_campaigns = df[
            (df["Cost (₹)"] > 0) &
            (df["Conversions"] == 0)
        ]

        if not waste_campaigns.empty:
            alerts.append(
                f"🔴 {len(waste_campaigns)} campaign(s) have spend but 0 conversions."
            )

        for alert in alerts:
            if "🔴" in alert:
                st.error(alert)

            elif "🟡" in alert:
                st.warning(alert)

            else:
                st.success(alert)

        st.divider()
        # ==================================================
        # CAMPAIGN FILTER
        # ==================================================

        campaign_list = [
            "All Campaigns"
        ] + list(df["Campaign"].unique())

        selected_campaign = st.selectbox(
            "🎯 Select Campaign",
            campaign_list
        )

        if selected_campaign == "All Campaigns":

            filtered_df = df.copy()
        else:
            filtered_df = df
     
             # ==================================================
        # CAMPAIGN PERFORMANCE SCORE
        # ==================================================
        selected_impressions = filtered_df["Impressions"].sum()
        selected_clicks = filtered_df["Clicks"].sum()
        selected_cost = filtered_df["Cost (₹)"].sum()
        selected_conversions = filtered_df["Conversions"].sum()

        selected_ctr = (
            selected_clicks / selected_impressions * 100
            if selected_impressions else 0
        )

        selected_cpc = (
            selected_cost / selected_clicks
            if selected_clicks else 0
        )

        selected_conversion_rate = (
            selected_conversions / selected_clicks * 100
            if selected_clicks else 0
        )

        # Score calculation

        performance_score = 0

        # CTR Score
        if selected_ctr >= 10:
            performance_score += 30
        elif selected_ctr >= 5:
            performance_score += 20
        elif selected_ctr >= 3:
            performance_score += 10

        # Conversion Rate Score
        if selected_conversion_rate >= 10:
            performance_score += 40
        elif selected_conversion_rate >= 5:
            performance_score += 30
        elif selected_conversion_rate >= 2:
            performance_score += 20
        elif selected_conversion_rate > 0:
            performance_score += 10

        # CPC Score
        if selected_cpc <= 30:
            performance_score += 30
        elif selected_cpc <= 50:
            performance_score += 20
        elif selected_cpc <= 70:
            performance_score += 10


        st.header("🎯 Campaign Performance Score")

        score_col1, score_col2, score_col3 = st.columns(3)

        score_col1.metric(
            "Performance Score",
            f"{performance_score}/100"
        )

        score_col2.metric(
            "CTR",
            f"{selected_ctr:.2f}%"
        )

        score_col3.metric(
            "Conversion Rate",
            f"{selected_conversion_rate:.2f}%"
        )


        if performance_score >= 70:
            st.success(
                "🟢 Excellent Performance"
            )

        elif performance_score >= 40:
            st.warning(
                "🟡 Average Performance – Optimization Needed"
            )

        else:
            st.error(
                "🔴 Poor Performance – Immediate Action Needed"
            )

        st.divider()
         


        st.header("📊 Campaign Performance")

        st.dataframe(
            filtered_df,
            use_container_width=True
        ) 
        
        st.divider()
except Exception as e:
    st.error(f"Error: {e}")
    
  # ==================================================
# CAMPAIGN CHARTS
# ==================================================

except Exception as e:
    st.error(f"Error: {e}")

# CAMPAIGN CHARTS

st.header("📈 Campaign Comparison")


        # ------------------------------------------
        # CONVERSIONS BY CAMPAIGN
        # ------------------------------------------

      

            st.subheader("Conversions by Campaign")

            conversion_chart = filtered_df[
                ["Campaign", "Conversions"]
            ].set_index("Campaign")

            st.bar_chart(
                conversion_chart,
                use_container_width=True
            )
# ==================================================
# CAMPAIGN CHARTS
# ==================================================

st.header("📈 Campaign Comparison")

if not filtered_df.empty:

    chart_col1, chart_col2 = st.columns(2)

    # ==============================================
    # LEFT COLUMN
    # ==============================================

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


    # ==============================================
    # RIGHT COLUMN
    # ==============================================

    with chart_col2:

        st.subheader("Cost by Campaign")

        cost_chart = filtered_df[
            ["Campaign", "Cost (₹)"]
        ].set_index("Campaign")

        st.bar_chart(
            cost_chart,
            use_container_width=True
        )


else:

    st.warning("Campaign data is not available.")


st.divider()

        # ------------------------------------------
        # CLICKS VS CONVERSIONS
        # ------------------------------------------

        with chart_col4:

            st.subheader("Clicks vs Conversions")

            comparison_chart = filtered_df[
                ["Campaign", "Clicks", "Conversions"]
            ].set_index("Campaign")

            st.bar_chart(
                comparison_chart,
                use_container_width=True
            )


    else:

        st.warning("Campaign data is not available.")


except Exception as e:

    st.error(f"Campaign Comparison Error: {e}")


st.divider() 
# =========================================
# DAILY DATA
# =========================================

st.divider()
except Exception as e:
    st.error(f"Error: {e}")

st.header("📅 Daily Performance")


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

        impressions = row.metrics.impressions
        clicks = row.metrics.clicks
        cost = row.metrics.cost_micros / 1_000_000
        conversions = row.metrics.conversions

        daily_ctr = (
            clicks / impressions * 100
            if impressions else 0
        )

        daily_cpc = (
            cost / clicks
            if clicks else 0
        )

        daily_cpa = (
            cost / conversions
            if conversions else 0
        )

        daily_data.append({
            "Date": str(row.segments.date),
            "Impressions": impressions,
            "Clicks": clicks,
            "Cost": round(cost, 2),
            "Conversions": round(conversions, 2),
            "CTR": round(daily_ctr, 2),
            "CPC": round(daily_cpc, 2),
            "CPA": round(daily_cpa, 2)
        })

    if daily_data:

        daily_df = pd.DataFrame(daily_data)

        daily_df["Date"] = pd.to_datetime(
            daily_df["Date"]
        )

        daily_df = daily_df.set_index("Date")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Clicks per Day")
            st.line_chart(daily_df["Clicks"])

        with col2:
            st.subheader("Cost per Day")
            st.line_chart(daily_df["Cost"])

        col3, col4 = st.columns(2)

        with col3:
            st.subheader("CTR per Day")
            st.line_chart(daily_df["CTR"])

        with col4:
            st.subheader("CPC per Day")
            st.line_chart(daily_df["CPC"])

        col5, col6 = st.columns(2)

        with col5:
            st.subheader("Conversions per Day")
            st.line_chart(daily_df["Conversions"])

        with col6:
            st.subheader("CPA per Day")
            st.line_chart(daily_df["CPA"])

        st.subheader("Daily Performance Table")
        st.dataframe(
            daily_df.reset_index(),
            use_container_width=True
        )

    else:
        st.warning("Daily performance data is not available.")


             # ==================================================
        # DAILY PERFORMANCE
        # ==================================================



# DAILY DATA
if daily_data:
    daily_df = pd.DataFrame(daily_data)

    daily_df["Date"] = pd.to_datetime(daily_df["Date"])

    daily_df = daily_df.set_index("Date")


            st.header("📅 Daily Performance")

            st.subheader("Clicks per Day")
            st.line_chart(daily_df["Clicks"])

            st.subheader("Cost per Day")
            st.line_chart(daily_df["Cost"])

            st.subheader("CTR per Day")
            st.line_chart(daily_df["CTR"])

            st.subheader("CPC per Day")
            st.line_chart(daily_df["CPC"])

            st.subheader("Conversions per Day")
            st.line_chart(daily_df["Conversions"])
            st.header("📅 Daily Performance")


            col1, col2 = st.columns(2)

            with col1:

                st.write("Clicks per Day")

                st.line_chart(
                    daily_df["Clicks"]
                )

            with col2:

                st.write("Cost per Day")

                st.line_chart(
                    daily_df["Cost"]
                )


            col3, col4 = st.columns(2)

            with col3:

                st.write("CTR per Day")

                st.line_chart(
                    daily_df["CTR"]
                )

            with col4:

                st.write("CPC per Day")

                st.line_chart(
                    daily_df["CPC"]
                )


            st.write("Conversions per Day")

            st.line_chart(
                daily_df["Conversions"]
            )


        st.divider()


        # ==================================================
        # SEARCH TERMS ANALYSIS
        # ==================================================

        st.header("🔍 Search Terms Analysis")

        search_query = f"""
            SELECT
                search_term_view.search_term,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM search_term_view
            WHERE segments.date DURING {date_range}
            ORDER BY metrics.cost_micros DESC
            LIMIT 100
        """

        search_response = ga_service.search(
            customer_id=customer_id,
            query=search_query
        )

        search_data = []

        for row in search_response:

            search_data.append({
                "Search Term": row.search_term_view.search_term,
                "Campaign": row.campaign.name,
                "Impressions": row.metrics.impressions,
                "Clicks": row.metrics.clicks,
                "Cost (₹)": round(
                    row.metrics.cost_micros / 1_000_000,
                    2
                ),
                "Conversions": round(
                    row.metrics.conversions,
                    2
                )
            })


        if search_data:

            search_df = pd.DataFrame(search_data)

            st.dataframe(
                search_df,
                use_container_width=True
            )

        else:

            st.info(
                "No search term data found for this period."
            )


        st.divider()


        # ==================================================
        # WASTE SPEND DETECTION
        # ==================================================

        st.header("💸 Potential Waste Spend")

        if search_data:

            waste_df = search_df[
                (search_df["Cost (₹)"] > 0) &
                (search_df["Conversions"] == 0)
            ].copy()

            if not waste_df.empty:

                waste_df = waste_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

                st.warning(
                    "These search terms have spend but no conversions."
                )

                st.dataframe(
                    waste_df,
                    use_container_width=True
                )

            else:

                st.success(
                    "No obvious zero-conversion spend found."
                )


        st.divider()


        # ==================================================
        # ASK AI
        # ==================================================

        st.header("🤖 Ask AI About Your Campaign")

        question = st.text_input(
            "Ask a question about your Google Ads campaigns",
            placeholder=(
                "Example: Why am I getting clicks but no conversions?"
            ),
            key="general_question"
        )

        if st.button(
            "Analyze with AI",
            key="analyze_button"
        ):

            if question:

                ai_campaign_data = filtered_df.to_string(
                    index=False
                )

                prompt = f"""
You are a professional Google Ads expert.

Analyze this campaign data:

{ai_campaign_data}

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
2. Possible causes
3. Specific recommendations
4. Priority action plan

Be practical and concise.
"""

                with st.spinner(
                    "AI is analyzing your campaign..."
                ):

                    ai_response = (
                        openai_client.responses.create(
                            model="gpt-5.4-mini",
                            input=prompt
                        )
                    )

                st.subheader("🤖 AI Analysis")

                st.write(
                    ai_response.output_text
                )

            else:

                st.warning(
                    "Please enter a question."
                )


        st.divider()


        # ==================================================
        # CAMPAIGN-WISE AI RECOMMENDATION
        # ==================================================

        st.header(
            "🎯 Campaign-wise AI Recommendations"
        )

        ai_campaign = st.selectbox(
            "Select campaign",
            list(df["Campaign"].unique()),
            key="ai_campaign_select"
        )

        if st.button(
            "Get AI Recommendation",
            key="campaign_ai_button"
        ):

            selected_data = df[
                df["Campaign"] == ai_campaign
            ]

            prompt = f"""
You are a Google Ads optimization expert.

Analyze this campaign:

{selected_data.to_string(index=False)}

Give:

1. Performance Summary
2. Main Problems
3. What Is Working Well
4. Budget Recommendation
5. Bidding Recommendation
6. Keyword Recommendation
7. Conversion Improvement Plan
8. Top 3 Actions to Take Now

Keep it practical.
"""

            with st.spinner(
                "AI is preparing recommendations..."
            ):

                recommendation_response = (
                    openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=prompt
                    )
                )

            st.subheader(
                "🤖 AI Campaign Recommendation"
            )

            st.write(
                recommendation_response.output_text
            )


        st.divider()


        # ==================================================
        # AI KEYWORD + NEGATIVE KEYWORDS
        # ==================================================

        st.header(
            "🔑 AI Keyword & Negative Keyword Suggestions"
        )

        keyword_campaign = st.selectbox(
            "Select campaign for keyword analysis",
            list(df["Campaign"].unique()),
            key="keyword_campaign_select"
        )

        if st.button(
            "Get Keyword Suggestions",
            key="keyword_button"
        ):

            selected_keyword_data = df[
                df["Campaign"] == keyword_campaign
            ]

            search_context = ""

            if search_data:

                campaign_search_terms = search_df[
                    search_df["Campaign"] == keyword_campaign
                ]

                search_context = campaign_search_terms.to_string(
                    index=False
                )

            keyword_prompt = f"""
You are a Google Ads keyword specialist.

Business type: Homecare services.

Campaign data:

{selected_keyword_data.to_string(index=False)}

Search term data:

{search_context}

Provide:

1. High-intent keywords to add
2. Long-tail keywords
3. Exact match keywords
4. Phrase match keywords
5. Negative keywords
6. Search terms that may waste budget
7. Top 10 keywords to test first

Clearly separate positive and negative keywords.

Focus on generating genuine customer calls and leads.
"""

            with st.spinner(
                "AI is generating keyword suggestions..."
            ):

                keyword_response = (
                    openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=keyword_prompt
                    )
                )

            st.subheader(
                "🔑 AI Keyword Recommendations"
            )

            st.write(
                keyword_response.output_text
            )


        st.divider()


        # ==================================================
        # DAILY AI OPTIMIZATION
        # ==================================================

        st.header(
            "⚡ AI Optimization Plan"
        )

        if st.button(
            "What Should I Optimize Today?",
            key="daily_optimization_button"
        ):

            search_summary = (
                search_df.head(20).to_string(index=False)
                if search_data else
                "No search term data available."
            )

            optimization_prompt = f"""
You are a senior Google Ads optimization expert.

Analyze the account performance below.

Campaign data:

{df.to_string(index=False)}

Overall:
Impressions: {total_impressions}
Clicks: {total_clicks}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {overall_ctr:.2f}%
CPC: ₹{overall_cpc:.2f}
CPA: ₹{overall_cpa:.2f}
Conversion Rate: {overall_conversion_rate:.2f}%

Top search terms:

{search_summary}

Give a prioritized action plan:

1. STOP or reduce waste
2. Keywords to add
3. Negative keywords to add
4. Campaigns to increase budget
5. Campaigns to reduce budget
6. Bidding changes
7. Conversion tracking issues to check
8. Top 5 actions to do today

Be specific and practical.
"""

            with st.spinner(
                "AI is creating your optimization plan..."
            ):

                optimization_response = (
                    openai_client.responses.create(
                        model="gpt-5.4-mini",
                        input=optimization_prompt
                    )
                )

            st.subheader(
                "⚡ Today's AI Action Plan"
            )

            st.write(
                optimization_response.output_text
            )


    else:

        st.info(
            f"No campaign data found for {date_option}."
        )


except Exception as e:

    st.error("Dashboard error")

    st.exception(e)
