        # ---------------- KEYWORD AI RECOMMENDATIONS ----------------

        st.divider()

        st.header("🔑 AI Keyword Recommendations")

        keyword_campaign = st.selectbox(
            "Select a campaign for keyword suggestions",
            df["Campaign"].unique(),
            key="keyword_campaign"
        )

        if st.button("Get Keyword Suggestions"):

            campaign_keywords_data = df[
                df["Campaign"] == keyword_campaign
            ].to_string(index=False)

            openai_client = OpenAI(
                api_key=st.secrets["openai"]["api_key"]
            )

            keyword_prompt = f"""
You are an expert Google Ads keyword strategist.

Analyze this Google Ads campaign:

{campaign_keywords_data}

The business provides homecare services.

Give practical recommendations in these sections:

1. High Intent Keywords
Suggest keywords likely to generate calls or leads.

2. Long Tail Keywords
Suggest detailed, high-intent search keywords.

3. Exact Match Keywords
Give recommended keywords using [exact match] format.

4. Phrase Match Keywords
Give recommended keywords using "phrase match" format.

5. Negative Keywords
Suggest irrelevant keywords that may waste budget.

6. Keywords to Avoid
Identify low-quality or low-intent keywords.

7. Top 10 Keywords to Add
Give the best 10 keywords to test first.

Focus on homecare lead generation.
Keep the answer practical, clear, and easy to understand.
"""

            with st.spinner(
                "AI is generating keyword suggestions..."
            ):

                keyword_response = openai_client.responses.create(
                    model="gpt-5.4-mini",
                    input=keyword_prompt
                )

                st.subheader("🔑 AI Keyword Suggestions")

                st.write(keyword_response.output_text)
