import json
from minio import Minio
from minio.error import S3Error

# --- Konfigurasi ---
# Sesuaikan jika Anda menggunakan konfigurasi yang berbeda
MINIO_API_HOST = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "movies"

# --- Inisialisasi Klien MinIO ---
try:
    client = Minio(
        MINIO_API_HOST,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )
    print("✅ Berhasil terhubung ke MinIO.")
except Exception as e:
    print(f"❌ Gagal terhubung ke MinIO: {e}")
    exit()

# --- Kebijakan Akses Publik (Public Read-Only) ---
# Kebijakan ini mengizinkan siapa saja untuk MEMBACA (GetObject)
# semua objek di dalam bucket yang ditentukan.
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

# --- Terapkan dan Verifikasi Kebijakan ---
def set_and_verify_policy():
    try:
        # Cek dulu apakah bucket ada
        if not client.bucket_exists(BUCKET_NAME):
            print(f"❌ Bucket '{BUCKET_NAME}' tidak ditemukan. Jalankan script upload terlebih dahulu.")
            return

        # Terapkan kebijakan baru ke bucket
        client.set_bucket_policy(BUCKET_NAME, json.dumps(policy))
        print(f"✅ Kebijakan untuk bucket '{BUCKET_NAME}' berhasil diatur menjadi publik.")

        # Verifikasi dengan mengambil kembali kebijakan yang sudah diatur
        print("\n--- Verifikasi Kebijakan yang Sekarang Aktif ---")
        retrieved_policy = client.get_bucket_policy(BUCKET_NAME)
        print(json.dumps(json.loads(retrieved_policy), indent=4))
        print("---------------------------------------------")

    except S3Error as exc:
        print(f"❌ Terjadi error saat mengatur kebijakan: {exc}")

if __name__ == "__main__":
    set_and_verify_policy()