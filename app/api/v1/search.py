import hashlib
import json
from typing import Any, Dict, List


from cachetools import TTLCache

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.v1.like import mark_liked_products
from dependencies import User, get_current_user
from services.product_search import vectorSearch

from services.cloud import supabase

from currency_converter import CurrencyConverter
import logging

logger = logging.getLogger(__name__)
convertCurrency = CurrencyConverter().convert

router = APIRouter()


def _group_products(
    raw_products: List[Dict[str, Any]],
    product_conf: Dict[str, float],
    currency: str = "DKK",
) -> List[Dict[str, Any]]:
    """
    Convert the flat response coming from Supabase into the shape expected
    by the client. All heavy grouping has already been done in SQL.
    """
    products: List[Dict[str, Any]] = []

    # order by similarity
    raw_products.sort(
        key=lambda p: product_conf.get(p["id"], 0),
        reverse=True,
    )

    for i, p in enumerate(raw_products):
        imgs = sorted(p.get("product_images") or [], key=lambda i: i.get("sort", 0))
        img_urls = [
            f"https://trendbook.s3.eu-west-1.amazonaws.com/{img['s3_key']}"
            for img in imgs
            if img.get("s3_key")
        ]

        # ---------- listings ----------
        listings = p.get("v_product_listings", [])
        feed_listings: Dict[str, Dict[str, Any]] = {}

        # Track the cheapest *in-stock* price while we build the feeds
        cheapest_price: float | None = None

        for lst in listings:
            if not lst.get("in_stock") or lst.get("price") is None:
                # skip out-of-stock or price-less variants everywhere
                continue

            feed_name = lst["feeds"]["name"]

            converted_price = round(
                convertCurrency(lst["price"], lst["currency"], currency), 2
            )

            # update cheapest price once, not twice
            if cheapest_price is None or converted_price < cheapest_price:
                cheapest_price = converted_price

            if feed_name not in feed_listings:
                feed_listings[feed_name] = {
                    **lst["feeds"],
                    "price_original": converted_price,  # for display
                    "price": converted_price,  # effective selling price
                    "compare_price": (
                        round(
                            convertCurrency(
                                lst["compare_price"], lst["currency"], currency
                            ),
                            2,
                        )
                        if lst["compare_price"] is not None
                        else None
                    ),
                    "original_currency": lst["currency"],
                    "currency": currency,
                    "link": lst["affiliate_url"],
                    "sizes": [],
                }

            # add the size only if we actually have one
            size = lst.get("variant", {}).get("size")
            if size:
                feed_listings[feed_name]["sizes"].append(size)

        products.append(
            {
                "id": p["id"],
                "brand": p["brand"],
                "from_price": cheapest_price,  # now only in-stock / converted once
                "currency": currency,
                "listings": list(feed_listings.values()),
                "images": img_urls,
                "confidence": round(product_conf.get(p["id"], 0), 10),
                "index": i,  # Added index property
            }
        )

    return products


search_detection_cache = TTLCache(maxsize=1000, ttl=300)  # 5 min expiry


def _cache_key(detection_id: str, gender: str) -> str:
    base = {"detection_id": detection_id, "gender": gender}
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()


@router.get("/search-detection")
def search_detection(
    detection_id: str,
    gender: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    cache_key = _cache_key(detection_id, gender)
    cached = search_detection_cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for detection_id={detection_id}, gender={gender}")

        return cached

    # 1) fetch detection
    det = (
        supabase.table("detections")
        .select("embedding, label")
        .eq("id", detection_id)
        .single()
        .execute()
    ).data or {}

    if not det:
        return {"products": []}

    # 2) vector search
    vectors = vectorSearch(vector=det["embedding"], label=det["label"], gender=gender)

    ranks = {}
    confidence = {}
    for i, v in enumerate(vectors):
        pid = v["product_id"]
        if pid not in ranks:
            ranks[pid] = i
            confidence[pid] = 1.0 / (1 + v["distance"])

    product_ids = list(ranks)

    # 3) product fetch
    prod = (
        (
            supabase.table("products")
            .select(
                """
                id, brand,
                product_images(url, s3_key, sort),
                v_product_listings:shop_listings!inner(*, variant(size), feeds(name, domain, bf_logo))
                """
            )
            .in_("id", product_ids)
            .execute()
        ).data
        or []
    )

    products = _group_products(prod, confidence)
    products = mark_liked_products(products, user.id)
    result = {"products": products}

    # Cache full result
    search_detection_cache[cache_key] = result

    return result
