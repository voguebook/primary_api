# import time
# from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException

# from fastapi.responses import JSONResponse

# from app.dependencies import User, get_current_user
# from app.services.get_products import process_products
# from app.services.product_search import vectorSearch, vectorSearchSimilar
# from app.services.cloud import supabase


router = APIRouter()


# @router.get("/similar-products")
# def similar_products(
#     product_id: str,
#     label: str,
#     gender: Optional[str] = None,
#     user: User = Depends(get_current_user),
# ) -> Dict[str, Any]:
#     start_time = time.time()

#     product_ids = vectorSearchSimilar(product_id, label, gender=gender or user.gender)
#     prod = (
#         (
#             supabase.table("products")
#             .select(
#                 """
#                 id, brand,
#                 product_images(url, s3_key, sort),
#                 v_product_listings:shop_listings!inner(*, variant(size), feeds(id, name, domain, bf_logo))
#                 """
#             )
#             .in_("id", product_ids)
#             .execute()
#         ).data
#         or []
#     )

#     products = process_products(
#         raw_products=prod,
#         product_conf={},
#     )

#     query_time = time.time() - start_time
#     print(f"Time to get search data: {query_time:.4f} seconds")

#     return JSONResponse(products)
