# File: ingestion/set_minio_policy.py (Versi Final dengan Path Absolut)
import json
from minio import Minio
from minio.error import S3Error

MINIO_API_HOST = "minio:9000" # Alamat internal Docker
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "movies"

try:
    client = Minio(
        MINIO_API_HOST,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
except Exception as e:
    print(f"❌ Gagal terhubung ke MinIO: {e}")
    exit(1)

policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{BUCKET_NAME}/*"],
        }
    ],
}

def set_and_verify_policy():
    try:
        if not client.bucket_exists(BUCKET_NAME):
            print(f"❌ Bucket '{BUCKET_NAME}' tidak ditemukan.")
            return

        client.set_bucket_policy(BUCKET_NAME, json.dumps(policy))
        print(f"✅ Kebijakan untuk bucket '{BUCKET_NAME}' berhasil diatur menjadi publik.")
    except S3Error as exc:
        print(f"❌ Terjadi error saat mengatur kebijakan: {exc}")

if __name__ == "__main__":
    set_and_verify_policy()