import json
import os
from typing import Optional

import numpy as np
from qdrant_client.http import models

from app.services.reranking import re_rank_result, re_ranking
from .cloud import postgresql

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    SearchRequest,
)
from sklearn.metrics.pairwise import cosine_distances

qdrant = QdrantClient(
    host="54.228.147.115",
    port=6333,
    grpc_port=6334,
    prefer_grpc=True,
    timeout=10,
)

qdrant_collection = os.getenv("QDRANT_COLLECTION", "tbnetv1_vectors")
gender_key = os.getenv("QDRANT_GENDER_KEY", "generalized_gender")
query_limit = int(os.getenv("QDRANT_QUERY_LIMIT", 150))


def vectorSearch(vector: list[float], label: str, gender: str) -> list[dict]:
    gender_match = ["unisex"]
    if gender is not None and gender != "all":
        gender_match.append(gender)

    search_filter = Filter(
        must=[
            FieldCondition(key="label", match=MatchValue(value=label)),
            FieldCondition(
                key=gender_key,
                match=MatchAny(any=gender_match),
            ),
        ]
    )

    hits = qdrant.search(
        collection_name=qdrant_collection,
        query_vector=vector,
        limit=query_limit,
        query_filter=search_filter,
        with_vectors=True,
        with_payload=True,
    )

    if not hits:
        return []
    reranked = re_rank_result(vector, hits)

    return reranked
