import hashlib
import uuid
import psycopg2
from tqdm import tqdm
from qdrant_client import QdrantClient, models  # models = http.models

# --------------------------------------------------
# PostgreSQL
PG_CONN = {
    "host": "aws-0-eu-central-1.pooler.supabase.com",
    "port": 5432,
    "dbname": "postgres",
    "user": "postgres.lowqgmhuxbejwbapqkxs",
    "password": "lNqWq2CXGfuSRY8X",
}

VIEW_NAME = "tb2.labeled_images"

# Qdrant
COLLECTION_NAME = "tbnetv1_vectors"
qdrant = QdrantClient(
    host="54.228.147.115",  # or use url="https://..."
    port=6333,
    prefer_grpc=True,  # ← enables the gRPC channel
    timeout=300,  # raise if server stalls
    check_compatibility=False,
)

# --------------------------------------------------
conn = psycopg2.connect(**PG_CONN)
with conn, conn.cursor() as cur:
    cur.execute("SELECT COUNT(*) FROM " + VIEW_NAME)
    total = cur.fetchone()[0]

cur = conn.cursor(name="label_cursor")  # server-side streaming
cur.itersize = 10_000
cur.execute(
    f"""
    SELECT image_id, label, gender
    FROM {VIEW_NAME}
    WHERE label IS NOT NULL AND gender IS NOT NULL AND tbnetv1 IS NOT NULL
    """
)

BATCH = 5_000  # start with 5 k – tune if needed
ops = []  # SetPayloadOperation objects
pbar = tqdm(total=total, desc="Updating payloads", unit="pts")

for image_id, label, gender in cur:
    # If ids are already valid (uuid/str/int) there is no need to re-hash

    id_str = str(image_id)  # Already a valid UUID/ID used in Qdrant
    point_id = str(uuid.UUID(hashlib.md5(id_str.encode()).hexdigest()))

    ops.append(
        models.SetPayloadOperation(
            set_payload=models.SetPayload(
                payload={"label": label, "generalized_gender": gender},
                points=[point_id],  # one id per op
            )
        )
    )

    if len(ops) >= BATCH:
        qdrant.batch_update_points(  # ← single call
            collection_name=COLLECTION_NAME,
            update_operations=ops,
            wait=False,  # returns immediately; set True if you need ACK
        )
        pbar.update(len(ops))
        ops.clear()

# flush the tail
if ops:
    qdrant.batch_update_points(COLLECTION_NAME, ops, wait=False)
    pbar.update(len(ops))

pbar.close()
cur.close()
conn.close()
print("✅ Payload enrichment complete.")
