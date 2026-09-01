import streamlit as st
import pandas as pd
import hashlib
import json
import re
from datetime import date, timedelta
from urllib.parse import urlparse
from uuid import uuid4
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from openai import OpenAI


# ==================================================
# AI CAMPAIGN BUILDER HELPERS
# ==================================================

CAMPAIGN_BUILDER_LANGUAGE_IDS = {
    "English": "1000",
    "Hindi": "1023",
    "Telugu": "1131",
}

CAMPAIGN_BUILDER_PROTECTED_NEGATIVE_PHRASES = (
    "hare krishna",
    "harekrishna",
    "home care",
    "homecare",
    "patient care",
    "elderly care",
    "nursing care",
    "nurse at home",
    "home nurse",
    "caretaker",
    "care taker",
    "caregiver",
    "baby care",
    "babysitter",
    "nanny",
    "maid",
    "domestic help",
    "housekeeping",
    "cook",
)


def campaign_builder_clip_text(value, limit):
    """Trim text safely to the requested Google Ads character limit."""
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(value) <= limit:
        return value

    clipped = value[:limit].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0].rstrip()

    return clipped or value[:limit].strip()


def campaign_builder_dedupe_strings(values, limit, max_items):
    """Clean, de-duplicate and cap a list of strings."""
    cleaned = []
    seen = set()

    for value in values or []:
        item = campaign_builder_clip_text(value, limit)
        key = item.casefold()

        if not item or key in seen:
            continue

        seen.add(key)
        cleaned.append(item)

        if len(cleaned) >= max_items:
            break

    return cleaned


def campaign_builder_extract_json(text):
    """Extract the first JSON object from an AI response."""
    raw = str(text or "").strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)

    start = raw.find("{")
    end = raw.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI did not return a valid JSON object.")

    return json.loads(raw[start:end + 1])


def campaign_builder_normalize_match_type(value, default="PHRASE"):
    match_type = str(value or default).strip().upper()
    if match_type not in {"EXACT", "PHRASE", "BROAD"}:
        return default
    return match_type


def campaign_builder_clean_keyword_rows(rows, max_items=20, negative=False):
    """Normalize keyword dictionaries and protect core services from negatives."""
    cleaned = []
    seen = set()

    for row in rows or []:
        if isinstance(row, str):
            text = row
            match_type = "PHRASE"
        elif isinstance(row, dict):
            text = row.get("text", "")
            match_type = row.get("match_type", "PHRASE")
        else:
            continue

        text = campaign_builder_clip_text(text, 80)
        text = re.sub(r"\s+", " ", text).strip()

        if not text or len(text.split()) > 10:
            continue

        lower_text = text.casefold()

        if negative and any(
            protected in lower_text
            for protected in CAMPAIGN_BUILDER_PROTECTED_NEGATIVE_PHRASES
        ):
            continue

        dedupe_key = lower_text
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        cleaned.append(
            {
                "text": text,
                "match_type": campaign_builder_normalize_match_type(
                    match_type,
                    default="PHRASE"
                ),
            }
        )

        if len(cleaned) >= max_items:
            break

    return cleaned


def campaign_builder_fallback_headlines(service, location):
    return campaign_builder_dedupe_strings(
        [
            f"{service} At Home",
            f"{service} {location}",
            "Home Care Support",
            "Call For Care Services",
            "Care At Your Home",
        ],
        limit=30,
        max_items=15,
    )


def campaign_builder_fallback_descriptions(service, location):
    return campaign_builder_dedupe_strings(
        [
            f"Get {service.lower()} support at home in {location}. Call to check availability.",
            "Home care staff support for families. Enquire now for service availability.",
        ],
        limit=90,
        max_items=4,
    )


def campaign_builder_sanitize_path(value):
    value = str(value or "").strip().lower()
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value[:15]


def campaign_builder_sanitize_draft(raw_draft, service, location):
    """Return a policy-conscious, length-safe campaign draft."""
    raw_draft = raw_draft if isinstance(raw_draft, dict) else {}

    headlines = campaign_builder_dedupe_strings(
        raw_draft.get("headlines", []),
        limit=30,
        max_items=15,
    )
    descriptions = campaign_builder_dedupe_strings(
        raw_draft.get("descriptions", []),
        limit=90,
        max_items=4,
    )

    for fallback in campaign_builder_fallback_headlines(service, location):
        if len(headlines) >= 3:
            break
        if fallback.casefold() not in {item.casefold() for item in headlines}:
            headlines.append(fallback)

    for fallback in campaign_builder_fallback_descriptions(service, location):
        if len(descriptions) >= 2:
            break
        if fallback.casefold() not in {item.casefold() for item in descriptions}:
            descriptions.append(fallback)

    keywords = campaign_builder_clean_keyword_rows(
        raw_draft.get("keywords", []),
        max_items=20,
        negative=False,
    )
    negatives = campaign_builder_clean_keyword_rows(
        raw_draft.get("negative_keywords", []),
        max_items=15,
        negative=True,
    )

    if not keywords:
        keywords = campaign_builder_clean_keyword_rows(
            [
                {"text": f"{service} at home", "match_type": "PHRASE"},
                {"text": f"{service} services", "match_type": "PHRASE"},
                {"text": f"{service} {location}", "match_type": "EXACT"},
            ],
            max_items=20,
            negative=False,
        )

    ad_group_name = campaign_builder_clip_text(
        raw_draft.get("ad_group_name") or f"{service} - High Intent",
        255,
    )

    return {
        "ad_group_name": ad_group_name,
        "keywords": keywords,
        "negative_keywords": negatives,
        "headlines": headlines[:15],
        "descriptions": descriptions[:4],
        "path1": campaign_builder_sanitize_path(
            raw_draft.get("path1") or service
        ),
        "path2": campaign_builder_sanitize_path(
            raw_draft.get("path2") or location
        ),
    }


def campaign_builder_parse_keyword_lines(text, negative=False):
    rows = []

    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            keyword_text, match_type = line.rsplit("|", 1)
        else:
            keyword_text, match_type = line, "PHRASE"

        rows.append(
            {
                "text": keyword_text.strip(),
                "match_type": match_type.strip(),
            }
        )

    return campaign_builder_clean_keyword_rows(
        rows,
        max_items=15 if negative else 20,
        negative=negative,
    )


def campaign_builder_keyword_lines(rows):
    return "\n".join(
        f"{row.get('text', '')} | {row.get('match_type', 'PHRASE')}"
        for row in rows or []
    )


