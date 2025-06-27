# File: spark/run_setup_and_batch.py
import time
import subprocess
import sys
from minio import Minio

def wait_for_minio(host, port, access_key, secret_key):
    """Menunggu hingga layanan MinIO siap menerima koneksi."""
    print(f"Menunggu MinIO di {host}:{port}...")
    while True:
        try:
            client = Minio(
                f"{host}:{port}", access_key=access_key, secret_key=secret_key, secure=False
            )
            client.bucket_exists("non-existent-bucket-for-testing")
            print("✅ MinIO sudah siap.")
            break
        except Exception:
            print("MinIO belum siap, mencoba lagi dalam 5 detik...")
            time.sleep(5)

def run_command(command, description):
    """Menjalankan perintah dan mencetak outputnya, terutama saat error."""
    print(f"\n--- Menjalankan: {description} ---")
    process = subprocess.run(command, capture_output=True, text=True, shell=False)
    
    if process.stdout:
        print(process.stdout)

    if process.returncode != 0:
        print(f"❌ GAGAL: {description} (Exit code: {process.returncode})")
        print("--- Pesan Error (stderr) ---")
        print(process.stderr)
        print("--------------------------")
        raise subprocess.CalledProcessError(process.returncode, command, output=process.stdout, stderr=process.stderr)
    else:
        print(f"✅ Selesai: {description}")

def main():
    try:
        wait_for_minio("minio", 9000, "minioadmin", "minioadmin")
        
        run_command(["python", "/ingestion/upload_to_minio.py"], "Upload data ke MinIO")
        run_command(["python", "/ingestion/set_minio_policy.py"], "Set kebijakan bucket MinIO")
        
        # Perintah Spark dengan tuning timeout untuk stabilitas
        spark_command = [
            "spark-submit",
            "--master", "spark://spark-master:7077",
            "--packages", "org.apache.hadoop:hadoop-aws:3.3.4",
            "--conf", "spark.network.timeout=300s", # Menambah timeout jaringan
            "/opt/bitnami/spark/app/batch/process_models.py"
        ]
        run_command(spark_command, "Spark Batch Job (Recommendation Model)")

        print("\n🎉 Semua proses setup dan batch job telah selesai dengan sukses!")

    except subprocess.CalledProcessError:
        print("\n🔥 Terjadi kegagalan pada salah satu langkah. Proses dihentikan.")
        sys.exit(1)
    except Exception as e:
        print(f"\n🔥 Terjadi error tak terduga: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()