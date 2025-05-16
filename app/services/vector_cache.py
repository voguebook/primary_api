import logging
from typing import List, Optional
from cachetools import LRUCache
import hashlib
import json

# Cache up to 100 queries per session (adjust as needed)
vector_cache = LRUCache(maxsize=100)


def vector_key(
    vector: list[float], label: str, gender: Optional[List[str]], detection_id: str
) -> str:
    """Create a unique cache key from search inputs including detection context."""
    base = {
        "vector": [round(v, 5) for v in vector],
        "label": label,
        "gender": gender or [],
        "detection_id": detection_id,
    }
    return hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()


def get_cached_result(key: str) -> Optional[list[dict]]:
    return vector_cache.get(key)


def cache_result(key: str, results: list[dict]) -> None:
    vector_cache[key] = results


# Configure logging
logger = logging.getLogger(__name__)
