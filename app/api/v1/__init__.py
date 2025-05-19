# api/v1/__init__.py
from fastapi import APIRouter, Depends

from .manage import router as manage_router
from .search import router as search_router
from .similar import router as similar_router
from .like import router as like_router


router = APIRouter()
router.include_router(search_router, prefix="")
router.include_router(manage_router, prefix="")
router.include_router(like_router, prefix="")
router.include_router(similar_router, prefix="")
