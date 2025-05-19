import hashlib
import json
from typing import Any, Dict
from cachetools import TTLCache
from fastapi import APIRouter, Depends
from app.dependencies import User, get_current_user
from app.services.get_products import process_products
from app.services.product_search import vectorSearch
from app.services.cloud import supabase
from currency_converter import CurrencyConverter
import logging

logger = logging.getLogger(__name__)
convertCurrency = CurrencyConverter().convert


router = APIRouter()


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
                v_product_listings:shop_listings!inner(*, variant(size), feeds(id, name, domain, bf_logo))
                """
            )
            .in_("id", product_ids)
            .execute()
        ).data
        or []
    )

    products = process_products(prod, confidence)

    result = {"products": products}

    # Cache full result
    search_detection_cache[cache_key] = result

    return result
