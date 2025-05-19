import os
from dotenv import load_dotenv

from app.tbpy_cloud import supabaseClient, bucket, S3Bucket, PostgreSQL

load_dotenv()

AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = supabaseClient(url=SUPABASE_URL, key=SUPABASE_KEY)

postgresql = PostgreSQL(database_url=os.getenv("DATABASE_URL"))

bucket = S3Bucket(
    AWS_S3_BUCKET_NAME=AWS_S3_BUCKET_NAME,
    AWS_ACCESS_KEY=AWS_ACCESS_KEY,
    AWS_SECRET_KEY=AWS_SECRET_KEY,
    AWS_REGION=AWS_REGION,
)
