# bigdata-final-project

Pastikan Anda sudah melakukan persiapan berikut:
* Docker Desktop sudah terinstal dan sedang berjalan.
* Semua file dan folder proyek (`docker-compose.yml`, folder `data`, `ingestion`, `spark`, `streamlit`) sudah Anda buat dan isi sesuai panduan sebelumnya.
* File `final_movies_dataset.csv` dan folder `posters/` sudah Anda letakkan di dalam folder `data/`.

Buka aplikasi terminal Anda (seperti Command Prompt, PowerShell, atau Terminal di MacOS/Linux).

---

### Langkah 1: Menjalankan Semua Layanan dengan Docker

Langkah ini akan menghidupkan semua infrastruktur kita: MinIO, Kafka, Zookeeper, Spark, dan Streamlit.

1.  **Navigasi ke Folder Proyek:**
    Buka terminal dan arahkan ke direktori root proyek Anda.
    ```bash
    cd path/to/your/movie-streaming-project
    ```

2.  **Jalankan Docker Compose:**
    Ketik perintah berikut dan tekan Enter. Perintah ini akan membangun (jika perlu) dan menjalankan semua container di latar belakang (`-d`).
    ```bash
    docker-compose up -d
    ```

3.  **Verifikasi Layanan:**
    Tunggu sekitar 1-2 menit agar semua layanan stabil. Lalu, cek statusnya dengan perintah:
    ```bash
    docker-compose ps
    ```
    Anda akan melihat daftar semua container (`minio`, `kafka`, `spark-master`, dll.) dengan status `Up` atau `running`.

    * **Opsional:** Anda juga bisa membuka UI layanan di browser untuk memastikan:
        * **MinIO Console:** `http://localhost:9001` (Login: `minioadmin` / `minioadmin`)
        * **Spark Master UI:** `http://localhost:8080`

---

### Langkah 2: Ingesti (Upload) Data Awal ke MinIO

Langkah ini memindahkan dataset lokal Anda ke dalam sistem MinIO yang berjalan di Docker.

1.  **Navigasi ke Folder Ingestion:**
    Di terminal yang sama, masuk ke dalam folder `ingestion`.
    ```bash
    cd ingestion
    ```

2.  **Jalankan Script Upload:**
    Jalankan script Python untuk memulai proses upload.
    ```bash
    python upload_to_minio.py
    ```

3.  **Verifikasi Upload:**
    Setelah script selesai, buka MinIO Console di `http://localhost:9001`. Anda akan melihat sebuah *bucket* baru bernama `movies`. Klik bucket tersebut, dan Anda akan menemukan file `final_movies_dataset.csv` dan folder `posters/` di dalamnya.

---

### Langkah 3: Menjalankan Proses Batch Spark (Training Model)

Langkah ini akan memproses data di MinIO untuk membuat model rekomendasi dan klasifikasi.

1.  **Kembali ke Folder Root:**
    Di terminal, kembali ke direktori root proyek.
    ```bash
    cd ..
    ```

2.  **Jalankan Spark Job:**
    Salin dan tempel seluruh perintah panjang di bawah ini ke terminal Anda, lalu tekan Enter. Ini akan mengeksekusi script `process_models.py` di dalam container Spark.
    ```bash
    docker exec spark-master spark-submit --master spark://spark-master:7077 --packages org.apache.hadoop:hadoop-aws:3.3.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 /opt/bitnami/spark/app/batch/process_models.py
    ```
    *Proses ini mungkin memakan waktu beberapa menit tergantung spesifikasi komputer Anda.*

3.  **Verifikasi Hasil:**
    Setelah terminal selesai menjalankan perintah (kembali ke prompt biasa), cek lagi MinIO Console. Di dalam bucket `movies`, sekarang seharusnya ada folder baru bernama `ml_results/` yang berisi output dari Spark.

---

### Langkah 4: Menjalankan Pipeline Micro-Batch (Membutuhkan 2 Terminal)

Ini adalah langkah untuk mensimulasikan aliran data. Anda perlu membuka **dua jendela terminal** yang berbeda.

#### Di Terminal 1: Jalankan Consumer Spark

1.  **Pastikan Anda di Folder Root:** Pastikan terminal ini berada di direktori root proyek Anda.
2.  **Jalankan Spark Consumer:**
    Jalankan perintah ini untuk membuat Spark siaga mendengarkan data dari Kafka.
    ```bash
    docker exec spark-master spark-submit --master spark://spark-master:7077 --packages org.apache.hadoop:hadoop-aws:3.3.4,org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.0 /opt/bitnami/spark/app/stream/consumer.py
    ```
    Terminal ini akan menampilkan log Spark dan kemudian akan terlihat "diam" sambil menunggu pesan. Biarkan terminal ini tetap terbuka.

#### Di Terminal 2: Jalankan Producer Micro-Batch

1.  **Navigasi ke Folder Stream:** Buka jendela terminal **BARU**, dan arahkan ke folder `spark/stream/`.
    ```bash
    cd path/to/your/movie-streaming-project/spark/stream
    ```
2.  **Jalankan Python Producer:**
    Jalankan script ini untuk mulai mengirim data dari CSV ke Kafka dalam bentuk batch.
    ```bash
    python producer.py
    ```
    Terminal ini akan menampilkan log setiap kali satu batch data berhasil dikirim, dan akan **otomatis berhenti** ketika semua data di CSV selesai diproses.

3.  **Amati Interaksinya:**
    Saat Producer di Terminal 2 berjalan, lihatlah ke Terminal 1. Anda akan melihat log dari Consumer Spark bermunculan, menandakan ia sedang menerima dan memproses data yang dikirim oleh Producer.

---

### Langkah 5: Mengakses Aplikasi Web Streamlit

Ini adalah langkah terakhir untuk melihat hasil akhir dari proyek Anda.

1.  **Buka Web Browser:** Buka browser favorit Anda (Chrome, Firefox, dll).
2.  **Kunjungi Alamat:** Masukkan URL berikut di address bar:
    ```
    http://localhost:8501
    ```
3.  **Nikmati Hasilnya:** Anda akan melihat aplikasi web interaktif yang sudah Anda buat. Anda bisa menavigasi antar halaman melalui sidebar untuk melihat `Dashboard`, `Movie Like This`, dan `Rekomendasi per Usia`.

---

### Langkah Opsional: Menghentikan Semua Layanan

Jika Anda sudah selesai bekerja, Anda bisa mematikan semua container dengan rapi.

1.  **Kembali ke Folder Root:** Di salah satu terminal Anda, pastikan Anda berada di direktori root proyek.
2.  **Jalankan Docker Compose Down:**
    ```bash
    docker-compose down
    ```
    Perintah ini akan menghentikan dan menghapus semua container yang dibuat oleh `docker-compose up`.
