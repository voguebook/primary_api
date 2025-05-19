import numpy as np

from sklearn.metrics.pairwise import cosine_distances


# def re_ranking(q_g_dist, q_q_dist, g_g_dist, k1=20, k2=6, lambda_value=0.3):
#     query_num = q_g_dist.shape[0]
#     gallery_num = q_g_dist.shape[1]
#     all_num = query_num + gallery_num

#     original_dist = np.concatenate(
#         [
#             np.concatenate([q_q_dist, q_g_dist], axis=1),
#             np.concatenate([q_g_dist.T, g_g_dist], axis=1),
#         ],
#         axis=0,
#     ).astype(np.float32)

#     # Normalize per column and transpose
#     original_dist /= np.max(original_dist, axis=0, keepdims=True)
#     original_dist = original_dist.T

#     V = np.zeros_like(original_dist, dtype=np.float32)
#     initial_rank = np.argsort(original_dist, axis=1)

#     for i in range(all_num):
#         forward_k = initial_rank[i, : k1 + 1]
#         backward_k = initial_rank[forward_k, : k1 + 1]
#         fi = np.where(backward_k == i)[0]
#         k_reciprocal = forward_k[fi]
#         k_reciprocal_exp = k_reciprocal.copy()

#         for candidate in k_reciprocal:
#             c_forward = initial_rank[candidate, : int(np.round(k1 / 2)) + 1]
#             c_backward = initial_rank[c_forward, : int(np.round(k1 / 2)) + 1]
#             fi_candidate = np.where(c_backward == candidate)[0]
#             c_reciprocal = c_forward[fi_candidate]
#             if len(np.intersect1d(c_reciprocal, k_reciprocal)) > 2 / 3 * len(
#                 c_reciprocal
#             ):
#                 k_reciprocal_exp = np.append(k_reciprocal_exp, c_reciprocal)

#         k_reciprocal_exp = np.unique(k_reciprocal_exp)
#         weight = np.exp(-original_dist[i, k_reciprocal_exp])
#         V[i, k_reciprocal_exp] = weight / np.sum(weight)

#     if k2 != 1:
#         V_qe = np.zeros_like(V, dtype=np.float32)
#         for i in range(all_num):
#             V_qe[i, :] = np.mean(V[initial_rank[i, :k2], :], axis=0)
#         V = V_qe
#         del V_qe

#     invIndex = []
#     for i in range(query_num, all_num):  # Only gallery columns
#         invIndex.append(np.where(V[:, i] != 0)[0])

#     jaccard_dist = np.zeros((query_num, gallery_num), dtype=np.float32)
#     for i in range(query_num):
#         temp_min = np.zeros((1, gallery_num), dtype=np.float32)
#         non_zero = np.where(V[i, :] != 0)[0]
#         for j in non_zero:
#             if j < query_num:
#                 continue  # skip query columns
#             j_idx = j - query_num
#             temp_min[0, j_idx] += np.sum(np.minimum(V[i, j], V[invIndex[j_idx], j]))

#         jaccard_dist[i] = 1 - temp_min / (2 - temp_min)

#     final_dist = (1 - lambda_value) * jaccard_dist + lambda_value * original_dist[
#         :query_num, query_num:
#     ]
#     return final_dist


def re_rank_result(query_vector, hits):
    if not hits:
        return []

    gallery_vecs = np.array([h.vector for h in hits], dtype=np.float32)
    query_vec = np.asarray(query_vector, dtype=np.float32).reshape(1, -1)

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


def re_ranking(q_g_dist, q_q_dist, g_g_dist, k1=20, k2=6, lambda_value=0.3):
    query_num = q_g_dist.shape[0]
    gallery_num = q_g_dist.shape[1]
    all_num = query_num + gallery_num

    original_dist = np.concatenate(
        [
            np.concatenate([q_q_dist, q_g_dist], axis=1),
            np.concatenate([q_g_dist.T, g_g_dist], axis=1),
        ],
        axis=0,
    ).astype(np.float32)

    # Normalize per column and transpose
    original_dist /= np.max(original_dist, axis=0, keepdims=True)
    original_dist = original_dist.T

    V = np.zeros_like(original_dist, dtype=np.float32)
    initial_rank = np.argsort(original_dist, axis=1)

    for i in range(all_num):
        forward_k = initial_rank[i, : k1 + 1]
        backward_k = initial_rank[forward_k, : k1 + 1]
        fi = np.where(backward_k == i)[0]
        k_reciprocal = forward_k[fi]
        k_reciprocal_exp = k_reciprocal.copy()

        for candidate in k_reciprocal:
            c_forward = initial_rank[candidate, : int(np.round(k1 / 2)) + 1]
            c_backward = initial_rank[c_forward, : int(np.round(k1 / 2)) + 1]
            fi_candidate = np.where(c_backward == candidate)[0]
            c_reciprocal = c_forward[fi_candidate]
            if len(np.intersect1d(c_reciprocal, k_reciprocal)) > 2 / 3 * len(
                c_reciprocal
            ):
                k_reciprocal_exp = np.append(k_reciprocal_exp, c_reciprocal)

        k_reciprocal_exp = np.unique(k_reciprocal_exp)
        weight = np.exp(-original_dist[i, k_reciprocal_exp])
        V[i, k_reciprocal_exp] = weight / np.sum(weight)

    if k2 != 1:
        V_qe = np.zeros_like(V, dtype=np.float32)
        for i in range(all_num):
            V_qe[i, :] = np.mean(V[initial_rank[i, :k2], :], axis=0)
        V = V_qe
        del V_qe

    invIndex = []
    for i in range(query_num, all_num):  # Only gallery columns
        invIndex.append(np.where(V[:, i] != 0)[0])

    jaccard_dist = np.zeros((query_num, gallery_num), dtype=np.float32)
    for i in range(query_num):
        temp_min = np.zeros((1, gallery_num), dtype=np.float32)
        non_zero = np.where(V[i, :] != 0)[0]
        for j in non_zero:
            if j < query_num:
                continue  # skip query columns
            j_idx = j - query_num
            temp_min[0, j_idx] += np.sum(np.minimum(V[i, j], V[invIndex[j_idx], j]))

        jaccard_dist[i] = 1 - temp_min / (2 - temp_min)

    final_dist = (1 - lambda_value) * jaccard_dist + lambda_value * original_dist[
        :query_num, query_num:
    ]
    return final_dist
