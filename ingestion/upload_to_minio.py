import os
from minio import Minio

# Konfigurasi MinIO
MINIO_CLIENT = Minio(
    "localhost:9000",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)

BUCKET_NAME = "movies"
CSV_FILE_PATH = "../data/final_movies_dataset.csv"
POSTERS_FOLDER_PATH = "../data/posters"

def main():
    # Buat bucket jika belum ada
    if not MINIO_CLIENT.bucket_exists(BUCKET_NAME):
        MINIO_CLIENT.make_bucket(BUCKET_NAME)
        print(f"Bucket '{BUCKET_NAME}' berhasil dibuat.")
    else:
        print(f"Bucket '{BUCKET_NAME}' sudah ada.")

    # Upload file CSV
    try:
        MINIO_CLIENT.fput_object(
            BUCKET_NAME, "final_movies_dataset.csv", CSV_FILE_PATH
        )
        print(f"File CSV '{CSV_FILE_PATH}' berhasil diupload.")
    except Exception as e:
        print(f"Error saat upload CSV: {e}")

    # Upload semua poster
    print("Mulai mengupload poster...")
    for filename in os.listdir(POSTERS_FOLDER_PATH):
        if filename.endswith(".jpg"):
            file_path = os.path.join(POSTERS_FOLDER_PATH, filename)
            object_name = f"posters/{filename}"
            try:
                MINIO_CLIENT.fput_object(BUCKET_NAME, object_name, file_path)
            except Exception as e:
                print(f"Error saat upload {filename}: {e}")
    print("Upload semua poster selesai.")

if __name__ == "__main__":
    main()