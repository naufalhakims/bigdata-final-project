# File: spark/run_setup_and_batch.py (Versi Scheduler Berbasis Waktu)
import time
import subprocess
import sys
from minio import Minio

def wait_for_minio(host="minio", port=9000):
    """Menunggu hingga layanan MinIO siap menerima koneksi."""
    print(f"Menunggu MinIO di {host}:{port}...")
    client = Minio(f"{host}:{port}", access_key="minioadmin", secret_key="minioadmin", secure=False)
    while True:
        try:
            client.bucket_exists("non-existent-bucket")
            print("✅ MinIO sudah siap.")
            break
        except Exception:
            print("MinIO belum siap, mencoba lagi dalam 5 detik...")
            time.sleep(5)

def run_command(command, description, exit_on_failure=True):
    """Menjalankan perintah dan menangani kegagalan."""
    print(f"\n--- Menjalankan: {description} ---")
    try:
        # check=True akan otomatis melempar error jika return code bukan 0
        subprocess.run(command, check=True)
        print(f"✅ Selesai: {description}")
        return True # Mengembalikan status sukses
    except subprocess.CalledProcessError as e:
        print(f"❌ GAGAL: {description} (Exit code: {e.returncode})")
        if exit_on_failure:
            sys.exit(1) # Hentikan skrip jika tugas krusial gagal
        return False # Mengembalikan status gagal

def main():
    # --- TAHAP 1: SETUP SEKALI JALAN ---
    wait_for_minio()
    run_command(["python", "/ingestion/upload_to_minio.py"], "Upload data awal ke MinIO")
    run_command(["python", "/ingestion/set_minio_policy.py"], "Set kebijakan bucket MinIO")

    # --- TAHAP 2: LOOP TRAINING SETIAP 5 MENIT ---
    spark_command = [
        "spark-submit",
        "--master", "spark://spark-master:7077",
        "--packages", "org.apache.hadoop:hadoop-aws:3.3.4",
        "/opt/bitnami/spark/app/batch/process_models.py"
    ]
    
    TRAINING_INTERVAL_SECONDS = 300 # 300 detik = 5 menit

    print("\n🎉 Setup awal selesai. Memasuki loop retraining model...")
    
    while True:
        # Jalankan training job. Jangan hentikan seluruh skrip jika training gagal.
        run_command(spark_command, "Spark Batch Job (Retraining Model)", exit_on_failure=False)
        
        print(f"\nScheduler akan tidur selama {TRAINING_INTERVAL_SECONDS} detik hingga training berikutnya...")
        time.sleep(TRAINING_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
