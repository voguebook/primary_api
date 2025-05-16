import json
from typing import Optional

import numpy as np

from services.reranking import re_ranking
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


def vectorSearch(vector: list[float], label: str, gender: str) -> list[dict]:

    gender_match = ["unisex"]
    if gender is not None and gender != "all":
        gender_match.append(gender)

    print(gender_match)

    search_filter = Filter(
        must=[
            FieldCondition(key="label", match=MatchValue(value=label)),
            FieldCondition(
                key="generalized_gender",
                match=MatchAny(any=gender_match),
            ),
        ]
    )

    hits = qdrant.search(
        collection_name="tbnetv1_vectors",
        query_vector=vector,
        limit=200,  # More candidates = better re-ranking
        query_filter=search_filter,
        with_vectors=True,
        with_payload=True,
    )

    if not hits:
        return []

    gallery_vecs = np.array([h.vector for h in hits], dtype=np.float32)
    query_vec = np.asarray(vector, dtype=np.float32).reshape(1, -1)

    q_g = cosine_distances(query_vec, gallery_vecs)
    q_q = np.zeros((1, 1), dtype=np.float32)
    g_g = cosine_distances(gallery_vecs, gallery_vecs)

    ng = len(hits)
    k1_eff = min(20, ng - 1)
    k2_eff = min(6, k1_eff)

    reranked = re_ranking(q_g, q_q, g_g, k1=k1_eff, k2=k2_eff, lambda_value=0.3)
    order = np.argsort(reranked[0])

    results = []
    for i, idx in enumerate(order):
        h = hits[idx]
        results.append(
            {
                "rank": i + 1,
                "id": h.id,
                "product_id": h.payload.get("product_id"),
                "image_id": h.payload.get("image_id"),
                "distance": float(reranked[0, idx]),
                "ann_score": h.score,
            }
        )

    return results


def vectorSearchDepreciated(vector: list, label: str) -> list:
    """
    Perform a vector similarity search on the TBNetV1 column.
    """
    query = """
    SELECT image_id as id, product_id AS product_id,
        tbnetv1 <=> %s::vector AS distance
    FROM tb2.labeled_images
    WHERE tbnetv1 IS NOT NULL
    AND label = %s
    ORDER BY distance
    LIMIT 50;
    """

    # Ensure this is a list of floats

    print(label)
    results = postgresql.direct_query(query, params=[vector, label])
    return results
