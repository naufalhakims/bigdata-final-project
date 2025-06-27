# File: ingestion/upload_to_minio.py (Versi Final dengan Path Absolut)
import os
from minio import Minio

# Konfigurasi MinIO
MINIO_CLIENT = Minio(
    "minio:9000",  # Alamat internal Docker
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

BUCKET_NAME = "movies"
# Path absolut di dalam kontainer (sesuai definisi 'volumes' di docker-compose)
CSV_FILE_PATH = "/data/final_movies_dataset.csv"
POSTERS_FOLDER_PATH = "/data/posters"

def main():
    try:
        if not MINIO_CLIENT.bucket_exists(BUCKET_NAME):
            MINIO_CLIENT.make_bucket(BUCKET_NAME)
            print(f"Bucket '{BUCKET_NAME}' berhasil dibuat.")
        else:
            print(f"Bucket '{BUCKET_NAME}' sudah ada.")

        try:
            MINIO_CLIENT.fput_object(
                BUCKET_NAME, "final_movies_dataset.csv", CSV_FILE_PATH
            )
            print(f"File CSV '{CSV_FILE_PATH}' berhasil diupload.")
        except Exception as e:
            print(f"Error saat upload CSV: {e}")

        print("Mulai mengupload poster...")
        try:
            for filename in os.listdir(POSTERS_FOLDER_PATH):
                if filename.endswith(".jpg"):
                    file_path = os.path.join(POSTERS_FOLDER_PATH, filename)
                    object_name = f"posters/{filename}"
                    MINIO_CLIENT.fput_object(BUCKET_NAME, object_name, file_path)
            print("Upload semua poster selesai.")
        except Exception as e:
            print(f"Error saat upload poster: {e}")
            
    except Exception as e:
        print(f"Terjadi error pada fungsi main: {e}")
        # Keluar dengan status error agar subprocess mendeteksinya
        exit(1)

if __name__ == "__main__":
    main()