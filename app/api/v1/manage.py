import json
import time
from fastapi import APIRouter, Depends
from typing import Dict, Any, List, Optional

from fastapi.responses import JSONResponse
import pycountry
from dependencies import User, get_current_user
from services.cloud import supabase, postgresql
from babel.numbers import get_currency_symbol

router = APIRouter()


def get_listers_filters(country) -> List[Dict[str, Any]]:
    listers = postgresql.direct_query(
        "SELECT id, name, bf_logo FROM tb2.feeds WHERE markets @> %s::jsonb AND status = 'ACTIVE';",
        params=(json.dumps([country]),),
    )
    lister_list = [
        {"id": row["id"], "name": row["name"], "icon": row["bf_logo"]}
        for row in listers
        if row["name"]
    ]

    return [
        {
            "key": "lister",
            "label": "Shop",
            "multiSelect": True,
            "options": [
                {
                    "icon": lister["icon"],
                    "label": lister["name"].upper(),
                    "value": lister["id"],
                }
                for lister in lister_list
            ],
        }
    ]


def get_brand_filters() -> List[Dict[str, Any]]:
    brands = postgresql.direct_query("SELECT DISTINCT(brand) FROM tb2.products;")
    brand_list = [row["brand"] for row in brands if row["brand"]]

    return [
        {
            "key": "brand",
            "label": "Brand",
            "multiSelect": True,
            "options": [{"label": b, "value": b} for b in brand_list],
        }
    ]


def get_gender_filters(gender: Optional[str]) -> List[Dict[str, Any]]:

    return [
        {
            "key": "gender",
            "label": "Gender",
            "multiSelect": True,
            "selected": [gender] if gender else [],
            "options": [
                {"label": "Woman", "value": "female"},
                {"label": "Man", "value": "male"},
                {"label": "Boy", "value": "boy"},
                {"label": "Girl", "value": "girl"},
            ],
        }
    ]


def get_price_filter(currency: Optional[str] = "DKK") -> Dict[str, Any]:

    return {
        "key": "price",
        "label": f"Price ({currency})",
        "type": "slider",
        "multiSelect": False,
        "range": {"min": 0, "max": 2000, "step": 50},
        "defaultValue": [0, 1000],
        "currency": currency,
    }


@router.get("/get-filters")
def get_user(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    start_time = time.time()

    filters: List[Dict[str, Any]] = []
    filters += get_brand_filters()
    filters += get_gender_filters(user.gender)
    filters += get_listers_filters(user.country)
    # filters.append(get_price_filter(user.currency))

    return JSONResponse(
        content={"filters": filters}, media_type="application/json; charset=utf-8"
    )


@router.get("/get-details")
def get_user(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    start_time = time.time()

    searches = (
        supabase.table("searches")
        .select("id, s3_key", count="exact")
        .order("created_at", desc=True)
        .limit(24)
        .eq("user", user.id)
        .execute()
    )
    searches_time = time.time() - start_time
    print(f"Time to query searches: {searches_time:.4f} seconds")

    liked_start_time = time.time()
    likedProductsCount = (
        supabase.table("liked_products")
        .select("product", count="exact")
        .eq("user", user.id)
        .execute()
    )
    liked_time = time.time() - liked_start_time
    print(f"Time to query liked products: {liked_time:.4f} seconds")

    total_time = time.time() - start_time
    print(f"Total get-details endpoint time: {total_time:.4f} seconds")

    return {
        "searchesCount": searches.count,
        "searches": searches.data,
        "likedProductsCount": likedProductsCount.count,
    }


@router.get("/get-search")
def get_search(
    search_id: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    start_time = time.time()

    detection = (
        supabase.table("searches")
        .select("id, s3_key, detections(id, label, confidence, bbox, mask, search)")
        .eq("id", search_id)
        .single()
        .execute()
    )
    query_time = time.time() - start_time
    print(f"Time to get search data: {query_time:.4f} seconds")

    return detection.data


@router.get("/onboarding")
def get_onboarding_options() -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns onboarding options for country, gender, and currency.
    Does not require authentication.
    """

    # which countries & currencies we actually want to show
    VISIBLE_COUNTRIES = {"DK", "SE", "DE", "NO"}
    VISIBLE_CURRENCIES = {"DKK", "SEK", "NOK", "EUR", "USD"}

    # --- countries as before ---
    countries = []
    for country in pycountry.countries:
        code = country.alpha_2
        flag = "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code)
        countries.append(
            {
                "value": code,
                "label": f"{flag} {country.name}",
                "hidden": code not in VISIBLE_COUNTRIES,
            }
        )

    # --- genders as before ---
    genders = [
        {"value": "female", "label": "Woman"},
        {"value": "male", "label": "Man"},
    ]

    # --- currencies, generated dynamically ---
    currencies = []
    for cur in pycountry.currencies:
        code = cur.alpha_3
        # get the symbol (falls back to code if unknown)
        try:
            symbol = get_currency_symbol(code, locale="en")
        except:
            symbol = code
        # build a label like "€ Euro (EUR)"
        label = f"{symbol} {cur.name} ({code})"
        currencies.append(
            {
                "value": code,
                "label": code,
                "hidden": code not in VISIBLE_CURRENCIES,
            }
        )

    return JSONResponse(
        {"country": countries, "gender": genders, "currency": currencies},
        media_type="application/json; charset=utf-8",
    )