def campaign_builder_valid_url(url):
    try:
        parsed = urlparse(str(url or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def campaign_builder_fingerprint(payload):
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def campaign_builder_format_google_ads_error(error):
    if not isinstance(error, GoogleAdsException):
        return str(error)

    lines = [f"Request ID: {error.request_id}"]

    for item in error.failure.errors:
        message = getattr(item, "message", "Google Ads API error")
        field_names = []

        if getattr(item, "location", None):
            for element in item.location.field_path_elements:
                name = getattr(element, "field_name", "")
                if name:
                    field_names.append(name)

        if field_names:
            lines.append(f"{message} (Field: {' > '.join(field_names)})")
        else:
            lines.append(message)

    return "\n".join(lines)


def campaign_builder_resolve_location(client, location_text):
    """Resolve a typed Indian location to a Google geo target resource name."""
    geo_service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = "en"
    request.country_code = "IN"
    request.location_names.names.append(str(location_text).strip())

    response = geo_service.suggest_geo_target_constants(request=request)
    suggestions = list(response.geo_target_constant_suggestions)

    if not suggestions:
        raise ValueError(
            f"Google Ads could not resolve location: {location_text}"
        )

    requested = str(location_text).strip().casefold()
    exact = [
        item
        for item in suggestions
        if str(item.geo_target_constant.name).strip().casefold() == requested
    ]

    chosen = exact[0] if exact else suggestions[0]
    geo = chosen.geo_target_constant

    return {
        "resource_name": geo.resource_name,
        "name": geo.name,
        "canonical_name": geo.canonical_name,
        "target_type": geo.target_type,
        "country_code": geo.country_code,
    }


def campaign_builder_match_enum(client, match_type):
    match_type = campaign_builder_normalize_match_type(match_type)
    mapping = {
        "EXACT": client.enums.KeywordMatchTypeEnum.EXACT,
        "PHRASE": client.enums.KeywordMatchTypeEnum.PHRASE,
        "BROAD": client.enums.KeywordMatchTypeEnum.BROAD,
    }
    return mapping[match_type]


def campaign_builder_build_operations(client, customer_id, payload):
    """Build one atomic Search campaign with budget, targeting, keywords and RSA."""
    operations = []

    budget_service = client.get_service("CampaignBudgetService")
    campaign_service = client.get_service("CampaignService")
    ad_group_service = client.get_service("AdGroupService")

    budget_resource = budget_service.campaign_budget_path(customer_id, -1)
    campaign_resource = campaign_service.campaign_path(customer_id, -2)
    ad_group_resource = ad_group_service.ad_group_path(customer_id, -3)

    # 1. Campaign budget.
    mutate = client.get_type("MutateOperation")
    budget = mutate.campaign_budget_operation.create
    budget.resource_name = budget_resource
    budget.name = (
        f"{payload['campaign_name']} Budget {uuid4().hex[:8]}"
    )
    budget.amount_micros = int(round(float(payload["daily_budget"]) * 1_000_000))
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD
    operations.append(mutate)

    # 2. Search campaign - always PAUSED at creation for safety.
    mutate = client.get_type("MutateOperation")
    campaign = mutate.campaign_operation.create
    campaign.resource_name = campaign_resource
    campaign.name = campaign_builder_clip_text(payload["campaign_name"], 255)
    campaign.advertising_channel_type = (
        client.enums.AdvertisingChannelTypeEnum.SEARCH
    )
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    campaign.campaign_budget = budget_resource
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = False
    campaign.network_settings.target_partner_search_network = False
    campaign.network_settings.target_content_network = False
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum.
        DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
    )

    if payload["bidding_strategy"] == "Manual CPC":
        client.copy_from(campaign.manual_cpc, client.get_type("ManualCpc"))
    else:
        client.copy_from(
            campaign.maximize_conversions,
            client.get_type("MaximizeConversions"),
        )

    operations.append(mutate)

    # 3. Location targeting.
    mutate = client.get_type("MutateOperation")
    criterion = mutate.campaign_criterion_operation.create
    criterion.campaign = campaign_resource
    criterion.location.geo_target_constant = payload["location_resource_name"]
    operations.append(mutate)

    # 4. Language targeting.
    for language_id in payload["language_ids"]:
        mutate = client.get_type("MutateOperation")
        criterion = mutate.campaign_criterion_operation.create
        criterion.campaign = campaign_resource
        criterion.language.language_constant = f"languageConstants/{language_id}"
        operations.append(mutate)

    # 5. Campaign-level negative keywords.
    for row in payload["negative_keywords"]:
        mutate = client.get_type("MutateOperation")
        criterion = mutate.campaign_criterion_operation.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.keyword.text = row["text"]
        criterion.keyword.match_type = campaign_builder_match_enum(
            client,
            row["match_type"],
        )
        operations.append(mutate)

    # 6. Ad group.
    mutate = client.get_type("MutateOperation")
    ad_group = mutate.ad_group_operation.create
    ad_group.resource_name = ad_group_resource
    ad_group.name = campaign_builder_clip_text(payload["ad_group_name"], 255)
    ad_group.campaign = campaign_resource
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    if payload["bidding_strategy"] == "Manual CPC":
        ad_group.cpc_bid_micros = int(
            round(float(payload["manual_cpc_bid"]) * 1_000_000)
        )

    operations.append(mutate)

    # 7. Positive keywords.
    for row in payload["keywords"]:
        mutate = client.get_type("MutateOperation")
        ad_group_criterion = mutate.ad_group_criterion_operation.create
        ad_group_criterion.ad_group = ad_group_resource
        ad_group_criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        ad_group_criterion.keyword.text = row["text"]
        ad_group_criterion.keyword.match_type = campaign_builder_match_enum(
            client,
            row["match_type"],
        )
        operations.append(mutate)

    # 8. Responsive Search Ad.
    mutate = client.get_type("MutateOperation")
    ad_group_ad = mutate.ad_group_ad_operation.create
    ad_group_ad.ad_group = ad_group_resource
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED
    ad_group_ad.ad.final_urls.append(payload["final_url"])

    rsa = ad_group_ad.ad.responsive_search_ad
    headline_assets = []
    for text in payload["headlines"][:15]:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        headline_assets.append(asset)
    rsa.headlines.extend(headline_assets)

    description_assets = []
    for text in payload["descriptions"][:4]:
        asset = client.get_type("AdTextAsset")
        asset.text = text
        description_assets.append(asset)
    rsa.descriptions.extend(description_assets)

    if payload.get("path1"):
        rsa.path1 = payload["path1"]
    if payload.get("path2"):
        rsa.path2 = payload["path2"]

    operations.append(mutate)

    return operations


def campaign_builder_mutate(
    client,
    google_ads_service,
    customer_id,
    payload,
    validate_only,
):
    """Validate or atomically create the full campaign structure."""
    request = client.get_type("MutateGoogleAdsRequest")
    request.customer_id = customer_id
    request.partial_failure = False
    request.validate_only = bool(validate_only)
    request.mutate_operations.extend(
        campaign_builder_build_operations(client, customer_id, payload)
    )

    return google_ads_service.mutate(request=request)


# ==================================================
# GROWTH INTELLIGENCE HELPERS
# TOP KEYWORDS + SEARCH VOLUME + COMPETITORS
# ==================================================

GROWTH_OWN_BRAND_PHRASES = (
    "hare krishna",
    "harekrishna",
    "hare krishna home care",
    "harekrishna home care",
    "hare krishna home care services",
    "harekrishna home care services",
    "shiva kaartikeya",
    "shiva kartikeya",
    "shivakaartikeya",
    "shiva kaartikeya home care",
    "shivakaartikeya home care",
)

GROWTH_OWN_DOMAINS = (
    "hareekrishna.com",
    "harekrishna.com",
    "shivakaartikeya.com",
)

GROWTH_GENERIC_SERVICE_TOKENS = {
    "home", "care", "homecare", "service", "services", "elderly", "senior",
    "seniors", "old", "age", "aged", "patient", "patients", "nursing",
    "nurse", "nurses", "caretaker", "caretakers", "caregiver", "caregivers",
    "attendant", "attendants", "baby", "babysitter", "babysitters", "nanny",
    "nannies", "maid", "maids", "domestic", "help", "housekeeping",
    "housekeeper", "housekeepers", "cook", "cooks", "doctor", "doctors",
    "medical", "health", "support", "professional", "private", "personal",
    "bedridden", "surgery", "post", "skilled", "staff", "gnm", "anm",
    "at", "in", "for", "of", "the", "and", "to", "with", "from", "by",
    "near", "me", "my", "our", "your", "best", "top", "good", "available",
    "24", "7", "24x7", "hour", "hours", "day", "days", "daily", "monthly",
    "hyderabad", "secunderabad", "telangana", "india",
    "chintal", "suchitra", "jeedimetla", "shapur", "nagole", "uppal",
    "suraram", "quthbullapur", "kukatpally", "gachibowli", "madhapur",
    "banjara", "hills", "jubilee", "ameerpet", "begumpet", "kompally",
    "bachupally", "miyapur", "lingampally", "manikonda", "kondapur",
    "hitech", "city", "mehdipatnam", "tolichowki", "lb", "nagar",
}

GROWTH_BUSINESS_MARKERS = (
    "agency", "company", "pvt", "private limited", "ltd", "limited", "llp",
    "hospital", "clinic", "foundation", "trust", "solutions", "centre",
    "center", "nursing home", "old age home", "retirement home",
    "senior living", "assisted living", "rehab", "rehabilitation", "wellness",
)


def growth_normalize_text(value):
    value = str(value or "").casefold().strip()
    value = re.sub(r"https?://", "", value)
    value = re.sub(r"^www\.", "", value)
    value = re.sub(r"[^a-z0-9\s.-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def growth_normalize_keyword(value):
    value = growth_normalize_text(value)
    value = value.replace(".", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value).strip()


def growth_is_own_brand(value):
    term = growth_normalize_text(value)
    return any(brand in term for brand in GROWTH_OWN_BRAND_PHRASES)


def growth_is_own_domain(value):
    domain = growth_normalize_text(value).split("/")[0]
    return any(
        domain == own_domain or domain.endswith("." + own_domain)
        for own_domain in GROWTH_OWN_DOMAINS
    )


def growth_safe_float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return default
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def growth_percentage(value):
    """Convert Google Ads ratio-style percentage metrics to 0-100 values."""
    number = growth_safe_float(value, 0.0)
    return number * 100.0


def growth_enum_name(value):
    if value is None:
        return "UNSPECIFIED"
    name = getattr(value, "name", None)
    if name:
        return str(name)
    text = str(value)
    if "." in text:
        text = text.split(".")[-1]
    return text


def growth_competition_name(value):
    name = growth_enum_name(value)
    enum_map = {
        "0": "UNSPECIFIED",
        "1": "UNKNOWN",
        "2": "LOW",
        "3": "MEDIUM",
        "4": "HIGH",
    }
    return enum_map.get(name, name)


def growth_extract_json_array(text):
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI did not return a JSON array.")
    data = json.loads(raw[start:end + 1])
    if not isinstance(data, list):
        raise ValueError("AI competitor output was not a list.")
    return data


def growth_brand_candidate_score(search_term):
    term = growth_normalize_text(search_term)
    if not term or growth_is_own_brand(term):
        return -999

    cleaned = re.sub(r"[^a-z0-9]+", " ", term)
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        return -999

    unknown_tokens = [
        token
        for token in tokens
        if token not in GROWTH_GENERIC_SERVICE_TOKENS and not token.isdigit()
    ]

    score = len(set(unknown_tokens)) * 3

    if len(tokens) <= 4 and unknown_tokens:
        score += 2

    if any(marker in term for marker in GROWTH_BUSINESS_MARKERS):
        score += 5

    if any(
        marker in term
        for marker in ("phone number", "contact number", "address", "reviews", "review")
    ):
        score += 2

    return score


def growth_competitor_key(value):
    text = growth_normalize_text(value)
    text = re.sub(r"\.(com|in|org|net)$", "", text)
    text = re.sub(r"\b(pvt|private|ltd|limited|llp)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def growth_competitor_review_risk(spend, conversions, campaign_calls, reference_cpa, reference_cpc):
    """
    Conservative risk signal for competitor-brand search terms.
    A zero-conversion term is never automatically called confirmed waste.
    """
    spend = growth_safe_float(spend)
    conversions = growth_safe_float(conversions)
    campaign_calls = growth_safe_float(campaign_calls)
    reference_cpa = growth_safe_float(reference_cpa)
    reference_cpc = growth_safe_float(reference_cpc)

    if conversions > 0:
        return "🟢 LOW — Converted"

    if campaign_calls > 0:
        return "🟠 MEDIUM — Review (campaign has calls)"

    high_threshold = reference_cpa if reference_cpa > 0 else max(reference_cpc * 12, 1200)
    medium_threshold = max(reference_cpc * 6, 500)

    if spend >= high_threshold and spend > 0:
        return "🔴 HIGH — Review"
    if spend >= medium_threshold and spend > 0:
        return "🟠 MEDIUM — Review"
    return "🟡 LOW — Monitor"


def growth_keyword_signal(conversions, cost, cpa, benchmark_cpa, clicks):
    conversions = growth_safe_float(conversions)
    cost = growth_safe_float(cost)
    cpa = growth_safe_float(cpa)
    benchmark_cpa = growth_safe_float(benchmark_cpa)
    clicks = growth_safe_float(clicks)

    if conversions >= 3 and benchmark_cpa > 0 and cpa > 0 and cpa <= benchmark_cpa * 0.80:
        return "🚀 Scale Candidate"
    if conversions > 0 and (benchmark_cpa <= 0 or cpa <= benchmark_cpa * 1.20):
        return "✅ Strong"
    if conversions > 0:
        return "🟠 CPA Review"
    if benchmark_cpa > 0 and cost >= benchmark_cpa:
        return "🔴 Spend Review"
    if clicks >= 5:
        return "🟡 Needs Data / Review"
    return "⚪ Monitor"


def growth_auction_threat_score(overlap, position_above, impression_share, top_impression):
    overlap = max(0.0, min(100.0, growth_safe_float(overlap)))
    position_above = max(0.0, min(100.0, growth_safe_float(position_above)))
    impression_share = max(0.0, min(100.0, growth_safe_float(impression_share)))
    top_impression = max(0.0, min(100.0, growth_safe_float(top_impression)))

    score = (
        overlap * 0.35
        + position_above * 0.30
        + impression_share * 0.25
        + top_impression * 0.10
    )
    return round(score, 1)


def growth_auction_risk(score):
    score = growth_safe_float(score)
    if score >= 55:
        return "🔴 HIGH"
    if score >= 30:
        return "🟠 MEDIUM"
    return "🟢 LOW"


def growth_resolve_geo_target(client, location_name="Hyderabad", country_code="IN"):
    service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = "en"
    request.country_code = country_code
    request.location_names.names.append(location_name)

    try:
        response = service.suggest_geo_target_constants(request=request)
    except TypeError:
        response = service.suggest_geo_target_constants(request)

    suggestions = list(response.geo_target_constant_suggestions)
    if not suggestions:
        raise ValueError(f"No Google Ads geo target found for {location_name}.")

    def suggestion_rank(item):
        geo = item.geo_target_constant
        name_match = str(geo.name or "").casefold() == location_name.casefold()
        city_match = str(geo.target_type or "").casefold() == "city"
        country_match = str(geo.country_code or "").casefold() == country_code.casefold()
        return (country_match, name_match, city_match, int(item.reach or 0))

    best = sorted(suggestions, key=suggestion_rank, reverse=True)[0]
    return best.geo_target_constant.resource_name, best.geo_target_constant.name


def growth_fetch_keyword_historical_metrics(
    client,
    customer_id,
    keywords,
    geo_resource_name,
    language_id="1000",
):
    clean_keywords = []
    seen = set()
    for keyword in keywords:
        text = re.sub(r"\s+", " ", str(keyword or "")).strip()
        key = growth_normalize_keyword(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        clean_keywords.append(text)

    if not clean_keywords:
        return pd.DataFrame(), {}

    service = client.get_service("KeywordPlanIdeaService")
    google_ads_service = client.get_service("GoogleAdsService")
    request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
    request.customer_id = customer_id
    request.keywords.extend(clean_keywords)
    request.geo_target_constants.append(geo_resource_name)
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.language = google_ads_service.language_constant_path(str(language_id))

    response = service.generate_keyword_historical_metrics(request=request)

    metric_rows = []
    monthly_map = {}

    for result in response.results:
        metrics = result.keyword_metrics
        result_text = str(result.text or "").strip()
        aliases = [result_text] + [str(v) for v in list(result.close_variants or [])]
        aliases = [alias for alias in aliases if alias]

        row = {
            "Planner Keyword": result_text,
            "Avg Monthly Searches": int(metrics.avg_monthly_searches or 0),
            "Competition": growth_competition_name(metrics.competition),
            "Competition Index": int(metrics.competition_index or 0),
            "Top Page Bid Low (₹)": round(
                growth_safe_float(metrics.low_top_of_page_bid_micros) / 1_000_000,
                2,
            ),
            "Top Page Bid High (₹)": round(
                growth_safe_float(metrics.high_top_of_page_bid_micros) / 1_000_000,
                2,
            ),
            "Close Variants": "; ".join(sorted(set(aliases[1:]))),
        }
        metric_rows.append(row)

        monthly_rows = []
        for month_row in list(metrics.monthly_search_volumes or []):
            month_name = growth_enum_name(month_row.month)
            monthly_rows.append(
                {
                    "Year": int(month_row.year or 0),
                    "Month": month_name,
                    "Monthly Searches": int(month_row.monthly_searches or 0),
                }
            )

        for alias in aliases:
            monthly_map[growth_normalize_keyword(alias)] = monthly_rows

    metrics_df = pd.DataFrame(metric_rows)

    # Expand close variants into a stable alias map so Keyword Planner grouping
    # can still merge back to the actual Google Ads keyword rows.
    expanded_rows = []
    for _, row in metrics_df.iterrows():
        aliases = [row["Planner Keyword"]]
        if row.get("Close Variants"):
            aliases.extend(
                item.strip()
                for item in str(row["Close Variants"]).split(";")
                if item.strip()
            )
        for alias in aliases:
            expanded = row.to_dict()
            expanded["Keyword Key"] = growth_normalize_keyword(alias)
            expanded_rows.append(expanded)

    return pd.DataFrame(expanded_rows), monthly_map


def growth_fetch_auction_insights(ga_service, customer_id, date_filter_clause):
    query = f"""
        SELECT
            campaign.name,
            ad_group.name,
            ad_group_criterion.keyword.text,
            segments.auction_insight_domain,
            metrics.auction_insight_search_impression_share,
            metrics.auction_insight_search_overlap_rate,
            metrics.auction_insight_search_position_above_rate,
            metrics.auction_insight_search_top_impression_percentage,
            metrics.auction_insight_search_absolute_top_impression_percentage,
            metrics.auction_insight_search_outranking_share
        FROM keyword_view
        WHERE {date_filter_clause}
          AND ad_group_criterion.status != 'REMOVED'
        ORDER BY metrics.auction_insight_search_overlap_rate DESC
    """

    response = ga_service.search(customer_id=customer_id, query=query)
    rows = []

    for row in response:
        domain = str(row.segments.auction_insight_domain or "").strip()
        keyword = str(row.ad_group_criterion.keyword.text or "").strip()
        if not domain or not keyword or growth_is_own_domain(domain):
            continue

        impression_share = growth_percentage(
            row.metrics.auction_insight_search_impression_share
        )
        overlap = growth_percentage(
            row.metrics.auction_insight_search_overlap_rate
        )
        position_above = growth_percentage(
            row.metrics.auction_insight_search_position_above_rate
        )
        top_impression = growth_percentage(
            row.metrics.auction_insight_search_top_impression_percentage
        )
        absolute_top = growth_percentage(
            row.metrics.auction_insight_search_absolute_top_impression_percentage
        )
        outranking = growth_percentage(
            row.metrics.auction_insight_search_outranking_share
        )

        threat_score = growth_auction_threat_score(
            overlap,
            position_above,
            impression_share,
            top_impression,
        )

        rows.append(
            {
                "Keyword": keyword,
                "Keyword Key": growth_normalize_keyword(keyword),
                "Campaign": row.campaign.name,
                "Ad Group": row.ad_group.name,
                "Competitor Domain": domain,
                "Competitor Impression Share %": round(impression_share, 2),
                "Overlap Rate %": round(overlap, 2),
                "Position Above Rate %": round(position_above, 2),
                "Top Impression %": round(top_impression, 2),
                "Absolute Top %": round(absolute_top, 2),
                "Our Outranking Share %": round(outranking, 2),
                "Threat Score": threat_score,
                "Threat": growth_auction_risk(threat_score),
            }
        )

    return pd.DataFrame(rows)



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
    st.session_state.date_option = "Last 30 Days"

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
            metrics.conversions,
            metrics.phone_calls
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
        calls = int(row.metrics.phone_calls or 0)

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
            "Calls": calls,
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
        total_calls = int(df["Calls"].sum()) if "Calls" in df.columns else 0

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
        # TOP METRICS — SELECTED CAMPAIGN VIEW
        # ==================================================

        selected_impressions = filtered_df["Impressions"].sum()
        selected_clicks = filtered_df["Clicks"].sum()
        selected_cost = filtered_df["Cost (₹)"].sum()
        selected_conversions = filtered_df["Conversions"].sum()
        selected_calls = (
            int(filtered_df["Calls"].sum())
            if "Calls" in filtered_df.columns
            else 0
        )

        selected_ctr = (
            selected_clicks / selected_impressions * 100
            if selected_impressions else 0
        )

        selected_cpc = (
            selected_cost / selected_clicks
            if selected_clicks else 0
        )

        selected_cpa = (
            selected_cost / selected_conversions
            if selected_conversions else 0
        )

        selected_conversion_rate = (
            selected_conversions / selected_clicks * 100
            if selected_clicks else 0
        )

        # ==================================================
        # UNIFIED ANALYSIS SCOPE
        # ==================================================
        # Every downstream intelligence section must follow the Campaign Filter.
        # Reuse the existing total/overall variable names so AI Daily Actions,
        # AI Report and Ask AI cannot accidentally fall back to account-wide KPIs.
        total_impressions = selected_impressions
        total_clicks = selected_clicks
        total_cost = selected_cost
        total_conversions = selected_conversions
        total_calls = selected_calls
        overall_ctr = selected_ctr
        overall_cpc = selected_cpc
        overall_cpa = selected_cpa
        overall_conversion_rate = selected_conversion_rate

        analysis_scope_label = (
            "All Campaigns"
            if selected_campaign == "All Campaigns"
            else f"Campaign: {selected_campaign}"
        )

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric(
            "Impressions",
            f"{selected_impressions:,}"
        )

        col2.metric(
            "Clicks",
            f"{selected_clicks:,}"
        )

        col3.metric(
            "📞 Calls",
            f"{selected_calls:,}"
        )

        col4.metric(
            "Cost",
            f"₹{selected_cost:,.2f}"
        )

        col5.metric(
            "Conversions",
            f"{selected_conversions:.2f}"
        )

        col6, col7, col8, col9 = st.columns(4)

        col6.metric(
            "CTR",
            f"{selected_ctr:.2f}%"
        )

        col7.metric(
            "Avg CPC",
            f"₹{selected_cpc:.2f}"
        )

        col8.metric(
            "CPA",
            f"₹{selected_cpa:.2f}"
        )

        col9.metric(
            "Conversion Rate",
            f"{selected_conversion_rate:.2f}%"
        )

        st.caption(
            "📞 Calls = Google Ads reported phone calls for the selected campaign/date range."
        )

        st.divider()


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

        # Google Ads exposes phone_calls at campaign level, not in
        # search_term_view. Keep campaign-level call context in a backend-only
        # column so zero-conversion search terms from call-producing campaigns
        # are REVIEWED instead of automatically counted as confirmed waste.
        campaign_calls_map = (
            df.set_index("Campaign")["Calls"].to_dict()
            if "Calls" in df.columns
            else {}
        )

        if not search_df.empty:
            search_df["_Campaign Calls"] = (
                search_df["Campaign"]
                .map(campaign_calls_map)
                .fillna(0)
                .astype(float)
            )

            # Keep Search Terms and every downstream search-term intelligence
            # section aligned with the Campaign Filter.
            if selected_campaign != "All Campaigns":
                search_df = search_df[
                    search_df["Campaign"] == selected_campaign
                ].copy()
            else:
                search_df = search_df.copy()

        st.divider()
        st.header("🔍 Search Terms Analysis")
        st.caption(f"Scope: {analysis_scope_label}")

        if not search_df.empty:
            search_terms_display_df = search_df.drop(
                columns=["_Campaign Calls"],
                errors="ignore"
            )

            st.dataframe(
                search_terms_display_df,
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
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions
            FROM campaign
            WHERE {date_filter_clause}
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
                "Campaign": row.campaign.name,
                "Impressions": int(row.metrics.impressions or 0),
                "Clicks": int(row.metrics.clicks or 0),
                "Cost": float(row.metrics.cost_micros or 0) / 1_000_000,
                "Conversions": float(row.metrics.conversions or 0)
            })

        daily_raw_df = pd.DataFrame(
            daily_data,
            columns=[
                "Date",
                "Campaign",
                "Impressions",
                "Clicks",
                "Cost",
                "Conversions"
            ]
        )

        if not daily_raw_df.empty:
            daily_raw_df["Date"] = pd.to_datetime(
                daily_raw_df["Date"],
                errors="coerce"
            )

            daily_raw_df = daily_raw_df.dropna(subset=["Date"])

            if selected_campaign != "All Campaigns":
                daily_raw_df = daily_raw_df[
                    daily_raw_df["Campaign"] == selected_campaign
                ].copy()

            # Aggregate after filtering so all downstream trend and
            # Before-vs-After calculations use exactly the selected scope.
            if not daily_raw_df.empty:
                daily_df = (
                    daily_raw_df
                    .groupby("Date", as_index=False)[
                        [
                            "Impressions",
                            "Clicks",
                            "Cost",
                            "Conversions"
                        ]
                    ]
                    .sum()
                    .sort_values("Date")
                )

                daily_df["CTR"] = daily_df.apply(
                    lambda row: (
                        row["Clicks"] / row["Impressions"] * 100
                        if row["Impressions"] > 0 else 0
                    ),
                    axis=1
                )

                daily_df["CPC"] = daily_df.apply(
                    lambda row: (
                        row["Cost"] / row["Clicks"]
                        if row["Clicks"] > 0 else 0
                    ),
                    axis=1
                )

                daily_df["CPA"] = daily_df.apply(
                    lambda row: (
                        row["Cost"] / row["Conversions"]
                        if row["Conversions"] > 0 else 0
                    ),
                    axis=1
                )

                daily_df = daily_df.set_index("Date")
            else:
                daily_df = pd.DataFrame(
                    columns=[
                        "Impressions",
                        "Clicks",
                        "Cost",
                        "Conversions",
                        "CTR",
                        "CPC",
                        "CPA"
                    ]
                )
        else:
            daily_df = pd.DataFrame(
                columns=[
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
            st.subheader("Daily Performance Trend")
            st.caption(f"Scope: {analysis_scope_label}")

            st.line_chart(
                daily_df[["Clicks", "Conversions"]],
                width="stretch"
            )

        else:
            st.info(
                "No daily performance data available for the selected campaign/date range."
            )

        # ==================================================
        # SUPPORTING DATA — POTENTIAL WASTE SPEND
        # Backend only; visible waste analysis is handled by
        # Advanced Negative AI and Waste Risk Intelligence.
        # ==================================================

        if not search_df.empty:

            zero_conversion_spend_df = search_df[
                (search_df["Cost (₹)"] > 0)
                &
                (search_df["Conversions"] == 0)
            ].copy()

            # Search-term phone_calls are not available directly. Therefore
            # campaign calls are supporting context only and never automatic
            # proof that every zero-conversion term produced a lead.
            # Potential Waste is intentionally limited to CLEAR irrelevant intent.
            clear_irrelevant_patterns = [
                r"\bjobs?\b",
                r"\bvacanc(?:y|ies)\b",
                r"\bcareer(?:s)?\b",
                r"\bsalar(?:y|ies)\b",
                r"\brecruit(?:ment|er|ers|ing)?\b",
                r"\bresume\b",
                r"\bcv\b",
                r"\bcourses?\b",
                r"\btraining\b",
                r"\binstitute\b",
                r"\bcertification\b",
                r"\bsyllabus\b",
                r"\bexams?\b",
                r"\bmeaning\b",
                r"\bdefinition\b",
                r"\bpdf\b"
            ]

            def has_clear_irrelevant_intent(term):
                term_text = str(term or "").casefold()
                return any(
                    re.search(pattern, term_text)
                    for pattern in clear_irrelevant_patterns
                )

            if not zero_conversion_spend_df.empty:
                irrelevant_mask = zero_conversion_spend_df[
                    "Search Term"
                ].apply(has_clear_irrelevant_intent)

                waste_df = zero_conversion_spend_df[
                    irrelevant_mask
                ].copy()

                review_spend_df = zero_conversion_spend_df[
                    ~irrelevant_mask
                ].copy()
            else:
                waste_df = pd.DataFrame(
                    columns=zero_conversion_spend_df.columns
                )
                review_spend_df = pd.DataFrame(
                    columns=zero_conversion_spend_df.columns
                )

            if not waste_df.empty:
                waste_df = waste_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

            if not review_spend_df.empty:
                review_spend_df = review_spend_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                )

        else:

            waste_df = pd.DataFrame(
                columns=search_df.columns
            )

            review_spend_df = pd.DataFrame(
                columns=search_df.columns
            )

        # Keep Waste Risk/Health aligned with the Campaign Filter.
        if selected_campaign == "All Campaigns":
            selected_waste_df = waste_df.copy()
            selected_review_spend_df = review_spend_df.copy()
        else:
            selected_waste_df = waste_df[
                waste_df["Campaign"] == selected_campaign
            ].copy() if "Campaign" in waste_df.columns else waste_df.copy()

            selected_review_spend_df = review_spend_df[
                review_spend_df["Campaign"] == selected_campaign
            ].copy() if "Campaign" in review_spend_df.columns else review_spend_df.copy()


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
        # GROWTH INTELLIGENCE HUB
        # TOP KEYWORDS + SEARCH VOLUME + COMPETITORS
        # ==================================================

        st.divider()
        st.header("🚀 Growth Intelligence Hub")
        st.caption(
            "Top Keywords, Google Keyword Planner search volume and competitor intelligence "
            "in one place. Heavy scans run only when you click their buttons."
        )

        # --------------------------------------------------
        # KEYWORD PERFORMANCE DATA
        # --------------------------------------------------

        keyword_perf_df = pd.DataFrame()
        keyword_summary_df = pd.DataFrame()
        keyword_data_error = None

        try:
            keyword_perf_query = f"""
                SELECT
                    campaign.name,
                    ad_group.name,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    ad_group_criterion.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros,
                    metrics.conversions
                FROM keyword_view
                WHERE {date_filter_clause}
                  AND ad_group_criterion.status != 'REMOVED'
                ORDER BY metrics.cost_micros DESC
            """

            keyword_perf_response = ga_service.search(
                customer_id=customer_id,
                query=keyword_perf_query,
            )

            keyword_perf_rows = []

            for row in keyword_perf_response:
                kw_impressions = int(row.metrics.impressions or 0)
                kw_clicks = int(row.metrics.clicks or 0)
                kw_cost = growth_safe_float(row.metrics.cost_micros) / 1_000_000
                kw_conversions = growth_safe_float(row.metrics.conversions)
                kw_ctr = kw_clicks / kw_impressions * 100 if kw_impressions else 0
                kw_cpc = kw_cost / kw_clicks if kw_clicks else 0
                kw_cpa = kw_cost / kw_conversions if kw_conversions else 0
                kw_cvr = kw_conversions / kw_clicks * 100 if kw_clicks else 0

                keyword_perf_rows.append(
                    {
                        "Keyword": str(row.ad_group_criterion.keyword.text or "").strip(),
                        "Keyword Key": growth_normalize_keyword(
                            row.ad_group_criterion.keyword.text
                        ),
                        "Campaign": row.campaign.name,
                        "Ad Group": row.ad_group.name,
                        "Match Type": growth_enum_name(
                            row.ad_group_criterion.keyword.match_type
                        ),
                        "Status": growth_enum_name(
                            row.ad_group_criterion.status
                        ),
                        "Impressions": kw_impressions,
                        "Clicks": kw_clicks,
                        "Cost (₹)": round(kw_cost, 2),
                        "Conversions": round(kw_conversions, 2),
                        "CTR %": round(kw_ctr, 2),
                        "Avg CPC (₹)": round(kw_cpc, 2),
                        "CPA (₹)": round(kw_cpa, 2),
                        "Conversion Rate %": round(kw_cvr, 2),
                    }
                )

            keyword_perf_df = pd.DataFrame(keyword_perf_rows)

            if not keyword_perf_df.empty:
                if selected_campaign != "All Campaigns":
                    keyword_perf_df = keyword_perf_df[
                        keyword_perf_df["Campaign"] == selected_campaign
                    ].copy()

                keyword_perf_df = keyword_perf_df[
                    keyword_perf_df["Keyword"].astype(str).str.strip() != ""
                ].copy()

            if not keyword_perf_df.empty:
                keyword_summary_rows = []

                for keyword_key, group_df in keyword_perf_df.groupby(
                    "Keyword Key",
                    dropna=False,
                ):
                    impressions = float(group_df["Impressions"].sum())
                    clicks = float(group_df["Clicks"].sum())
                    cost = float(group_df["Cost (₹)"].sum())
                    conversions = float(group_df["Conversions"].sum())

                    keyword_values = [
                        str(v).strip()
                        for v in group_df["Keyword"].tolist()
                        if str(v).strip()
                    ]
                    keyword_label = keyword_values[0] if keyword_values else str(keyword_key)

                    ctr = clicks / impressions * 100 if impressions else 0
                    cpc = cost / clicks if clicks else 0
                    cpa = cost / conversions if conversions else 0
                    cvr = conversions / clicks * 100 if clicks else 0

                    keyword_summary_rows.append(
                        {
                            "Keyword": keyword_label,
                            "Keyword Key": keyword_key,
                            "Campaigns": "; ".join(
                                sorted(set(group_df["Campaign"].astype(str)))
                            ),
                            "Ad Groups": "; ".join(
                                sorted(set(group_df["Ad Group"].astype(str)))
                            ),
                            "Match Types": "; ".join(
                                sorted(set(group_df["Match Type"].astype(str)))
                            ),
                            "Impressions": int(impressions),
                            "Clicks": int(clicks),
                            "Cost (₹)": round(cost, 2),
                            "Conversions": round(conversions, 2),
                            "CTR %": round(ctr, 2),
                            "Avg CPC (₹)": round(cpc, 2),
                            "CPA (₹)": round(cpa, 2),
                            "Conversion Rate %": round(cvr, 2),
                        }
                    )

                keyword_summary_df = pd.DataFrame(keyword_summary_rows)

                keyword_benchmark_cpa = (
                    float(keyword_summary_df.loc[
                        keyword_summary_df["Conversions"] > 0,
                        "CPA (₹)",
                    ].replace(0, pd.NA).dropna().median())
                    if not keyword_summary_df.loc[
                        keyword_summary_df["Conversions"] > 0
                    ].empty
                    else 0.0
                )

                if overall_cpa > 0:
                    keyword_benchmark_cpa = float(overall_cpa)

                keyword_summary_df["AI Signal"] = keyword_summary_df.apply(
                    lambda row: growth_keyword_signal(
                        row["Conversions"],
                        row["Cost (₹)"],
                        row["CPA (₹)"],
                        keyword_benchmark_cpa,
                        row["Clicks"],
                    ),
                    axis=1,
                )

        except Exception as keyword_error:
            keyword_data_error = keyword_error

        growth_tab_keywords, growth_tab_volume, growth_tab_competitors = st.tabs(
            [
                "🏆 Top Keywords",
                "🔎 Search Volume",
                "🏁 Competitors",
            ]
        )

        # ==================================================
        # TAB 1 — TOP KEYWORDS
        # ==================================================

        with growth_tab_keywords:
            st.subheader("🏆 Top Keyword Performance")
            st.caption(
                "Uses actual Google Ads keyword performance for the selected date range and campaign. "
                "Calls are not assigned to individual keywords because Google Ads phone_calls is campaign-level context."
            )

            if keyword_data_error is not None:
                st.warning(
                    "Keyword performance could not be loaded. The rest of the dashboard will continue to work."
                )
                st.caption(f"Technical detail: {keyword_data_error}")

            elif keyword_summary_df.empty:
                st.info("No keyword performance data is available for the selected scope.")

            else:
                kw_metric1, kw_metric2, kw_metric3, kw_metric4 = st.columns(4)

                kw_metric1.metric(
                    "Keywords With Data",
                    f"{len(keyword_summary_df):,}",
                )
                kw_metric2.metric(
                    "Converting Keywords",
                    f"{int((keyword_summary_df['Conversions'] > 0).sum()):,}",
                )
                kw_metric3.metric(
                    "Keyword Spend",
                    f"₹{float(keyword_summary_df['Cost (₹)'].sum()):,.2f}",
                )
                kw_metric4.metric(
                    "Keyword Conversions",
                    f"{float(keyword_summary_df['Conversions'].sum()):,.1f}",
                )

                top_converter_df = keyword_summary_df.sort_values(
                    ["Conversions", "CPA (₹)", "Cost (₹)"],
                    ascending=[False, True, False],
                ).head(15)

                best_cpa_df = keyword_summary_df[
                    keyword_summary_df["Conversions"] > 0
                ].copy()
                best_cpa_df = best_cpa_df.sort_values(
                    ["CPA (₹)", "Conversions"],
                    ascending=[True, False],
                ).head(15)

                high_spend_df = keyword_summary_df.sort_values(
                    ["Cost (₹)", "Conversions"],
                    ascending=[False, False],
                ).head(15)

                kw_view1, kw_view2, kw_view3 = st.tabs(
                    [
                        "🔥 High Converting",
                        "💰 Best CPA",
                        "📈 Highest Spend",
                    ]
                )

                keyword_display_columns = [
                    "Keyword",
                    "Campaigns",
                    "Match Types",
                    "Impressions",
                    "Clicks",
                    "Cost (₹)",
                    "Conversions",
                    "CTR %",
                    "Avg CPC (₹)",
                    "CPA (₹)",
                    "Conversion Rate %",
                    "AI Signal",
                ]

                with kw_view1:
                    st.dataframe(
                        top_converter_df[keyword_display_columns],
                        width="stretch",
                        hide_index=True,
                    )

                with kw_view2:
                    if best_cpa_df.empty:
                        st.info("No converting keyword is available for Best CPA ranking.")
                    else:
                        st.dataframe(
                            best_cpa_df[keyword_display_columns],
                            width="stretch",
                            hide_index=True,
                        )

                with kw_view3:
                    st.dataframe(
                        high_spend_df[keyword_display_columns],
                        width="stretch",
                        hide_index=True,
                    )

                st.caption(
                    "AI Signal is a decision-support label only. No bid or keyword change is applied automatically."
                )

        # ==================================================
        # TAB 2 — SEARCH VOLUME / KEYWORD PLANNER
        # ==================================================

        with growth_tab_volume:
            st.subheader("🔎 Keyword Search Volume & Market Demand")
            st.caption(
                "Google Keyword Planner historical metrics are loaded only when you click the button. "
                "Results are cached in this session so normal dashboard refreshes do not repeatedly call Keyword Planner."
            )

            if keyword_summary_df.empty:
                st.info("Keyword performance data is required before search volume can be loaded.")

            else:
                volume_col1, volume_col2 = st.columns(2)

                with volume_col1:
                    planner_language = st.selectbox(
                        "Keyword Planner Language",
                        ["English", "Hindi", "Telugu"],
                        index=0,
                        key="growth_planner_language",
                    )

                with volume_col2:
                    planner_keyword_limit = st.select_slider(
                        "Keywords To Check",
                        options=[25, 50, 75, 100],
                        value=50,
                        key="growth_planner_keyword_limit",
                    )

                planner_language_id = CAMPAIGN_BUILDER_LANGUAGE_IDS.get(
                    planner_language,
                    "1000",
                )

                planner_source_df = keyword_summary_df.sort_values(
                    ["Conversions", "Cost (₹)", "Clicks"],
                    ascending=[False, False, False],
                ).head(int(planner_keyword_limit))

                planner_keywords = planner_source_df["Keyword"].astype(str).tolist()

                volume_request_key = hashlib.sha256(
                    json.dumps(
                        {
                            "scope": analysis_scope_label,
                            "date": date_option,
                            "keywords": sorted(
                                growth_normalize_keyword(v)
                                for v in planner_keywords
                            ),
                            "language": planner_language_id,
                            "location": "Hyderabad, IN",
                        },
                        sort_keys=True,
                    ).encode("utf-8")
                ).hexdigest()

                if st.button(
                    "🔎 Load Hyderabad Search Volume",
                    key="growth_load_search_volume_button",
                    type="primary",
                ):
                    try:
                        with st.spinner(
                            "Loading Keyword Planner historical metrics for Hyderabad..."
                        ):
                            geo_resource_name, geo_name = growth_resolve_geo_target(
                                client,
                                location_name="Hyderabad",
                                country_code="IN",
                            )

                            planner_metrics_df, planner_monthly_map = (
                                growth_fetch_keyword_historical_metrics(
                                    client=client,
                                    customer_id=customer_id,
                                    keywords=planner_keywords,
                                    geo_resource_name=geo_resource_name,
                                    language_id=planner_language_id,
                                )
                            )

                        st.session_state["growth_volume_cache_key"] = volume_request_key
                        st.session_state["growth_volume_metrics_df"] = planner_metrics_df
                        st.session_state["growth_volume_monthly_map"] = planner_monthly_map
                        st.session_state["growth_volume_geo_name"] = geo_name
                        st.session_state["growth_volume_language"] = planner_language

                    except Exception as planner_error:
                        st.error(
                            "Keyword Planner search volume could not be loaded. "
                            "No other dashboard section was affected."
                        )
                        st.caption(f"Technical detail: {planner_error}")

                volume_cache_is_current = (
                    st.session_state.get("growth_volume_cache_key")
                    == volume_request_key
                    and isinstance(
                        st.session_state.get("growth_volume_metrics_df"),
                        pd.DataFrame,
                    )
                )

                if volume_cache_is_current:
                    planner_metrics_df = st.session_state.get(
                        "growth_volume_metrics_df",
                        pd.DataFrame(),
                    ).copy()
                    planner_monthly_map = st.session_state.get(
                        "growth_volume_monthly_map",
                        {},
                    )
                    planner_geo_name = st.session_state.get(
                        "growth_volume_geo_name",
                        "Hyderabad",
                    )
                    planner_language_name = st.session_state.get(
                        "growth_volume_language",
                        planner_language,
                    )

                    if planner_metrics_df.empty:
                        st.info(
                            "Keyword Planner returned no historical metrics for these keywords."
                        )
                    else:
                        planner_alias_df = planner_metrics_df.drop_duplicates(
                            subset=["Keyword Key"],
                            keep="first",
                        ).copy()

                        planner_merge_columns = [
                            "Keyword Key",
                            "Avg Monthly Searches",
                            "Competition",
                            "Competition Index",
                            "Top Page Bid Low (₹)",
                            "Top Page Bid High (₹)",
                            "Planner Keyword",
                        ]

                        volume_perf_df = keyword_summary_df.merge(
                            planner_alias_df[planner_merge_columns],
                            on="Keyword Key",
                            how="left",
                        )

                        volume_perf_df["Avg Monthly Searches"] = pd.to_numeric(
                            volume_perf_df["Avg Monthly Searches"],
                            errors="coerce",
                        ).fillna(0)

                        positive_volumes = volume_perf_df.loc[
                            volume_perf_df["Avg Monthly Searches"] > 0,
                            "Avg Monthly Searches",
                        ]

                        if not positive_volumes.empty:
                            high_volume_threshold = max(
                                float(positive_volumes.median()),
                                float(positive_volumes.quantile(0.75)),
                            )
                        else:
                            high_volume_threshold = 0.0

                        def growth_volume_opportunity(row):
                            searches = growth_safe_float(row["Avg Monthly Searches"])
                            conversions = growth_safe_float(row["Conversions"])
                            cpa = growth_safe_float(row["CPA (₹)"])
                            cost = growth_safe_float(row["Cost (₹)"])

                            is_high_volume = (
                                high_volume_threshold > 0
                                and searches >= high_volume_threshold
                            )

                            if is_high_volume and conversions > 0:
                                if overall_cpa <= 0 or (cpa > 0 and cpa <= overall_cpa * 1.20):
                                    return "🏆 High-Volume Winner"
                                return "🟠 High Volume / CPA Review"
                            if is_high_volume and conversions == 0:
                                return "⚠️ High Volume / No Conversion — Review"
                            if conversions > 0:
                                return "✅ Efficient Demand"
                            if cost > 0:
                                return "🟡 Monitor"
                            return "⚪ Low Data"

                        volume_perf_df["Market Signal"] = volume_perf_df.apply(
                            growth_volume_opportunity,
                            axis=1,
                        )

                        volume_perf_df = volume_perf_df.sort_values(
                            ["Avg Monthly Searches", "Conversions", "Cost (₹)"],
                            ascending=[False, False, False],
                        )

                        loaded_count = int(
                            (volume_perf_df["Avg Monthly Searches"] > 0).sum()
                        )
                        max_volume = int(
                            volume_perf_df["Avg Monthly Searches"].max()
                            if not volume_perf_df.empty
                            else 0
                        )

                        vol_metric1, vol_metric2, vol_metric3, vol_metric4 = st.columns(4)
                        vol_metric1.metric("Planner Keywords Loaded", f"{loaded_count:,}")
                        vol_metric2.metric("Highest Avg Monthly Searches", f"{max_volume:,}")
                        vol_metric3.metric(
                            "High-Volume Converters",
                            f"{int(((volume_perf_df['Avg Monthly Searches'] >= high_volume_threshold) & (volume_perf_df['Conversions'] > 0)).sum()) if high_volume_threshold > 0 else 0:,}",
                        )
                        vol_metric4.metric(
                            "High-Volume Review",
                            f"{int(((volume_perf_df['Avg Monthly Searches'] >= high_volume_threshold) & (volume_perf_df['Conversions'] == 0)).sum()) if high_volume_threshold > 0 else 0:,}",
                        )

                        st.caption(
                            f"Planner market: {planner_geo_name} • Language: {planner_language_name}. "
                            "Search volume is market demand context; it does not automatically control bidding."
                        )

                        volume_display_columns = [
                            "Keyword",
                            "Avg Monthly Searches",
                            "Competition",
                            "Competition Index",
                            "Top Page Bid Low (₹)",
                            "Top Page Bid High (₹)",
                            "Clicks",
                            "Cost (₹)",
                            "Conversions",
                            "CPA (₹)",
                            "Conversion Rate %",
                            "Market Signal",
                        ]

                        st.dataframe(
                            volume_perf_df[volume_display_columns].head(50),
                            width="stretch",
                            hide_index=True,
                        )

                        trend_keyword_options = volume_perf_df.loc[
                            volume_perf_df["Avg Monthly Searches"] > 0,
                            "Keyword",
                        ].astype(str).tolist()

                        if trend_keyword_options:
                            selected_trend_keyword = st.selectbox(
                                "12-Month Search Trend Keyword",
                                trend_keyword_options,
                                key="growth_volume_trend_keyword",
                            )

                            trend_key = growth_normalize_keyword(selected_trend_keyword)
                            trend_rows = planner_monthly_map.get(trend_key, [])

                            if trend_rows:
                                month_order = {
                                    "JANUARY": 1,
                                    "FEBRUARY": 2,
                                    "MARCH": 3,
                                    "APRIL": 4,
                                    "MAY": 5,
                                    "JUNE": 6,
                                    "JULY": 7,
                                    "AUGUST": 8,
                                    "SEPTEMBER": 9,
                                    "OCTOBER": 10,
                                    "NOVEMBER": 11,
                                    "DECEMBER": 12,
                                }
                                trend_df = pd.DataFrame(trend_rows)
                                trend_df["Month Number"] = trend_df["Month"].map(
                                    month_order
                                ).fillna(0)
                                trend_df = trend_df.sort_values(
                                    ["Year", "Month Number"]
                                )
                                trend_df["Period"] = (
                                    trend_df["Month"].str.title().str[:3]
                                    + " "
                                    + trend_df["Year"].astype(str)
                                )
                                st.line_chart(
                                    trend_df.set_index("Period")[["Monthly Searches"]],
                                    width="stretch",
                                )
                else:
                    st.info(
                        "Click **Load Hyderabad Search Volume** when you want fresh Keyword Planner metrics. "
                        "It will not run automatically."
                    )

        # ==================================================
        # TAB 3 — COMPETITOR INTELLIGENCE
        # ==================================================

        with growth_tab_competitors:
            st.subheader("🏁 Competitor Intelligence")
            st.caption(
                "Two different signals are kept separate for accuracy: "
                "Auction Competition shows domains that actually overlap your keywords; "
                "Brand Search Scan shows competitor/provider names typed by users in Search Terms."
            )

            competitor_auction_tab, competitor_brand_tab = st.tabs(
                [
                    "⚔️ Keyword Auction Competition",
                    "🔍 Competitor Brand Search Scan",
                ]
            )

            # ----------------------------------------------
            # REAL KEYWORD AUCTION COMPETITION
            # ----------------------------------------------

            with competitor_auction_tab:
                st.markdown("#### ⚔️ Which competitor is fighting us on which keyword?")
                st.caption(
                    "Runs Google Ads Auction Insights on demand. No scan runs automatically. "
                    "If the account/API does not return Auction Insights, the dashboard fails safely and the Brand Search Scan remains available."
                )

                auction_scope_key = (
                    f"{analysis_scope_label}|{date_option}|"
                    f"{start_date if 'start_date' in locals() else ''}|"
                    f"{end_date if 'end_date' in locals() else ''}"
                )

                if st.button(
                    "🏁 Run Keyword Auction Competitor Scan",
                    key="growth_run_auction_competitor_scan",
                    type="primary",
                ):
                    try:
                        with st.spinner("Loading keyword-level Auction Insights..."):
                            new_auction_df = growth_fetch_auction_insights(
                                ga_service=ga_service,
                                customer_id=customer_id,
                                date_filter_clause=date_filter_clause,
                            )

                            if (
                                not new_auction_df.empty
                                and selected_campaign != "All Campaigns"
                            ):
                                new_auction_df = new_auction_df[
                                    new_auction_df["Campaign"] == selected_campaign
                                ].copy()

                        if (
                            st.session_state.get("growth_auction_scope_key")
                            == auction_scope_key
                            and isinstance(
                                st.session_state.get("growth_auction_current_df"),
                                pd.DataFrame,
                            )
                        ):
                            st.session_state["growth_auction_previous_df"] = (
                                st.session_state["growth_auction_current_df"].copy()
                            )
                        else:
                            st.session_state["growth_auction_previous_df"] = pd.DataFrame()

                        st.session_state["growth_auction_current_df"] = new_auction_df
                        st.session_state["growth_auction_scope_key"] = auction_scope_key
                        st.session_state.pop("growth_auction_error", None)

                    except Exception as auction_error:
                        st.session_state["growth_auction_error"] = str(auction_error)

                auction_error_text = st.session_state.get("growth_auction_error")
                if auction_error_text:
                    st.warning(
                        "Auction Insights could not be loaded for this run. "
                        "This can happen when the selected account/date range has insufficient Auction Insights data or the API does not expose it for that request."
                    )
                    st.caption(f"Technical detail: {auction_error_text}")

                auction_df = st.session_state.get(
                    "growth_auction_current_df",
                    pd.DataFrame(),
                )

                if (
                    isinstance(auction_df, pd.DataFrame)
                    and not auction_df.empty
                    and st.session_state.get("growth_auction_scope_key") == auction_scope_key
                ):
                    auction_display_df = auction_df.copy()

                    if not keyword_summary_df.empty:
                        own_keyword_metrics = keyword_summary_df[
                            [
                                "Keyword Key",
                                "Clicks",
                                "Cost (₹)",
                                "Conversions",
                                "CPA (₹)",
                                "Conversion Rate %",
                                "AI Signal",
                            ]
                        ].drop_duplicates("Keyword Key")

                        auction_display_df = auction_display_df.merge(
                            own_keyword_metrics,
                            on="Keyword Key",
                            how="left",
                        )
                    else:
                        for column_name in [
                            "Clicks",
                            "Cost (₹)",
                            "Conversions",
                            "CPA (₹)",
                            "Conversion Rate %",
                            "AI Signal",
                        ]:
                            auction_display_df[column_name] = 0

                    def auction_action(row):
                        threat = str(row.get("Threat", ""))
                        conversions = growth_safe_float(row.get("Conversions", 0))
                        if "HIGH" in threat and conversions > 0:
                            return "Protect winning keyword; review ad strength/bid later"
                        if "HIGH" in threat:
                            return "Review relevance + CPA before any bid increase"
                        if "MEDIUM" in threat and conversions > 0:
                            return "Monitor; defend profitable traffic"
                        if "MEDIUM" in threat:
                            return "Review ad/landing-page competitiveness"
                        return "Monitor"

                    auction_display_df["Recommended Action"] = (
                        auction_display_df.apply(auction_action, axis=1)
                    )

                    auction_domain_rows = []
                    for domain, domain_df in auction_display_df.groupby(
                        "Competitor Domain",
                        dropna=False,
                    ):
                        auction_domain_rows.append(
                            {
                                "Competitor Domain": domain,
                                "Keywords Battled": int(domain_df["Keyword"].nunique()),
                                "Avg Impression Share %": round(
                                    float(domain_df["Competitor Impression Share %"].mean()),
                                    2,
                                ),
                                "Avg Overlap Rate %": round(
                                    float(domain_df["Overlap Rate %"].mean()),
                                    2,
                                ),
                                "Avg Position Above %": round(
                                    float(domain_df["Position Above Rate %"].mean()),
                                    2,
                                ),
                                "Max Threat Score": round(
                                    float(domain_df["Threat Score"].max()),
                                    1,
                                ),
                                "Threat": growth_auction_risk(
                                    float(domain_df["Threat Score"].max())
                                ),
                            }
                        )

                    auction_domain_df = pd.DataFrame(auction_domain_rows).sort_values(
                        ["Max Threat Score", "Keywords Battled"],
                        ascending=[False, False],
                    )

                    auc_m1, auc_m2, auc_m3, auc_m4 = st.columns(4)
                    auc_m1.metric(
                        "Auction Competitors",
                        f"{auction_display_df['Competitor Domain'].nunique():,}",
                    )
                    auc_m2.metric(
                        "Keywords With Competition",
                        f"{auction_display_df['Keyword'].nunique():,}",
                    )
                    auc_m3.metric(
                        "High-Threat Rows",
                        f"{int(auction_display_df['Threat'].astype(str).str.contains('HIGH').sum()):,}",
                    )
                    auc_m4.metric(
                        "Highest Threat Score",
                        f"{float(auction_display_df['Threat Score'].max()):.1f}/100",
                    )

                    st.markdown("#### 🏢 Strongest Auction Competitors")
                    st.dataframe(
                        auction_domain_df,
                        width="stretch",
                        hide_index=True,
                    )

                    st.markdown("#### 🗺 Keyword Battle Map")
                    battle_columns = [
                        "Keyword",
                        "Competitor Domain",
                        "Campaign",
                        "Ad Group",
                        "Competitor Impression Share %",
                        "Overlap Rate %",
                        "Position Above Rate %",
                        "Top Impression %",
                        "Our Outranking Share %",
                        "Threat Score",
                        "Threat",
                        "Clicks",
                        "Cost (₹)",
                        "Conversions",
                        "CPA (₹)",
                        "Recommended Action",
                    ]
                    battle_columns = [
                        column
                        for column in battle_columns
                        if column in auction_display_df.columns
                    ]

                    st.dataframe(
                        auction_display_df[battle_columns].sort_values(
                            ["Threat Score", "Overlap Rate %"],
                            ascending=[False, False],
                        ),
                        width="stretch",
                        hide_index=True,
                    )

                    previous_auction_df = st.session_state.get(
                        "growth_auction_previous_df",
                        pd.DataFrame(),
                    )

                    if isinstance(previous_auction_df, pd.DataFrame) and not previous_auction_df.empty:
                        previous_domain_rows = []
                        for domain, domain_df in previous_auction_df.groupby(
                            "Competitor Domain",
                            dropna=False,
                        ):
                            previous_domain_rows.append(
                                {
                                    "Competitor Domain": domain,
                                    "Previous Keywords Battled": int(
                                        domain_df["Keyword"].nunique()
                                    ),
                                    "Previous Max Threat": round(
                                        float(domain_df["Threat Score"].max()),
                                        1,
                                    ),
                                }
                            )

                        previous_domain_df = pd.DataFrame(previous_domain_rows)
                        auction_compare_df = auction_domain_df.merge(
                            previous_domain_df,
                            on="Competitor Domain",
                            how="outer",
                        ).fillna(0)
                        auction_compare_df["Δ Keywords"] = (
                            auction_compare_df["Keywords Battled"]
                            - auction_compare_df["Previous Keywords Battled"]
                        )
                        auction_compare_df["Δ Threat"] = (
                            auction_compare_df["Max Threat Score"]
                            - auction_compare_df["Previous Max Threat"]
                        ).round(1)

                        with st.expander("📊 Current Run vs Previous Run"):
                            st.dataframe(
                                auction_compare_df[
                                    [
                                        "Competitor Domain",
                                        "Keywords Battled",
                                        "Previous Keywords Battled",
                                        "Δ Keywords",
                                        "Max Threat Score",
                                        "Previous Max Threat",
                                        "Δ Threat",
                                    ]
                                ].sort_values("Max Threat Score", ascending=False),
                                width="stretch",
                                hide_index=True,
                            )
                    else:
                        st.caption(
                            "Run the same scope again later to unlock Current Run vs Previous Run comparison."
                        )

                elif not auction_error_text:
                    st.info(
                        "Click **Run Keyword Auction Competitor Scan** to see exact keyword-to-domain competition."
                    )

            # ----------------------------------------------
            # COMPETITOR BRAND SEARCH-TERM SCAN
            # ----------------------------------------------

            with competitor_brand_tab:
                st.markdown("#### 🔍 Which competitor/provider names are users searching?")
                st.caption(
                    "Scans the full selected Search Terms dataset, protects your own brands and normal service phrases, "
                    "then sends only likely brand/ambiguous candidates to AI in batches. Competitor terms are REVIEW only — never auto-blocked."
                )

                brand_scope_key = (
                    f"{analysis_scope_label}|{date_option}|"
                    f"{start_date if 'start_date' in locals() else ''}|"
                    f"{end_date if 'end_date' in locals() else ''}"
                )

                if st.button(
                    "🔍 Run Full Competitor Brand Scan",
                    key="growth_run_brand_competitor_scan",
                ):
                    if "search_df" not in locals() or search_df.empty:
                        st.session_state["growth_brand_scan_error"] = (
                            "No Search Terms data is available for the selected scope."
                        )
                    else:
                        try:
                            brand_source_df = search_df.copy()
                            brand_source_df["Search Term"] = (
                                brand_source_df["Search Term"]
                                .fillna("")
                                .astype(str)
                                .str.strip()
                            )
                            brand_source_df = brand_source_df[
                                brand_source_df["Search Term"] != ""
                            ].copy()
                            brand_source_df["_Brand Candidate Score"] = (
                                brand_source_df["Search Term"].apply(
                                    growth_brand_candidate_score
                                )
                            )

                            own_brand_df = brand_source_df[
                                brand_source_df["Search Term"].apply(
                                    growth_is_own_brand
                                )
                            ].copy()

                            brand_candidate_df = brand_source_df[
                                brand_source_df["_Brand Candidate Score"] > 0
                            ].copy()
                            brand_candidate_df = brand_candidate_df.sort_values(
                                ["_Brand Candidate Score", "Cost (₹)"],
                                ascending=[False, False],
                            ).reset_index(drop=True)
                            brand_candidate_df["Row ID"] = range(
                                1,
                                len(brand_candidate_df) + 1,
                            )

                            brand_results = []
                            brand_batch_size = 15

                            with st.spinner(
                                "Reviewing all likely competitor/brand candidates in safe AI batches..."
                            ):
                                for batch_start in range(
                                    0,
                                    len(brand_candidate_df),
                                    brand_batch_size,
                                ):
                                    batch_df = brand_candidate_df.iloc[
                                        batch_start:batch_start + brand_batch_size
                                    ].copy()

                                    batch_payload_columns = [
                                        "Row ID",
                                        "Search Term",
                                        "Campaign",
                                        "Impressions",
                                        "Clicks",
                                        "Cost (₹)",
                                        "Conversions",
                                    ]
                                    if "_Campaign Calls" in batch_df.columns:
                                        batch_payload_columns.append("_Campaign Calls")

                                    batch_payload = batch_df[
                                        [
                                            column
                                            for column in batch_payload_columns
                                            if column in batch_df.columns
                                        ]
                                    ].to_dict("records")

                                    competitor_prompt = f"""
You are classifying Google Ads Search Terms for a Hyderabad home-care business.

OWN BRANDS — NEVER CLASSIFY AS COMPETITOR:
- Hare Krishna / Harekrishna Home Care Services
- Shiva Kaartikeya / Shivakaartikeya Home Care Services

CORE SERVICES — generic service phrases are NOT competitors:
- elderly care, patient care, nursing care, nurse at home
- caretaker, caregiver, baby care, babysitter, nanny
- maid, domestic help, housekeeping, cook, home care

Rules:
1. COMPETITOR only when there is a clear, distinctive provider/business/facility/brand name.
2. A location, locality, person's first name, common word, generic service phrase or unclear phrase is AMBIGUOUS/OTHER, not COMPETITOR.
3. Named hospitals, clinics, nursing homes, old-age homes, home-care agencies or care brands can be COMPETITOR when clearly named.
4. Do not infer a competitor from zero conversions or spend.
5. Never recommend automatic blocking. Competitor terms must be REVIEW.
6. Do not claim a specific Search Term caused a phone call. _Campaign Calls is campaign-level context only.
7. Normalize obvious spelling variants to one concise canonical competitor name when possible.
8. Return ONLY valid JSON array. One object per Row ID.

Required JSON fields:
- row_id: integer
- type: one of COMPETITOR, AMBIGUOUS, OTHER
- competitor_name: canonical name or empty string
- confidence: integer 0-100
- action: REVIEW or KEEP
- reason: short factual reason

DATA:
{json.dumps(batch_payload, ensure_ascii=False, default=str)}
"""

                                    try:
                                        response = openai_client.responses.create(
                                            model="gpt-5.4-mini",
                                            input=competitor_prompt,
                                            max_output_tokens=2200,
                                        )
                                        parsed_rows = growth_extract_json_array(
                                            response.output_text
                                        )
                                    except Exception as batch_error:
                                        parsed_rows = []
                                        for _, fallback_row in batch_df.iterrows():
                                            parsed_rows.append(
                                                {
                                                    "row_id": int(fallback_row["Row ID"]),
                                                    "type": "AMBIGUOUS",
                                                    "competitor_name": "",
                                                    "confidence": 0,
                                                    "action": "REVIEW",
                                                    "reason": (
                                                        "AI batch unavailable; kept for manual review. "
                                                        f"Technical: {batch_error}"
                                                    )[:220],
                                                }
                                            )

                                    parsed_map = {}
                                    for parsed in parsed_rows:
                                        try:
                                            parsed_id = int(parsed.get("row_id"))
                                        except (TypeError, ValueError):
                                            continue
                                        parsed_map[parsed_id] = parsed

                                    for _, source_row in batch_df.iterrows():
                                        row_id = int(source_row["Row ID"])
                                        parsed = parsed_map.get(
                                            row_id,
                                            {
                                                "type": "AMBIGUOUS",
                                                "competitor_name": "",
                                                "confidence": 0,
                                                "action": "REVIEW",
                                                "reason": "No AI classification returned; manual review required.",
                                            },
                                        )

                                        classification = str(
                                            parsed.get("type", "AMBIGUOUS")
                                        ).upper().strip()
                                        if classification not in {
                                            "COMPETITOR",
                                            "AMBIGUOUS",
                                            "OTHER",
                                        }:
                                            classification = "AMBIGUOUS"

                                        competitor_name = re.sub(
                                            r"\s+",
                                            " ",
                                            str(parsed.get("competitor_name", "")),
                                        ).strip()

                                        if (
                                            classification != "COMPETITOR"
                                            or not competitor_name
                                            or growth_is_own_brand(competitor_name)
                                        ):
                                            competitor_name = ""
                                            if classification == "COMPETITOR":
                                                classification = "AMBIGUOUS"

                                        campaign_calls = growth_safe_float(
                                            source_row.get("_Campaign Calls", 0)
                                        )

                                        result_row = source_row.to_dict()
                                        result_row.update(
                                            {
                                                "Type": classification,
                                                "Competitor Name": competitor_name or "—",
                                                "Confidence": int(
                                                    max(
                                                        0,
                                                        min(
                                                            100,
                                                            growth_safe_float(
                                                                parsed.get("confidence", 0)
                                                            ),
                                                        ),
                                                    )
                                                ),
                                                "Recommended Action": (
                                                    "REVIEW"
                                                    if classification in {"COMPETITOR", "AMBIGUOUS"}
                                                    else "KEEP"
                                                ),
                                                "Review Risk": growth_competitor_review_risk(
                                                    source_row.get("Cost (₹)", 0),
                                                    source_row.get("Conversions", 0),
                                                    campaign_calls,
                                                    overall_cpa,
                                                    overall_cpc,
                                                ),
                                                "Reason": str(
                                                    parsed.get("reason", "Manual review")
                                                )[:220],
                                            }
                                        )
                                        brand_results.append(result_row)

                            brand_results_df = pd.DataFrame(brand_results)

                            if brand_results_df.empty:
                                brand_summary_df = pd.DataFrame()
                            else:
                                competitor_rows_df = brand_results_df[
                                    (brand_results_df["Type"] == "COMPETITOR")
                                    & (brand_results_df["Competitor Name"] != "—")
                                ].copy()

                                competitor_rows_df["Competitor Key"] = (
                                    competitor_rows_df["Competitor Name"].apply(
                                        growth_competitor_key
                                    )
                                )

                                brand_summary_rows = []
                                for competitor_key, group_df in competitor_rows_df.groupby(
                                    "Competitor Key",
                                    dropna=False,
                                ):
                                    names = [
                                        str(v)
                                        for v in group_df["Competitor Name"].tolist()
                                        if str(v).strip() and str(v) != "—"
                                    ]
                                    canonical_name = (
                                        sorted(names, key=len)[0]
                                        if names
                                        else str(competitor_key)
                                    )
                                    impressions = float(group_df["Impressions"].sum())
                                    clicks = float(group_df["Clicks"].sum())
                                    spend = float(group_df["Cost (₹)"].sum())
                                    conversions = float(group_df["Conversions"].sum())
                                    campaign_calls_context = (
                                        float(group_df["_Campaign Calls"].max())
                                        if "_Campaign Calls" in group_df.columns
                                        else 0.0
                                    )

                                    brand_summary_rows.append(
                                        {
                                            "Competitor Key": competitor_key,
                                            "Competitor Name": canonical_name,
                                            "Search Terms": int(group_df["Search Term"].nunique()),
                                            "Impressions": int(impressions),
                                            "Clicks": int(clicks),
                                            "Spend (₹)": round(spend, 2),
                                            "Conversions": round(conversions, 2),
                                            "CTR %": round(
                                                clicks / impressions * 100 if impressions else 0,
                                                2,
                                            ),
                                            "Avg CPC (₹)": round(
                                                spend / clicks if clicks else 0,
                                                2,
                                            ),
                                            "Review Risk": growth_competitor_review_risk(
                                                spend,
                                                conversions,
                                                campaign_calls_context,
                                                overall_cpa,
                                                overall_cpc,
                                            ),
                                        }
                                    )

                                brand_summary_df = pd.DataFrame(brand_summary_rows)
                                if not brand_summary_df.empty:
                                    brand_summary_df = brand_summary_df.sort_values(
                                        ["Spend (₹)", "Search Terms"],
                                        ascending=[False, False],
                                    )

                            if (
                                st.session_state.get("growth_brand_scope_key")
                                == brand_scope_key
                                and isinstance(
                                    st.session_state.get("growth_brand_summary_df"),
                                    pd.DataFrame,
                                )
                            ):
                                st.session_state["growth_brand_previous_summary_df"] = (
                                    st.session_state["growth_brand_summary_df"].copy()
                                )
                            else:
                                st.session_state["growth_brand_previous_summary_df"] = pd.DataFrame()

                            st.session_state["growth_brand_scope_key"] = brand_scope_key
                            st.session_state["growth_brand_results_df"] = brand_results_df
                            st.session_state["growth_brand_summary_df"] = brand_summary_df
                            st.session_state["growth_brand_own_brand_df"] = own_brand_df
                            st.session_state["growth_brand_scanned_count"] = len(brand_source_df)
                            st.session_state["growth_brand_candidate_count"] = len(brand_candidate_df)
                            st.session_state.pop("growth_brand_scan_error", None)

                        except Exception as brand_scan_error:
                            st.session_state["growth_brand_scan_error"] = str(
                                brand_scan_error
                            )

                brand_scan_error_text = st.session_state.get(
                    "growth_brand_scan_error"
                )
                if brand_scan_error_text:
                    st.warning(brand_scan_error_text)

                brand_summary_df = st.session_state.get(
                    "growth_brand_summary_df",
                    pd.DataFrame(),
                )
                brand_results_df = st.session_state.get(
                    "growth_brand_results_df",
                    pd.DataFrame(),
                )

                brand_results_are_current = (
                    st.session_state.get("growth_brand_scope_key") == brand_scope_key
                )

                if brand_results_are_current:
                    brand_scanned_count = int(
                        st.session_state.get("growth_brand_scanned_count", 0)
                    )
                    brand_candidate_count = int(
                        st.session_state.get("growth_brand_candidate_count", 0)
                    )

                    brand_m1, brand_m2, brand_m3, brand_m4 = st.columns(4)
                    brand_m1.metric("Search Terms Scanned", f"{brand_scanned_count:,}")
                    brand_m2.metric("AI Candidates", f"{brand_candidate_count:,}")
                    brand_m3.metric(
                        "Unique Competitors",
                        f"{len(brand_summary_df) if isinstance(brand_summary_df, pd.DataFrame) else 0:,}",
                    )
                    brand_m4.metric(
                        "Competitor Review Spend",
                        f"₹{float(brand_summary_df['Spend (₹)'].sum()):,.2f}"
                        if isinstance(brand_summary_df, pd.DataFrame)
                        and not brand_summary_df.empty
                        else "₹0.00",
                    )

                    if isinstance(brand_summary_df, pd.DataFrame) and not brand_summary_df.empty:
                        st.markdown("#### 🏢 Competitor Brands Detected")
                        st.dataframe(
                            brand_summary_df[
                                [
                                    "Competitor Name",
                                    "Search Terms",
                                    "Impressions",
                                    "Clicks",
                                    "Spend (₹)",
                                    "Conversions",
                                    "CTR %",
                                    "Avg CPC (₹)",
                                    "Review Risk",
                                ]
                            ],
                            width="stretch",
                            hide_index=True,
                        )

                        previous_brand_df = st.session_state.get(
                            "growth_brand_previous_summary_df",
                            pd.DataFrame(),
                        )

                        if isinstance(previous_brand_df, pd.DataFrame) and not previous_brand_df.empty:
                            compare_df = brand_summary_df.merge(
                                previous_brand_df[
                                    [
                                        "Competitor Key",
                                        "Spend (₹)",
                                        "Search Terms",
                                    ]
                                ].rename(
                                    columns={
                                        "Spend (₹)": "Previous Spend (₹)",
                                        "Search Terms": "Previous Search Terms",
                                    }
                                ),
                                on="Competitor Key",
                                how="outer",
                            ).fillna(0)

                            compare_df["Δ Spend (₹)"] = (
                                compare_df["Spend (₹)"]
                                - compare_df["Previous Spend (₹)"]
                            ).round(2)
                            compare_df["Δ Search Terms"] = (
                                compare_df["Search Terms"]
                                - compare_df["Previous Search Terms"]
                            )

                            with st.expander("📊 Current Run vs Previous Run"):
                                st.dataframe(
                                    compare_df[
                                        [
                                            "Competitor Name",
                                            "Spend (₹)",
                                            "Previous Spend (₹)",
                                            "Δ Spend (₹)",
                                            "Search Terms",
                                            "Previous Search Terms",
                                            "Δ Search Terms",
                                        ]
                                    ].sort_values("Spend (₹)", ascending=False),
                                    width="stretch",
                                    hide_index=True,
                                )
                        else:
                            st.caption(
                                "Run the same scope again later to compare competitor-brand search activity with the previous run."
                            )
                    else:
                        st.success(
                            "No clear competitor brand/provider name was detected in the reviewed candidates."
                        )

                    if isinstance(brand_results_df, pd.DataFrame) and not brand_results_df.empty:
                        with st.expander("📋 Show All AI-Reviewed Brand Candidates"):
                            review_columns = [
                                "Search Term",
                                "Competitor Name",
                                "Campaign",
                                "Impressions",
                                "Clicks",
                                "Cost (₹)",
                                "Conversions",
                                "Type",
                                "Confidence",
                                "Recommended Action",
                                "Review Risk",
                                "Reason",
                            ]
                            review_columns = [
                                column
                                for column in review_columns
                                if column in brand_results_df.columns
                            ]
                            st.dataframe(
                                brand_results_df[review_columns].sort_values(
                                    "Cost (₹)",
                                    ascending=False,
                                ),
                                width="stretch",
                                hide_index=True,
                            )

                    own_brand_df = st.session_state.get(
                        "growth_brand_own_brand_df",
                        pd.DataFrame(),
                    )
                    if isinstance(own_brand_df, pd.DataFrame) and not own_brand_df.empty:
                        with st.expander("🛡 Own Brand Terms Protected"):
                            protected_columns = [
                                "Search Term",
                                "Campaign",
                                "Impressions",
                                "Clicks",
                                "Cost (₹)",
                                "Conversions",
                            ]
                            protected_columns = [
                                column
                                for column in protected_columns
                                if column in own_brand_df.columns
                            ]
                            st.dataframe(
                                own_brand_df[protected_columns],
                                width="stretch",
                                hide_index=True,
                            )
                elif not brand_scan_error_text:
                    st.info(
                        "Click **Run Full Competitor Brand Scan** only when you want to analyze competitor/provider searches. It will not run automatically."
                    )

                st.warning(
                    "Safety rule retained: competitor or ambiguous Search Terms are REVIEW items. "
                    "They are never automatically added as negatives, and zero conversions alone never proves waste."
                )



        # ==================================================
        # AI DAILY ACTION CENTER
        # TOKEN-EFFICIENT VERSION
        # ==================================================

        st.divider()
        st.header("🎯 AI Daily Action Center")
        st.caption(f"Scope: {analysis_scope_label}")

        st.caption(
            "Shows immediate priority signals from the selected data and, "
            "only when you click the AI button, sends a small Top-10 context "
            "to OpenAI for the Top 5 practical actions."
        )

        # --------------------------------------------------
        # INSTANT PRIORITY SIGNALS — NO OPENAI CALL
        # --------------------------------------------------

        priority_actions = []

        # HIGH CPA
        if overall_cpa > 2000 and total_conversions > 0:

            priority_actions.append({
                "Priority": "🔴 HIGH",
                "Area": "CPA",
                "Problem": f"CPA is high at ₹{overall_cpa:,.2f}",
                "Action": "Reduce waste spend and focus on converting traffic."
            })


        # ZERO / LOW CONVERSIONS + CALL-AWARE TRACKING CHECK
        if total_conversions == 0:

            if total_calls > 0:
                priority_actions.append({
                    "Priority": "🟠 MEDIUM",
                    "Area": "Calls vs Conversions",
                    "Problem": f"0 conversions are recorded, but Google Ads reports {total_calls} calls.",
                    "Action": "Verify call-conversion tracking before treating the traffic as no-lead traffic."
                })
            else:
                priority_actions.append({
                    "Priority": "🔴 HIGH",
                    "Area": "Conversions",
                    "Problem": "No conversions or reported phone calls recorded.",
                    "Action": "Check conversion tracking, search terms, keywords and landing page."
                })

        elif overall_conversion_rate < 2:

            priority_actions.append({
                "Priority": "🟠 MEDIUM",
                "Area": "Conversion Rate",
                "Problem": f"Conversion rate is only {overall_conversion_rate:.2f}%",
                "Action": "Focus on high-intent traffic and landing-page relevance."
            })


        # HIGH CPC
        if overall_cpc > 60:

            priority_actions.append({
                "Priority": "🟠 MEDIUM",
                "Area": "CPC",
                "Problem": f"Average CPC is ₹{overall_cpc:.2f}",
                "Action": "Review expensive search terms, keywords and match types."
            })


        # WASTE SPEND — CALL-AWARE
        daily_waste_amount = 0.0
        daily_review_amount = 0.0

        if "selected_waste_df" in locals() and not selected_waste_df.empty:

            if "Cost (₹)" in selected_waste_df.columns:
                daily_waste_amount = float(
                    selected_waste_df["Cost (₹)"].sum()
                )

            if daily_waste_amount > 500:

                priority_actions.append({
                    "Priority": "🔴 HIGH",
                    "Area": "Potential Waste",
                    "Problem": (
                        f"₹{daily_waste_amount:,.2f} spent with zero conversions "
                        "on search terms showing clear irrelevant intent."
                    ),
                    "Action": "Review high-spend terms and add only safe negatives after intent checks."
                })

        if "selected_review_spend_df" in locals() and not selected_review_spend_df.empty:
            if "Cost (₹)" in selected_review_spend_df.columns:
                daily_review_amount = float(
                    selected_review_spend_df["Cost (₹)"].sum()
                )


        # GOOD CTR
        if overall_ctr >= 8:

            priority_actions.append({
                "Priority": "🟢 GOOD",
                "Area": "CTR",
                "Problem": f"CTR is strong at {overall_ctr:.2f}%",
                "Action": "Protect strong ad relevance and focus next on lead quality."
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

            st.subheader("⚡ Immediate Priority Signals")

            st.dataframe(
                priority_df,
                width="stretch",
                hide_index=True
            )

        else:

            priority_df = pd.DataFrame(
                columns=[
                    "Priority",
                    "Area",
                    "Problem",
                    "Action"
                ]
            )

            st.success(
                "🟢 No major rule-based warning is visible right now."
            )


        # --------------------------------------------------
        # BUILD SMALL AI CONTEXT
        # --------------------------------------------------

        daily_campaign_context = "No campaign data available."

        if "filtered_df" in locals() and not filtered_df.empty:

            daily_campaign_columns = [
                col
                for col in [
                    "Campaign",
                    "Cost (₹)",
                    "Conversions",
                    "Calls",
                    "CPA (₹)"
                ]
                if col in filtered_df.columns
            ]

            if daily_campaign_columns:

                daily_campaign_df = filtered_df[
                    daily_campaign_columns
                ].copy()

                if "Cost (₹)" in daily_campaign_df.columns:
                    daily_campaign_df = daily_campaign_df.sort_values(
                        "Cost (₹)",
                        ascending=False
                    )

                daily_campaign_df = daily_campaign_df.head(5)

                daily_campaign_context = (
                    daily_campaign_df
                    .to_string(index=False)
                )


        daily_search_context = "No search-term data available."

        if "search_df" in locals() and not search_df.empty:

            daily_search_columns = [
                col
                for col in [
                    "Search Term",
                    "Campaign",
                    "Clicks",
                    "Cost (₹)",
                    "Conversions"
                ]
                if col in search_df.columns
            ]

            if daily_search_columns and "Cost (₹)" in search_df.columns:

                daily_search_ai_df = search_df[
                    search_df["Cost (₹)"] > 0
                ][daily_search_columns].copy()

                daily_search_ai_df = daily_search_ai_df.sort_values(
                    "Cost (₹)",
                    ascending=False
                ).head(10)

                if not daily_search_ai_df.empty:
                    daily_search_context = (
                        daily_search_ai_df
                        .to_string(index=False)
                    )


        if not priority_df.empty:
            daily_priority_context = (
                priority_df
                .head(5)
                .to_string(index=False)
            )
        else:
            daily_priority_context = "No rule-based priority warning."


        # --------------------------------------------------
        # AI DAILY ACTION BUTTON
        # --------------------------------------------------

        st.info(
            "AI uses only selected-scope KPIs + Top 5 campaigns + Top 10 highest-spend "
            "search terms. The full dashboard data stays on screen and is not "
            "sent in this AI request."
        )

        if st.button(
            "🧠 Generate Top 5 AI Actions",
            key="ai_daily_action_center_button_v1"
        ):

            daily_ai_cache_key = (
                f"v2|{date_option}|{selected_campaign}|"
                f"{total_impressions}|{total_clicks}|{total_cost}|"
                f"{total_conversions}|{total_calls}|{overall_ctr}|{overall_cpc}|"
                f"{overall_cpa}|{overall_conversion_rate}|"
                f"{daily_waste_amount}|{daily_review_amount}|{daily_campaign_context}|"
                f"{daily_search_context}|{daily_priority_context}"
            )

            if (
                st.session_state.get("daily_ai_cache_key")
                == daily_ai_cache_key
                and st.session_state.get("daily_ai_cache_text")
            ):

                daily_ai_text = st.session_state[
                    "daily_ai_cache_text"
                ]

                st.success(
                    "Showing the saved result for the same data. "
                    "No new AI call was used."
                )

            else:

                daily_action_prompt = f"""
You are a senior Google Ads performance manager.

BUSINESS:
Harekrishna Home Care Services, Hyderabad.

GOAL:
Generate ONLY the 5 most useful actions to take now from the supplied data.

SELECTED PERIOD:
{date_option}

SELECTED CAMPAIGN:
{selected_campaign}

SELECTED-SCOPE KPIs ({analysis_scope_label}):
Impressions: {total_impressions}
Clicks: {total_clicks}
Calls: {total_calls}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {overall_ctr:.2f}%
Average CPC: ₹{overall_cpc:.2f}
CPA: ₹{overall_cpa:.2f}
Conversion Rate: {overall_conversion_rate:.2f}%
Potential waste spend (0 conversions + clear irrelevant intent): ₹{daily_waste_amount:.2f}
Other zero-conversion spend requiring review: ₹{daily_review_amount:.2f}

TOP 5 CAMPAIGNS BY SPEND:
{daily_campaign_context}

TOP 10 HIGHEST-SPEND SEARCH TERMS:
{daily_search_context}

RULE-BASED PRIORITY SIGNALS:
{daily_priority_context}

IMPORTANT RULES:
1. Use only the supplied data. Never invent metrics, leads, revenue or competitor facts.
2. Give exactly 5 actions, ranked from highest to lowest priority.
3. Prefer actions that can improve qualified calls/leads and reduce waste.
4. Do not recommend increasing budget when waste is high or conversions are weak.
5. Do not recommend blocking Harekrishna/Hare Krishna brand or valid service themes
   such as home care, elderly care, patient care, nursing, caretaker, baby care,
   maid, domestic help, housekeeping or cook merely because they have zero conversions.
6. For ambiguous or competitor terms, recommend REVIEW before blocking.
7. If evidence is weak, say REVIEW instead of making a strong change.
8. Calls are available at campaign/account level in this dashboard, not per search term.
   Never claim that a specific search term generated or did not generate a phone call.
9. Keep the answer concise and practical.

Return one Markdown table only with these columns:
Priority | Area | What the Data Shows | Action Today | Expected Purpose | Risk / Check

Priority must be:
1 - Critical
2 - High
3 - Medium
4 - Medium
5 - Low
"""

                try:

                    with st.spinner(
                        "AI is preparing the Top 5 actions..."
                    ):

                        daily_ai_response = (
                            openai_client.responses.create(
                                model="gpt-5.4-mini",
                                input=daily_action_prompt,
                                max_output_tokens=1000
                            )
                        )

                    daily_ai_text = (
                        daily_ai_response.output_text
                    )

                    st.session_state[
                        "daily_ai_cache_key"
                    ] = daily_ai_cache_key

                    st.session_state[
                        "daily_ai_cache_text"
                    ] = daily_ai_text

                except Exception as daily_ai_error:

                    daily_ai_text = None

                    st.error(
                        "AI Daily Action Center could not run right now. "
                        "If this is a rate-limit or credit issue, wait or "
                        "add API credit and try again once."
                    )

                    st.caption(
                        f"Technical detail: {daily_ai_error}"
                    )

            if daily_ai_text:

                st.subheader("🤖 Top 5 AI Actions")

                st.caption(
                    "AI used a compact context only: selected-scope KPIs, Top 5 campaigns "
                    "and Top 10 highest-spend search terms."
                )

                st.write(daily_ai_text)


        # ==================================================
        # ONE-CLICK AI PERFORMANCE REPORT
        # TOKEN-EFFICIENT + CACHED VERSION
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

        st.caption(
            "The full dashboard data stays visible. The AI report uses only "
            "selected-scope KPIs, Top 5 campaigns, Top 10 highest-spend search terms "
            "and Top 5 priority signals to reduce token usage."
        )

        if st.button(
            "Generate AI Performance Report",
            key="one_click_ai_report_generate_button_v3"
        ):

            # ----------------------------------------------
            # COMPACT CAMPAIGN CONTEXT
            # ----------------------------------------------

            report_campaign_columns = [
                col
                for col in [
                    "Campaign",
                    "Impressions",
                    "Clicks",
                    "Calls",
                    "Cost (₹)",
                    "Conversions",
                    "CTR %",
                    "Avg CPC (₹)",
                    "CPA (₹)"
                ]
                if col in filtered_df.columns
            ]

            if report_campaign_columns:
                report_campaign_df = filtered_df[
                    report_campaign_columns
                ].copy()

                if "Cost (₹)" in report_campaign_df.columns:
                    report_campaign_df = report_campaign_df.sort_values(
                        "Cost (₹)",
                        ascending=False
                    )

                report_campaign_df = report_campaign_df.head(5)
                report_campaign_context = report_campaign_df.to_string(
                    index=False
                )
            else:
                report_campaign_context = "Campaign detail is unavailable."

            # ----------------------------------------------
            # COMPACT SEARCH-TERM CONTEXT
            # ----------------------------------------------

            if "search_df" in locals() and not search_df.empty:

                report_search_columns = [
                    col
                    for col in [
                        "Search Term",
                        "Campaign",
                        "Clicks",
                        "Cost (₹)",
                        "Conversions"
                    ]
                    if col in search_df.columns
                ]

                if report_search_columns and "Cost (₹)" in search_df.columns:
                    report_search_df = (
                        search_df[
                            search_df["Cost (₹)"] > 0
                        ][report_search_columns]
                        .sort_values(
                            "Cost (₹)",
                            ascending=False
                        )
                        .head(10)
                        .copy()
                    )

                    report_search_context = report_search_df.to_string(
                        index=False
                    )
                else:
                    report_search_context = "Search-term detail is unavailable."
            else:
                report_search_context = "No search-term data is available."

            # ----------------------------------------------
            # COMPACT PRIORITY CONTEXT
            # ----------------------------------------------

            if "priority_df" in locals() and not priority_df.empty:
                report_priority_context = (
                    priority_df
                    .head(5)
                    .to_string(index=False)
                )
            else:
                report_priority_context = (
                    "No priority actions are currently available."
                )

            if (
                "selected_waste_df" in locals()
                and not selected_waste_df.empty
                and "Cost (₹)" in selected_waste_df.columns
            ):
                report_waste_amount = float(
                    selected_waste_df["Cost (₹)"].sum()
                )
            else:
                report_waste_amount = 0.0

            if (
                "selected_review_spend_df" in locals()
                and not selected_review_spend_df.empty
                and "Cost (₹)" in selected_review_spend_df.columns
            ):
                report_review_amount = float(
                    selected_review_spend_df["Cost (₹)"].sum()
                )
            else:
                report_review_amount = 0.0

            daily_report_prompt = f"""
You are a senior Google Ads performance analyst.

Use ONLY the supplied data. Never invent metrics, savings or causes that the data cannot prove.

REPORT PERIOD:
{report_period}

SELECTED SCOPE:
{analysis_scope_label}

SELECTED-SCOPE KPIs:
Impressions: {total_impressions}
Clicks: {total_clicks}
Calls: {total_calls}
Cost: ₹{total_cost:.2f}
Conversions: {total_conversions:.2f}
CTR: {overall_ctr:.2f}%
Average CPC: ₹{overall_cpc:.2f}
CPA: ₹{overall_cpa:.2f}
Conversion Rate: {overall_conversion_rate:.2f}%
Potential waste spend (0 conversions + clear irrelevant intent): ₹{report_waste_amount:.2f}
Other zero-conversion spend requiring review: ₹{report_review_amount:.2f}

TOP CAMPAIGNS BY SPEND (MAX 5):
{report_campaign_context}

TOP SEARCH TERMS BY SPEND (MAX 10):
{report_search_context}

TOP PRIORITY SIGNALS (MAX 5):
{report_priority_context}

IMPORTANT CALL-DATA RULE:
Calls are campaign/account-level in this dashboard, not search-term-level.
Never claim a specific search term did or did not generate a phone call.

Create a concise professional report with exactly these sections:
1. Executive Summary
2. What Is Working
3. Main Problems
4. Waste / Search-Term Review
5. Budget & Conversion Opportunities
6. Top 5 Actions

Use ₹ for money. Keep Google Ads terms such as CTR, CPC, CPA and Conversions in English.
"""

            report_cache_key = (
                f"v4|{report_period}|{selected_campaign}|"
                f"{total_impressions}|{total_clicks}|{total_calls}|{total_cost:.2f}|"
                f"{total_conversions:.2f}|{report_waste_amount:.2f}|{report_review_amount:.2f}|"
                f"{report_campaign_context}|"
                f"{report_search_context}|{report_priority_context}"
            )

            if (
                st.session_state.get("ai_report_cache_key_v3")
                == report_cache_key
                and st.session_state.get("ai_report_cache_text_v3")
            ):
                report_ai_text = st.session_state[
                    "ai_report_cache_text_v3"
                ]

                st.success(
                    "Showing the saved report for the same data. "
                    "No new AI call was used."
                )

            else:
                report_ai_text = None

                try:
                    with st.spinner(
                        "AI is generating your compact performance report..."
                    ):
                        daily_ai_response = openai_client.responses.create(
                            model="gpt-5.4-mini",
                            input=daily_report_prompt,
                            max_output_tokens=1600
                        )

                    report_ai_text = daily_ai_response.output_text

                    st.session_state[
                        "ai_report_cache_key_v3"
                    ] = report_cache_key

                    st.session_state[
                        "ai_report_cache_text_v3"
                    ] = report_ai_text

                except Exception as report_ai_error:
                    st.error(
                        "AI Performance Report could not run right now. "
                        "If this is a rate-limit or credit issue, wait or add "
                        "API credit and try again once."
                    )
                    st.caption(
                        f"Technical detail: {report_ai_error}"
                    )

            if report_ai_text:
                st.subheader(
                    f"🤖 {report_period} AI Performance Report"
                )
                st.write(report_ai_text)


        # ==================================================
        # ACCOUNT HEALTH SCORE
        # ==================================================

        st.divider()
        st.header("🧠 Account Health Score")
        st.caption(f"Scope: {analysis_scope_label}")

        # Use the currently selected campaign/date-range data
        health_impressions = float(filtered_df["Impressions"].sum()) if "Impressions" in filtered_df.columns else 0
        health_clicks = float(filtered_df["Clicks"].sum()) if "Clicks" in filtered_df.columns else 0
        health_cost = float(filtered_df["Cost (₹)"].sum()) if "Cost (₹)" in filtered_df.columns else 0
        health_conversions = float(filtered_df["Conversions"].sum()) if "Conversions" in filtered_df.columns else 0
        health_calls = int(filtered_df["Calls"].sum()) if "Calls" in filtered_df.columns else 0

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
            if health_calls > 0:
                health_score -= 10
                health_notes.append(
                    f"🟠 No conversions recorded, but Google Ads reports {health_calls} calls. "
                    "Verify call-conversion tracking before judging lead quality."
                )
            else:
                health_score -= 20
                health_notes.append(
                    "🔴 No conversions or reported phone calls recorded for the selected data."
                )

        # Calls
        if health_calls > 0:
            health_notes.append(
                f"🟢 Google Ads reports {health_calls} phone calls for the selected data."
            )

        # Waste spend — clear-intent and Campaign Filter aligned
        if "selected_waste_df" in locals() and not selected_waste_df.empty:
            waste_amount = float(selected_waste_df["Cost (₹)"].sum())

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
        st.caption(f"Scope: {analysis_scope_label}")

        selected_spend = (
            float(filtered_df["Cost (₹)"].sum())
            if "Cost (₹)" in filtered_df.columns
            else 0.0
        )

        selected_clicks = (
            float(filtered_df["Clicks"].sum())
            if "Clicks" in filtered_df.columns
            else 0.0
        )

        selected_conversions = (
            float(filtered_df["Conversions"].sum())
            if "Conversions" in filtered_df.columns
            else 0.0
        )

        selected_calls = (
            int(filtered_df["Calls"].sum())
            if "Calls" in filtered_df.columns
            else 0
        )

        selected_cpa = (
            selected_spend / selected_conversions
            if selected_conversions > 0
            else 0.0
        )

        selected_conversion_rate = (
            (selected_conversions / selected_clicks) * 100
            if selected_clicks > 0
            else 0.0
        )

        waste_amount = 0.0
        review_amount = 0.0

        if "selected_waste_df" in locals() and not selected_waste_df.empty:
            if "Cost (₹)" in selected_waste_df.columns:
                waste_amount = float(
                    selected_waste_df["Cost (₹)"].sum()
                )

        if (
            "selected_review_spend_df" in locals()
            and not selected_review_spend_df.empty
            and "Cost (₹)" in selected_review_spend_df.columns
        ):
            review_amount = float(
                selected_review_spend_df["Cost (₹)"].sum()
            )

        waste_ratio = (
            (waste_amount / selected_spend) * 100
            if selected_spend > 0
            else 0.0
        )

        review_ratio = (
            (review_amount / selected_spend) * 100
            if selected_spend > 0
            else 0.0
        )

        # -----------------------------
        # WEIGHTED WASTE RISK SCORE V2
        # -----------------------------
        # Confirmed/clear irrelevant spend receives full risk weight.
        # Review Spend is uncertain, so it receives only partial weight.
        # CPA and conversion-rate pressure add efficiency risk.
        # Campaign-level phone calls are context only and never automatically
        # erase or prove search-term waste.

        confirmed_waste_points = min(
            60.0,
            waste_ratio * 2.0
        )

        review_exposure_points = min(
            25.0,
            review_ratio * 0.30
        )

        cpa_pressure_points = 0.0

        if selected_spend > 0 and selected_conversions <= 0:
            cpa_pressure_points = 20.0
        elif selected_cpa >= 2500:
            cpa_pressure_points = 20.0
        elif selected_cpa >= 1800:
            cpa_pressure_points = 15.0
        elif selected_cpa >= 1200:
            cpa_pressure_points = 10.0
        elif selected_cpa >= 800:
            cpa_pressure_points = 5.0

        conversion_rate_points = 0.0

        # Avoid overreacting to tiny click samples.
        if selected_clicks >= 20:
            if selected_conversion_rate < 2:
                conversion_rate_points = 15.0
            elif selected_conversion_rate < 4:
                conversion_rate_points = 10.0
            elif selected_conversion_rate < 6:
                conversion_rate_points = 5.0

        waste_risk_score = int(
            round(
                min(
                    100.0,
                    confirmed_waste_points
                    + review_exposure_points
                    + cpa_pressure_points
                    + conversion_rate_points
                )
            )
        )

        if waste_risk_score >= 80:
            waste_risk_status = "🔴 Critical"
        elif waste_risk_score >= 60:
            waste_risk_status = "🟠 High"
        elif waste_risk_score >= 40:
            waste_risk_status = "🟡 Moderate"
        elif waste_risk_score >= 20:
            waste_risk_status = "🟢 Low"
        else:
            waste_risk_status = "🟢 Very Low"

        risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

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

        with risk_col4:
            st.metric(
                "Review Spend",
                f"₹{review_amount:,.2f}"
            )

        st.progress(waste_risk_score / 100)

        st.write(
            f"Confirmed potential waste is **{waste_ratio:.1f}%** of selected spend; "
            f"Review Spend is **{review_ratio:.1f}%**. "
            f"Selected CPA: **₹{selected_cpa:,.2f}** | "
            f"Conversion Rate: **{selected_conversion_rate:.2f}%** | "
            f"Google Ads reported calls: **{selected_calls}**."
        )

        st.caption(
            "Risk score V2 = confirmed-waste exposure + 30% weighted Review Spend + "
            "CPA pressure + conversion-rate pressure. Review Spend is not treated as "
            "automatic waste. Google Ads phone_calls are campaign-level context only, "
            "so calls do not automatically remove search-term risk."
        )

        # -----------------------------
        # BUDGET INTELLIGENCE V2
        # -----------------------------

        st.subheader("💰 Budget Reallocation Suggestions")

        budget_actions = []

        if waste_amount > 0:
            budget_actions.append(
                f"🔴 **₹{waste_amount:,.2f} is clear Potential Waste.** "
                "Review those irrelevant-intent search terms first and add safe negative keywords."
            )

        if review_amount > 0:
            budget_actions.append(
                f"🟡 **₹{review_amount:,.2f} is Review Spend.** "
                "It is zero-conversion spend without a clear irrelevant-intent signal; "
                "review search intent, campaign fit and call quality before blocking it."
            )

        if waste_risk_score >= 60:
            budget_actions.append(
                "🔴 **Do not increase total budget yet.** "
                "Risk is high; clean search terms and improve conversion efficiency first."
            )
        elif waste_risk_score >= 40:
            budget_actions.append(
                "🟡 **Hold broad budget increases for now.** "
                "Optimize high-spend zero-conversion traffic and CPA before scaling."
            )
        elif waste_risk_score >= 20:
            budget_actions.append(
                "🟢 **Scale only selectively.** "
                "Risk is controlled but Review Spend still needs monitoring."
            )
        else:
            budget_actions.append(
                "🟢 **Waste risk is currently low.** "
                "Any budget increase should still depend on CPA, lead quality and conversion trend."
            )

        # Campaign-level CPA message — never call a single selected campaign
        # the 'strongest' campaign because there is nothing to compare it with.
        if selected_campaign != "All Campaigns":
            if selected_conversions > 0:
                if selected_cpa >= 1800:
                    budget_actions.append(
                        f"🟠 **Selected campaign CPA is ₹{selected_cpa:,.2f}.** "
                        "Improve efficiency before increasing its budget."
                    )
                else:
                    budget_actions.append(
                        f"🟢 **Selected campaign CPA is ₹{selected_cpa:,.2f}.** "
                        "Scale carefully only if lead quality is acceptable."
                    )
            elif selected_spend > 0:
                budget_actions.append(
                    f"🔴 **Selected campaign spent ₹{selected_spend:,.2f} with zero conversions.** "
                    "Review targeting, search terms and conversion tracking before adding budget."
                )

        else:
            if not filtered_df.empty and (
                "Cost (₹)" in filtered_df.columns
                and "Conversions" in filtered_df.columns
            ):
                budget_df = filtered_df.copy()

                budget_df["AI CPA"] = budget_df.apply(
                    lambda row: (
                        row["Cost (₹)"] / row["Conversions"]
                        if row["Conversions"] > 0
                        else float("inf")
                    ),
                    axis=1
                )

                converting_df = budget_df[
                    budget_df["Conversions"] > 0
                ].copy()

                if len(converting_df) >= 2:
                    best_campaign = converting_df.loc[
                        converting_df["AI CPA"].idxmin()
                    ]

                    best_campaign_name = (
                        best_campaign["Campaign"]
                        if "Campaign" in converting_df.columns
                        else "Best-performing campaign"
                    )

                    budget_actions.append(
                        "🟢 **Selective reallocation candidate:** "
                        f"{best_campaign_name} currently has the lowest CPA "
                        f"at ₹{best_campaign['AI CPA']:,.2f}."
                    )

                zero_conversion_df = budget_df[
                    (budget_df["Cost (₹)"] > 0)
                    & (budget_df["Conversions"] == 0)
                ].copy()

                if not zero_conversion_df.empty:
                    highest_zero_campaign = zero_conversion_df.loc[
                        zero_conversion_df["Cost (₹)"].idxmax()
                    ]

                    zero_campaign_name = (
                        highest_zero_campaign["Campaign"]
                        if "Campaign" in zero_conversion_df.columns
                        else "Zero-conversion campaign"
                    )

                    budget_actions.append(
                        "🔴 **Review before funding further:** "
                        f"{zero_campaign_name} spent "
                        f"₹{highest_zero_campaign['Cost (₹)']:,.2f} "
                        "with zero conversions."
                    )

        if not budget_actions:
            budget_actions.append(
                "🟢 Current budget distribution looks stable. "
                "Continue monitoring CPA, conversion rate and search-term quality."
            )

        for i, action in enumerate(
            budget_actions[:5],
            start=1
        ):
            st.write(
                f"**{i}. {action}**"
            )

        # -----------------------------
        # TOP 5 ACTIONS NOW V2
        # -----------------------------

        st.subheader("🎯 Top 5 Actions Now")

        top_actions = []

        if waste_amount > 0:
            top_actions.append(
                "Add safe negative keywords for clear irrelevant-intent search terms."
            )

        if review_ratio >= 20:
            top_actions.append(
                "Review the highest-spend zero-conversion search terms before scaling."
            )

        if selected_cpa >= 1500:
            top_actions.append(
                "Reduce high-CPA traffic before increasing budget."
            )

        if selected_clicks >= 20 and selected_conversion_rate < 5:
            top_actions.append(
                "Improve landing-page and lead-conversion flow."
            )

        if selected_conversions > 0:
            top_actions.append(
                "Protect converting search intent and avoid broad negative keywords."
            )

        if selected_calls > 0:
            top_actions.append(
                "Check call quality and confirm valuable calls are tracked as conversions."
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
        st.caption(f"Scope: {analysis_scope_label}")


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
        # AI CAMPAIGN BUILDER
        # ==================================================

        st.divider()
        st.header("🚀 AI Campaign Builder")
        st.caption(
            "AI Draft → Validate Only → Create as PAUSED. "
            "The campaign cannot serve ads until you manually enable it in Google Ads."
        )

        campaign_builder_services = [
            "Elderly Care",
            "Patient Care",
            "Nursing Care",
            "Baby Care",
            "Caretaker",
            "Domestic Help / Maid",
        ]

        builder_col1, builder_col2 = st.columns(2)

        with builder_col1:
            builder_service = st.selectbox(
                "Service",
                campaign_builder_services,
                key="campaign_builder_service",
            )

            builder_campaign_name = st.text_input(
                "Campaign Name",
                value=f"HK | {builder_service} | Hyderabad | Search",
                key="campaign_builder_campaign_name",
            )

            builder_daily_budget = st.number_input(
                "Daily Budget (₹)",
                min_value=100.0,
                max_value=100000.0,
                value=1500.0,
                step=100.0,
                key="campaign_builder_daily_budget",
            )

            builder_location = st.text_input(
                "Target Location",
                value="Hyderabad",
                key="campaign_builder_location",
            )

        with builder_col2:
            builder_languages = st.multiselect(
                "Languages",
                list(CAMPAIGN_BUILDER_LANGUAGE_IDS.keys()),
                default=["English"],
                key="campaign_builder_languages",
            )

            builder_bidding = st.selectbox(
                "Bidding Strategy",
                ["Maximize Conversions", "Manual CPC"],
                index=0,
                key="campaign_builder_bidding",
            )

            if builder_bidding == "Manual CPC":
                builder_manual_cpc = st.number_input(
                    "Max CPC Bid (₹)",
                    min_value=1.0,
                    max_value=10000.0,
                    value=50.0,
                    step=5.0,
                    key="campaign_builder_manual_cpc",
                )
            else:
                builder_manual_cpc = 0.0

            builder_final_url = st.text_input(
                "Final URL",
                value="https://hareekrishna.com/",
                key="campaign_builder_final_url",
            )

        st.info(
            "Safety: AI generation only creates a draft. "
            "Validate Only makes no Google Ads changes. "
            "Actual creation always creates the campaign as PAUSED."
        )

        generate_builder_draft = st.button(
            "✨ Generate AI Campaign Draft",
            key="generate_ai_campaign_builder_draft",
            width="stretch",
        )

        if generate_builder_draft:
            builder_input_errors = []

            if not builder_campaign_name.strip():
                builder_input_errors.append("Campaign Name is required.")

            if not builder_location.strip():
                builder_input_errors.append("Target Location is required.")

            if not builder_languages:
                builder_input_errors.append("Select at least one language.")

            if not campaign_builder_valid_url(builder_final_url):
                builder_input_errors.append(
                    "Enter a valid Final URL starting with http:// or https://."
                )

            if builder_input_errors:
                for builder_error in builder_input_errors:
                    st.error(builder_error)
            else:
                builder_ai_prompt = f"""
You are a Google Ads Search campaign builder for a home-care services business.

Return ONLY one valid JSON object. Do not use markdown fences.

CAMPAIGN GOAL:
- Generate qualified phone-call and lead intent.
- Service: {builder_service}
- Location: {builder_location}
- Languages: {', '.join(builder_languages)}
- Final URL: {builder_final_url}

BUSINESS SERVICES:
- Home Care
- Elderly Care
- Patient Care
- Nursing Care
- Baby Care / Babysitter / Nanny
- Caretaker / Caregiver
- Domestic Help / Maid / Housekeeping / Cook

OWN BRAND - NEVER SUGGEST AS A NEGATIVE:
- Hare Krishna
- Harekrishna
- Harekrishna Home Care Services

REQUIREMENTS:
- One tightly themed Search ad group for the selected service.
- 12 to 20 high-intent keywords.
- Prefer PHRASE and EXACT match. Use BROAD only when clearly justified.
- Do not add unrelated or informational keywords.
- Negative keywords must be only clearly irrelevant intent such as jobs,
  vacancies, salary, course, training, free, PDF, meaning, definition, etc.
- Do not make any offered service or own brand a negative keyword.
- Create 10 to 15 unique RSA headlines, each <= 30 characters.
- Create 3 to 4 unique RSA descriptions, each <= 90 characters.
- Avoid unverifiable claims such as #1, guaranteed, cheapest, best in India.
- Use practical call/lead intent without promising unavailable staff.
- path1 and path2 must be lowercase URL path words, <= 15 characters each.

JSON SCHEMA:
{{
  "ad_group_name": "string",
  "keywords": [
    {{"text": "keyword", "match_type": "PHRASE"}}
  ],
  "negative_keywords": [
    {{"text": "negative", "match_type": "PHRASE"}}
  ],
  "headlines": ["headline"],
  "descriptions": ["description"],
  "path1": "string",
  "path2": "string"
}}
"""

                builder_ai_cache_key = campaign_builder_fingerprint(
                    {
                        "service": builder_service,
                        "location": builder_location,
                        "languages": builder_languages,
                        "final_url": builder_final_url,
                    }
                )

                try:
                    if (
                        st.session_state.get("campaign_builder_ai_cache_key")
                        == builder_ai_cache_key
                        and st.session_state.get("campaign_builder_ai_cache_draft")
                    ):
                        builder_draft = st.session_state[
                            "campaign_builder_ai_cache_draft"
                        ]
                        st.success(
                            "Saved AI draft reused for the same setup. "
                            "No new OpenAI call was used."
                        )
                    else:
                        with st.spinner("AI is building the campaign draft..."):
                            builder_ai_response = openai_client.responses.create(
                                model="gpt-5.4-mini",
                                input=builder_ai_prompt,
                                max_output_tokens=2200,
                            )

                        raw_builder_draft = campaign_builder_extract_json(
                            builder_ai_response.output_text
                        )
                        builder_draft = campaign_builder_sanitize_draft(
                            raw_builder_draft,
                            builder_service,
                            builder_location,
                        )

                        st.session_state[
                            "campaign_builder_ai_cache_key"
                        ] = builder_ai_cache_key
                        st.session_state[
                            "campaign_builder_ai_cache_draft"
                        ] = builder_draft

                    st.session_state["campaign_builder_draft"] = builder_draft
                    st.session_state.pop(
                        "campaign_builder_validated_fingerprint",
                        None,
                    )
                    st.session_state.pop(
                        "campaign_builder_validated_location",
                        None,
                    )

                    for edit_key in [
                        "campaign_builder_ad_group_edit",
                        "campaign_builder_keywords_edit",
                        "campaign_builder_negatives_edit",
                        "campaign_builder_headlines_edit",
                        "campaign_builder_descriptions_edit",
                        "campaign_builder_path1_edit",
                        "campaign_builder_path2_edit",
                    ]:
                        st.session_state.pop(edit_key, None)

                    st.rerun()

                except Exception as builder_ai_error:
                    st.error(
                        "AI campaign draft could not be generated. "
                        f"Technical detail: {builder_ai_error}"
                    )

        builder_draft = st.session_state.get("campaign_builder_draft")

        if builder_draft:
            st.subheader("📝 Review & Edit AI Draft")

            builder_ad_group_name = st.text_input(
                "Ad Group Name",
                value=builder_draft["ad_group_name"],
                key="campaign_builder_ad_group_edit",
            )

            edit_col1, edit_col2 = st.columns(2)

            with edit_col1:
                builder_keyword_text = st.text_area(
                    "Keywords — one per line: keyword | MATCH_TYPE",
                    value=campaign_builder_keyword_lines(
                        builder_draft["keywords"]
                    ),
                    height=280,
                    key="campaign_builder_keywords_edit",
                )

                builder_negative_text = st.text_area(
                    "Negative Keywords — one per line: keyword | MATCH_TYPE",
                    value=campaign_builder_keyword_lines(
                        builder_draft["negative_keywords"]
                    ),
                    height=220,
                    key="campaign_builder_negatives_edit",
                )

            with edit_col2:
                builder_headlines_text = st.text_area(
                    "RSA Headlines — one per line (max 30 chars)",
                    value="\n".join(builder_draft["headlines"]),
                    height=280,
                    key="campaign_builder_headlines_edit",
                )

                builder_descriptions_text = st.text_area(
                    "RSA Descriptions — one per line (max 90 chars)",
                    value="\n".join(builder_draft["descriptions"]),
                    height=220,
                    key="campaign_builder_descriptions_edit",
                )

            path_col1, path_col2 = st.columns(2)

            with path_col1:
                builder_path1 = st.text_input(
                    "Display Path 1",
                    value=builder_draft.get("path1", ""),
                    key="campaign_builder_path1_edit",
                )

            with path_col2:
                builder_path2 = st.text_input(
                    "Display Path 2",
                    value=builder_draft.get("path2", ""),
                    key="campaign_builder_path2_edit",
                )

            current_builder_draft = campaign_builder_sanitize_draft(
                {
                    "ad_group_name": builder_ad_group_name,
                    "keywords": campaign_builder_parse_keyword_lines(
                        builder_keyword_text,
                        negative=False,
                    ),
                    "negative_keywords": campaign_builder_parse_keyword_lines(
                        builder_negative_text,
                        negative=True,
                    ),
                    "headlines": [
                        line.strip()
                        for line in builder_headlines_text.splitlines()
                        if line.strip()
                    ],
                    "descriptions": [
                        line.strip()
                        for line in builder_descriptions_text.splitlines()
                        if line.strip()
                    ],
                    "path1": builder_path1,
                    "path2": builder_path2,
                },
                builder_service,
                builder_location,
            )

            builder_core_payload = {
                "service": builder_service,
                "campaign_name": campaign_builder_clip_text(
                    builder_campaign_name,
                    255,
                ),
                "daily_budget": float(builder_daily_budget),
                "location_text": builder_location.strip(),
                "languages": sorted(builder_languages),
                "language_ids": [
                    CAMPAIGN_BUILDER_LANGUAGE_IDS[name]
                    for name in sorted(builder_languages)
                ],
                "bidding_strategy": builder_bidding,
                "manual_cpc_bid": float(builder_manual_cpc),
                "final_url": builder_final_url.strip(),
                "ad_group_name": current_builder_draft["ad_group_name"],
                "keywords": current_builder_draft["keywords"],
                "negative_keywords": current_builder_draft[
                    "negative_keywords"
                ],
                "headlines": current_builder_draft["headlines"],
                "descriptions": current_builder_draft["descriptions"],
                "path1": current_builder_draft["path1"],
                "path2": current_builder_draft["path2"],
            }

            builder_current_fingerprint = campaign_builder_fingerprint(
                builder_core_payload
            )

            st.subheader("🔎 Campaign Preview")

            preview_settings = pd.DataFrame(
                [
                    ["Campaign", builder_core_payload["campaign_name"]],
                    ["Status", "PAUSED"],
                    ["Service", builder_service],
                    ["Daily Budget", f"₹{builder_daily_budget:,.2f}"],
                    ["Location", builder_location],
                    ["Languages", ", ".join(builder_languages)],
                    ["Bidding", builder_bidding],
                    ["Final URL", builder_final_url],
                    ["Ad Group", builder_core_payload["ad_group_name"]],
                    ["Keywords", len(builder_core_payload["keywords"])],
                    [
                        "Negative Keywords",
                        len(builder_core_payload["negative_keywords"]),
                    ],
                    ["Headlines", len(builder_core_payload["headlines"])],
                    [
                        "Descriptions",
                        len(builder_core_payload["descriptions"]),
                    ],
                ],
                columns=["Setting", "Value"],
            )
            st.dataframe(preview_settings, hide_index=True, width="stretch")

            preview_col1, preview_col2 = st.columns(2)

            with preview_col1:
                st.markdown("**Keywords**")
                st.dataframe(
                    pd.DataFrame(builder_core_payload["keywords"]),
                    hide_index=True,
                    width="stretch",
                )

                st.markdown("**Negative Keywords**")
                if builder_core_payload["negative_keywords"]:
                    st.dataframe(
                        pd.DataFrame(
                            builder_core_payload["negative_keywords"]
                        ),
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.caption("No campaign-level negative keywords in this draft.")

            with preview_col2:
                st.markdown("**Responsive Search Ad**")
                st.write("Headlines:")
                for headline in builder_core_payload["headlines"]:
                    st.write(f"• {headline}")

                st.write("Descriptions:")
                for description in builder_core_payload["descriptions"]:
                    st.write(f"• {description}")

            builder_validation_errors = []

            if not builder_core_payload["campaign_name"]:
                builder_validation_errors.append("Campaign Name is required.")

            if not campaign_builder_valid_url(builder_core_payload["final_url"]):
                builder_validation_errors.append("Final URL is invalid.")

            if not builder_languages:
                builder_validation_errors.append("Select at least one language.")

            if len(builder_core_payload["keywords"]) < 1:
                builder_validation_errors.append("At least one keyword is required.")

            if len(builder_core_payload["headlines"]) < 3:
                builder_validation_errors.append(
                    "Responsive Search Ad requires at least 3 headlines."
                )

            if len(builder_core_payload["descriptions"]) < 2:
                builder_validation_errors.append(
                    "Responsive Search Ad requires at least 2 descriptions."
                )

            if builder_validation_errors:
                for builder_error in builder_validation_errors:
                    st.error(builder_error)

            validate_campaign_button = st.button(
                "🧪 Validate Full Campaign — No Changes",
                key="validate_ai_campaign_builder",
                disabled=bool(builder_validation_errors),
                width="stretch",
            )

            if validate_campaign_button:
                try:
                    with st.spinner(
                        "Resolving location and validating the full Google Ads campaign..."
                    ):
                        resolved_location = campaign_builder_resolve_location(
                            client,
                            builder_location,
                        )

                        validated_payload = dict(builder_core_payload)
                        validated_payload["location_resource_name"] = (
                            resolved_location["resource_name"]
                        )

                        campaign_builder_mutate(
                            client,
                            ga_service,
                            customer_id,
                            validated_payload,
                            validate_only=True,
                        )

                    st.session_state[
                        "campaign_builder_validated_fingerprint"
                    ] = builder_current_fingerprint
                    st.session_state[
                        "campaign_builder_validated_location"
                    ] = resolved_location

                    st.success(
                        "✅ VALIDATION PASS — Google Ads accepted the full request. "
                        "Nothing was created."
                    )
                    st.caption(
                        "Resolved location: "
                        f"{resolved_location.get('canonical_name') or resolved_location.get('name')}"
                    )

                except Exception as builder_validate_error:
                    st.session_state.pop(
                        "campaign_builder_validated_fingerprint",
                        None,
                    )
                    st.session_state.pop(
                        "campaign_builder_validated_location",
                        None,
                    )
                    st.error("❌ VALIDATION FAILED")
                    st.code(
                        campaign_builder_format_google_ads_error(
                            builder_validate_error
                        )
                    )

            validated_fingerprint = st.session_state.get(
                "campaign_builder_validated_fingerprint"
            )
            validation_is_current = (
                validated_fingerprint == builder_current_fingerprint
            )

            if validation_is_current:
                st.success(
                    "✅ Current draft is validated and ready for PAUSED creation."
                )
            elif validated_fingerprint:
                st.warning(
                    "Draft settings changed after validation. "
                    "Run Validate Full Campaign again before creating."
                )
            else:
                st.caption(
                    "Run Validate Full Campaign first. "
                    "Create stays locked until validation passes."
                )

            builder_confirm_create = st.checkbox(
                "I confirm: create this campaign in Google Ads as PAUSED.",
                key="campaign_builder_confirm_create",
            )

            create_campaign_button = st.button(
                "🚀 Create PAUSED Campaign in Google Ads",
                key="create_ai_campaign_builder",
                disabled=(
                    bool(builder_validation_errors)
                    or not validation_is_current
                    or not builder_confirm_create
                ),
                width="stretch",
            )

            if create_campaign_button:
                try:
                    validated_location = st.session_state.get(
                        "campaign_builder_validated_location"
                    )

                    if not validated_location:
                        raise ValueError(
                            "Validated location is missing. Please validate again."
                        )

                    create_payload = dict(builder_core_payload)
                    create_payload["location_resource_name"] = (
                        validated_location["resource_name"]
                    )

                    with st.spinner(
                        "Creating budget, PAUSED campaign, targeting, ad group, "
                        "keywords and responsive search ad..."
                    ):
                        create_response = campaign_builder_mutate(
                            client,
                            ga_service,
                            customer_id,
                            create_payload,
                            validate_only=False,
                        )

                    campaign_resource_name = (
                        create_response.mutate_operation_responses[1]
                        .campaign_result.resource_name
                    )
                    campaign_id = campaign_resource_name.rsplit("/", 1)[-1]

                    st.session_state[
                        "campaign_builder_last_created_campaign_id"
                    ] = campaign_id
                    st.session_state[
                        "campaign_builder_last_created_resource"
                    ] = campaign_resource_name
                    st.session_state.pop(
                        "campaign_builder_validated_fingerprint",
                        None,
                    )
                    st.session_state.pop(
                        "campaign_builder_validated_location",
                        None,
                    )
                    st.success(
                        "✅ Campaign created successfully as PAUSED. "
                        f"Google Ads Campaign ID: {campaign_id}"
                    )
                    st.warning(
                        "Do not enable it until you review budget, location, "
                        "keywords, negatives, ad copy and conversion settings in Google Ads."
                    )

                except Exception as builder_create_error:
                    st.error("❌ Campaign creation failed. No partial campaign should be created because the request is atomic.")
                    st.code(
                        campaign_builder_format_google_ads_error(
                            builder_create_error
                        )
                    )

        else:
            st.caption(
                "Choose the campaign settings above and click "
                "Generate AI Campaign Draft."
            )

        # ==================================================
        # ASK AI
        # ==================================================

        st.divider()
        st.header("🤖 Ask AI About Your Campaign")
        st.caption(f"Scope: {analysis_scope_label}")

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

        current_ai_scope = f"{current_ai_period}|{selected_campaign}"

        if "ai_chat_period" not in st.session_state:
            st.session_state.ai_chat_period = current_ai_scope

        elif st.session_state.ai_chat_period != current_ai_scope:
            st.session_state.ai_chat_history = []
            st.session_state.ai_chat_period = current_ai_scope

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
                # ASK AI SEARCH-TERM CONTEXT
                # QUESTION-RELATED + TOP-15 TOKEN-EFFICIENT VERSION
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

                competitor_question = any(
                    phrase in question_lower
                    for phrase in [
                        "competitor",
                        "competitors",
                        "competition",
                        "competitor name",
                        "competitor names",
                        "కాంపిటిటర్",
                        "కాంపిటిటర్స్"
                    ]
                )

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
                        )

                        # AI receives only terms with actual spend.
                        search_terms_for_ai = search_terms_for_ai[
                            search_terms_for_ai["Cost (₹)"] > 0
                        ].copy()

                        # ------------------------------------------
                        # QUESTION-RELATED SERVICE FILTER
                        # ------------------------------------------

                        service_question_groups = [
                            (["nursing", "nurse"], ["nursing", "nurse"]),
                            (["patient"], ["patient"]),
                            (["elderly", "senior", "old age"], ["elderly", "senior", "old age"]),
                            (["baby", "babysitter", "nanny"], ["baby", "babysitter", "nanny"]),
                            (["caretaker", "care taker", "caregiver", "attendant"], ["caretaker", "care taker", "caregiver", "attendant"]),
                            (["maid", "domestic help", "housekeeping", "housekeeper", "cook"], ["maid", "domestic help", "housekeeping", "housekeeper", "cook"]),
                            (["home care", "homecare"], ["home care", "homecare"])
                        ]

                        matched_service_terms = []

                        for question_phrases, term_phrases in service_question_groups:
                            if any(
                                phrase in question_lower
                                for phrase in question_phrases
                            ):
                                matched_service_terms.extend(term_phrases)

                        if negative_keyword_question:
                            selected_search_terms_for_ai = (
                                search_terms_for_ai[
                                    search_terms_for_ai["Conversions"] == 0
                                ]
                                .sort_values(
                                    "Cost (₹)",
                                    ascending=False
                                )
                                .head(15)
                                .copy()
                            )

                        elif competitor_question:
                            # Prefer the saved Brand Scan results when the user has
                            # explicitly run them for the current scope. Otherwise use
                            # only a conservative local candidate filter; do not invent
                            # confirmed competitors.
                            saved_brand_results = st.session_state.get(
                                "growth_brand_results_df",
                                pd.DataFrame(),
                            )
                            saved_brand_is_current = (
                                st.session_state.get("growth_brand_scope_key")
                                == brand_scope_key
                            )

                            if (
                                saved_brand_is_current
                                and isinstance(saved_brand_results, pd.DataFrame)
                                and not saved_brand_results.empty
                            ):
                                saved_brand_subset = saved_brand_results[
                                    saved_brand_results["Type"].isin(
                                        ["COMPETITOR", "AMBIGUOUS"]
                                    )
                                ].copy()

                                competitor_ask_columns = [
                                    "Search Term",
                                    "Campaign",
                                    "Clicks",
                                    "Cost (₹)",
                                    "Conversions",
                                    "Type",
                                    "Competitor Name",
                                    "Confidence",
                                    "Recommended Action",
                                ]
                                competitor_ask_columns = [
                                    col
                                    for col in competitor_ask_columns
                                    if col in saved_brand_subset.columns
                                ]
                                selected_search_terms_for_ai = (
                                    saved_brand_subset[competitor_ask_columns]
                                    .sort_values("Cost (₹)", ascending=False)
                                    .head(15)
                                    .copy()
                                )
                            else:
                                local_candidate_mask = search_terms_for_ai[
                                    "Search Term"
                                ].apply(
                                    lambda term: growth_brand_candidate_score(term) > 0
                                )
                                local_candidate_df = search_terms_for_ai[
                                    local_candidate_mask
                                ].copy()

                                if not local_candidate_df.empty:
                                    selected_search_terms_for_ai = (
                                        local_candidate_df
                                        .sort_values("Cost (₹)", ascending=False)
                                        .head(15)
                                        .copy()
                                    )
                                else:
                                    selected_search_terms_for_ai = (
                                        search_terms_for_ai
                                        .sort_values("Cost (₹)", ascending=False)
                                        .head(15)
                                        .copy()
                                    )

                        elif matched_service_terms:
                            service_mask = search_terms_for_ai[
                                "Search Term"
                            ].astype(str).str.lower().apply(
                                lambda term: any(
                                    phrase in term
                                    for phrase in matched_service_terms
                                )
                            )

                            service_filtered_df = search_terms_for_ai[
                                service_mask
                            ].copy()

                            if not service_filtered_df.empty:
                                selected_search_terms_for_ai = (
                                    service_filtered_df
                                    .sort_values(
                                        "Cost (₹)",
                                        ascending=False
                                    )
                                    .head(15)
                                    .copy()
                                )
                            else:
                                selected_search_terms_for_ai = (
                                    search_terms_for_ai
                                    .sort_values(
                                        "Cost (₹)",
                                        ascending=False
                                    )
                                    .head(15)
                                    .copy()
                                )

                        else:
                            # General questions: combine high-spend terms with
                            # a few converting terms so AI sees both risk and quality.
                            high_spend_terms = (
                                search_terms_for_ai
                                .sort_values(
                                    "Cost (₹)",
                                    ascending=False
                                )
                                .head(10)
                            )

                            converting_terms = (
                                search_terms_for_ai[
                                    search_terms_for_ai["Conversions"] > 0
                                ]
                                .sort_values(
                                    ["Conversions", "Cost (₹)"],
                                    ascending=[False, False]
                                )
                                .head(5)
                            )

                            selected_search_terms_for_ai = (
                                pd.concat(
                                    [high_spend_terms, converting_terms],
                                    ignore_index=True
                                )
                                .drop_duplicates(
                                    subset=["Search Term", "Campaign"]
                                )
                                .head(15)
                                .copy()
                            )

                        search_terms_context = (
                            selected_search_terms_for_ai
                            .to_string(index=False)
                        )

                    else:
                        selected_search_terms_for_ai = (
                            search_terms_for_ai
                            .head(15)
                            .copy()
                        )

                        search_terms_context = (
                            selected_search_terms_for_ai
                            .to_string(index=False)
                        )

                    search_terms_available = True

                else:
                    search_terms_context = (
                        "No Search Terms data is available "
                        "for the selected date range."
                    )

                    search_terms_available = False

                # ==================================================
                # COMPETITOR CONTEXT FOR ASK AI
                # ==================================================

                competitor_context = (
                    "No current competitor scan result has been loaded. "
                    "Do not invent competitor names or auction metrics."
                )

                if competitor_question:
                    competitor_context_parts = []

                    saved_auction_df = st.session_state.get(
                        "growth_auction_current_df",
                        pd.DataFrame(),
                    )
                    if (
                        st.session_state.get("growth_auction_scope_key")
                        == auction_scope_key
                        and isinstance(saved_auction_df, pd.DataFrame)
                        and not saved_auction_df.empty
                    ):
                        auction_context_columns = [
                            "Keyword",
                            "Competitor Domain",
                            "Campaign",
                            "Overlap Rate %",
                            "Position Above Rate %",
                            "Competitor Impression Share %",
                            "Threat Score",
                            "Threat",
                        ]
                        auction_context_columns = [
                            col
                            for col in auction_context_columns
                            if col in saved_auction_df.columns
                        ]
                        competitor_context_parts.append(
                            "AUCTION INSIGHTS (confirmed keyword/domain overlap):\n"
                            + saved_auction_df[auction_context_columns]
                            .sort_values("Threat Score", ascending=False)
                            .head(15)
                            .to_string(index=False)
                        )

                    saved_brand_summary = st.session_state.get(
                        "growth_brand_summary_df",
                        pd.DataFrame(),
                    )
                    if (
                        st.session_state.get("growth_brand_scope_key")
                        == brand_scope_key
                        and isinstance(saved_brand_summary, pd.DataFrame)
                        and not saved_brand_summary.empty
                    ):
                        brand_context_columns = [
                            "Competitor Name",
                            "Search Terms",
                            "Clicks",
                            "Spend (₹)",
                            "Conversions",
                            "Review Risk",
                        ]
                        brand_context_columns = [
                            col
                            for col in brand_context_columns
                            if col in saved_brand_summary.columns
                        ]
                        competitor_context_parts.append(
                            "COMPETITOR BRAND SEARCHES (user query intent, not auction overlap):\n"
                            + saved_brand_summary[brand_context_columns]
                            .head(15)
                            .to_string(index=False)
                        )

                    if competitor_context_parts:
                        competitor_context = "\n\n".join(competitor_context_parts)

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
                    # COMPACT CAMPAIGN CONTEXT FOR ASK AI
                    # ==================================================

                    ask_campaign_columns = [
                        col
                        for col in [
                            "Campaign",
                            "Impressions",
                            "Clicks",
                            "Calls",
                            "Cost (₹)",
                            "Conversions",
                            "CTR %",
                            "Avg CPC (₹)",
                            "CPA (₹)"
                        ]
                        if col in filtered_df.columns
                    ]

                    if ask_campaign_columns:
                        ask_campaign_df = filtered_df[
                            ask_campaign_columns
                        ].copy()

                        if "Cost (₹)" in ask_campaign_df.columns:
                            ask_campaign_df = ask_campaign_df.sort_values(
                                "Cost (₹)",
                                ascending=False
                            )

                        ask_campaign_df = ask_campaign_df.head(5)
                        ask_campaign_context = ask_campaign_df.to_string(
                            index=False
                        )
                    else:
                        ask_campaign_context = (
                            "Campaign detail is unavailable."
                        )

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
        - Calls are campaign/account-level in this dashboard, not search-term-level.
        - Never claim that a specific Search Term generated or did not generate a phone call.
        - If conversions are zero but Calls are greater than zero, recommend checking call-conversion tracking before labeling traffic as no-lead traffic.

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

        CAMPAIGN DATA (TOP 5 BY SPEND):
        {ask_campaign_context}

        SEARCH TERMS DATA (QUESTION-RELEVANT / IMPORTANT, MAX 15 WITH SPEND):
        {search_terms_context}

        COMPETITOR INTELLIGENCE (only if a scan was run for this scope):
        {competitor_context}

        BEFORE VS AFTER DATA:
        {before_after_context}

        SELECTED-SCOPE METRICS ({analysis_scope_label}):
        Impressions: {total_impressions}
        Clicks: {total_clicks}
        Calls: {total_calls}
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

                    ask_ai_cache_key = (
                        f"v5|{current_ai_period}|{selected_campaign}|{total_calls}|"
                        f"{question}|{ask_campaign_context}|"
                        f"{search_terms_context}|{competitor_context}|"
                        f"{before_after_context}"
                    )

                    if (
                        st.session_state.get("ask_ai_cache_key_v3")
                        == ask_ai_cache_key
                        and st.session_state.get("ask_ai_cache_text_v3")
                    ):
                        assistant_text = st.session_state[
                            "ask_ai_cache_text_v3"
                        ]

                        st.success(
                            "Showing the saved answer for the same question "
                            "and same data. No new AI call was used."
                        )

                    else:
                        try:
                            with st.spinner("AI is analyzing..."):

                                ai_response = openai_client.responses.create(
                                    model="gpt-5.4-mini",
                                    input=prompt,
                                    max_output_tokens=1400
                                )

                            assistant_text = ai_response.output_text

                            st.session_state[
                                "ask_ai_cache_key_v3"
                            ] = ask_ai_cache_key

                            st.session_state[
                                "ask_ai_cache_text_v3"
                            ] = assistant_text

                        except Exception as ask_ai_error:
                            telugu_question = any(
                                "\u0c00" <= char <= "\u0c7f"
                                for char in question
                            )

                            if telugu_question:
                                assistant_text = (
                                    "AI ఇప్పుడు run కాలేదు. API credit / rate limit "
                                    "issue ఉంటే కొంతసేపటి తర్వాత లేదా credit add "
                                    "చేసిన తర్వాత మళ్లీ ఒక్కసారి try చేయండి."
                                )
                            else:
                                assistant_text = (
                                    "AI could not run right now. If this is an "
                                    "API credit or rate-limit issue, wait or add "
                                    "credit and try again once."
                                )

                            st.caption(
                                f"Technical detail: {ask_ai_error}"
                            )

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
