import hashlib
import json
from typing import Any, Dict, List
from currency_converter import CurrencyConverter
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import User, get_current_user
from app.services.get_products import process_products
from app.services.product_search import vectorSearch
from app.services.cloud import supabase

import logging


logger = logging.getLogger(__name__)

convertCurrency = CurrencyConverter().convert

router = APIRouter()


def mark_liked_products(products: List[Dict], user_id: str) -> List[Dict]:
    if not products or not user_id:
        return products

    product_ids = [p["id"] for p in products]

    liked_result = (
        supabase.table("liked_products")
        .select("product")
        .eq("user", user_id)
        .in_("product", product_ids)
        .execute()
    )

    liked_ids = {entry["product"] for entry in (liked_result.data or [])}
    print(liked_result)
    print(liked_ids)

    for product in products:
        product["liked"] = product["id"] in liked_ids
        if product["liked"]:
            print(product)

    return products


@router.get("/like-product")
async def like_product(
    product_id: str, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Like a product for the current user.
    """
    try:

        if not product_id:
            raise HTTPException(status_code=400, detail="Product ID is required")

        # Insert record if not already liked
        result = (
            supabase.table("liked_products")
            .insert({"user": current_user.id, "product": product_id})
            .execute()
        )

        if result.data:
            return {"success": True, "message": "Product liked successfully"}

    except Exception as e:
        logger.error(f"Error liking product: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to like product: {str(e)}")


@router.get("/unlike-product")
async def unlike_product(
    product_id: str, current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Unlike a previously liked product.
    """
    try:

        if not product_id:
            raise HTTPException(status_code=400, detail="Product ID is required")

        result = (
            supabase.table("liked_products")
            .delete()
            .eq("user", current_user.id)
            .eq("product", product_id)
            .execute()
        )

        return {"success": True, "message": "Product unliked successfully"}

    except Exception as e:
        logger.error(f"Error unliking product: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to unlike product: {str(e)}"
        )


@router.get("/get-liked-products")
async def get_liked_products(
    page: int = 1,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Get the current user's liked products with pagination support.
    Returns products in the same format as the search API.

    Args:
        page: Page number (starts at 1)
        limit: Number of items per page
        current_user: Current authenticated user

    Returns:
        Dictionary containing paginated liked products and pagination metadata
    """
    try:
        # Calculate pagination values
        if page < 1:
            page = 1
        if limit < 1:
            limit = 10

        offset = (page - 1) * limit

        # Get total count of user's liked products
        count_result = (
            supabase.table("liked_products")
            .select("*", count="exact")
            .eq("user", current_user.id)
            .execute()
        )

        total_count = count_result.count or 0

        # Get paginated liked products with full product data including images and listings
        join_query = (
            supabase.table("liked_products")
            .select(
                """
                product,
                products!inner(
                    id, brand,
                    product_images(url, s3_key, sort),
                    v_product_listings:shop_listings!inner(*, variant(size), feeds(id, name, domain, bf_logo))
                )
                """
            )
            .eq("user", current_user.id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        # Extract the 'products' data from each item before processing
        product_data = []
        if join_query.data:
            for item in join_query.data:
                if item.get("products"):
                    product_data.append(item["products"])

        # Format products in the same way as search API
        liked_products = process_products(
            product_data,
            currency=current_user.currency,
        )

        # Mark all products as liked
        for product in liked_products:
            product["liked"] = True

        # Calculate total pages
        total_pages = (total_count + limit - 1) // limit if total_count > 0 else 0

        return {
            "success": True,
            "products": liked_products,
            "pagination": {
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
            },
        }

    except Exception as e:
        logger.error(f"Error retrieving liked products: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve liked products: {str(e)}"
        )
