import hashlib
import json
import os
from typing import Any, Dict, List, Optional


from cachetools import TTLCache

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import User, get_current_user
from app.services.product_search import vectorSearch

from app.services.cloud import supabase

from currency_converter import CurrencyConverter
import logging

convertCurrency = CurrencyConverter().convert

logger = logging.getLogger(__name__)


def process_products(
    raw_products: List[Dict[str, Any]],
    product_conf: Optional[Dict[str, float]] = None,
    currency: str = "DKK",
) -> List[Dict[str, Any]]:
    """
    Convert the flat response coming from Supabase into the shape expected
    by the client. All heavy grouping has already been done in SQL.
    """
    products: List[Dict[str, Any]] = []

    db_prefix = os.getenv("DB_PREFIX", "")

    # order by similarity
    if product_conf:
        raw_products.sort(
            key=lambda p: product_conf.get(p["id"], 0),
            reverse=True,
        )

    for i, p in enumerate(raw_products):
        imgs = sorted(
            p.get(f"{db_prefix}product_images") or [], key=lambda i: i.get("sort", 0)
        )
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
        has_in_stock_listing = (
            False  # Flag to track if product has any in-stock listings
        )

        for lst in listings:
            if not lst.get("in_stock") or lst.get("price") is None:
                # skip out-of-stock or price-less variants everywhere
                continue

            has_in_stock_listing = (
                True  # Set flag when we find at least one in-stock listing
            )
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
                    "id": lst["id"],
                    "shop_id": lst["feeds"]["id"],
                    "price_original": converted_price,
                    "price": converted_price,
                    "compare_price": (
                        round(
                            convertCurrency(
                                lst["compare_price"],
                                lst["currency"],
                                currency,
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

        # Skip adding this product if it has no in-stock listings
        if not has_in_stock_listing:
            continue

        conf = None
        if product_conf:
            conf = round(product_conf.get(p["id"], 0), 10)

        products.append(
            {
                "id": p["id"],
                "brand": p["brand"],
                "from_price": cheapest_price,  # now only in-stock / converted once
                "currency": currency,
                "listings": list(feed_listings.values()),
                "images": img_urls,
                "confidence": conf,
                "index": i,  # Added index property
            }
        )

    return products
