import numpy as np

from sklearn.metrics.pairwise import cosine_distances


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

    return results


def re_ranking(q_g_dist, q_q_dist, g_g_dist, k1=20, k2=6, lambda_value=0.3):

    # The following naming, e.g. gallery_num, is different from outer scope.
    # Don't care about it.

    original_dist = np.concatenate(
        [
            np.concatenate([q_q_dist, q_g_dist], axis=1),
            np.concatenate([q_g_dist.T, g_g_dist], axis=1),
        ],
        axis=0,
    )
    original_dist = np.power(original_dist, 2).astype(np.float32)
    original_dist = np.transpose(1.0 * original_dist / np.max(original_dist, axis=0))
    V = np.zeros_like(original_dist).astype(np.float32)
    initial_rank = np.argsort(original_dist).astype(np.int32)

    query_num = q_g_dist.shape[0]
    gallery_num = q_g_dist.shape[0] + q_g_dist.shape[1]
    all_num = gallery_num

    for i in range(all_num):
        # k-reciprocal neighbors
        forward_k_neigh_index = initial_rank[i, : k1 + 1]
        backward_k_neigh_index = initial_rank[forward_k_neigh_index, : k1 + 1]
        fi = np.where(backward_k_neigh_index == i)[0]
        k_reciprocal_index = forward_k_neigh_index[fi]
        k_reciprocal_expansion_index = k_reciprocal_index
        for j in range(len(k_reciprocal_index)):
            candidate = k_reciprocal_index[j]
            candidate_forward_k_neigh_index = initial_rank[
                candidate, : int(np.around(k1 / 2.0)) + 1
            ]
            candidate_backward_k_neigh_index = initial_rank[
                candidate_forward_k_neigh_index, : int(np.around(k1 / 2.0)) + 1
            ]
            fi_candidate = np.where(candidate_backward_k_neigh_index == candidate)[0]
            candidate_k_reciprocal_index = candidate_forward_k_neigh_index[fi_candidate]
            if len(
                np.intersect1d(candidate_k_reciprocal_index, k_reciprocal_index)
            ) > 2.0 / 3 * len(candidate_k_reciprocal_index):
                k_reciprocal_expansion_index = np.append(
                    k_reciprocal_expansion_index, candidate_k_reciprocal_index
                )

        k_reciprocal_expansion_index = np.unique(k_reciprocal_expansion_index)
        weight = np.exp(-original_dist[i, k_reciprocal_expansion_index])
        V[i, k_reciprocal_expansion_index] = 1.0 * weight / np.sum(weight)
    original_dist = original_dist[:query_num,]
    if k2 != 1:
        V_qe = np.zeros_like(V, dtype=np.float32)
        for i in range(all_num):
            V_qe[i, :] = np.mean(V[initial_rank[i, :k2], :], axis=0)
        V = V_qe
        del V_qe
    del initial_rank
    invIndex = []
    for i in range(gallery_num):
        invIndex.append(np.where(V[:, i] != 0)[0])

    jaccard_dist = np.zeros_like(original_dist, dtype=np.float32)

    for i in range(query_num):
        temp_min = np.zeros(shape=[1, gallery_num], dtype=np.float32)
        indNonZero = np.where(V[i, :] != 0)[0]
        indImages = []
        indImages = [invIndex[ind] for ind in indNonZero]
        for j in range(len(indNonZero)):
            temp_min[0, indImages[j]] = temp_min[0, indImages[j]] + np.minimum(
                V[i, indNonZero[j]], V[indImages[j], indNonZero[j]]
            )
        jaccard_dist[i] = 1 - temp_min / (2.0 - temp_min)

    final_dist = jaccard_dist * (1 - lambda_value) + original_dist * lambda_value
    del original_dist
    del V
    del jaccard_dist
    final_dist = final_dist[:query_num, query_num:]
    return final_dist
