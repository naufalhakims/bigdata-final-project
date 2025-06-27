# 🎥 Sistem Rekomendasi Film - Implementasi Big Data

Sebuah sistem rekomendasi film yang komprehensif dengan arsitektur big data modern, menampilkan pemrosesan real-time, machine learning, dan visualisasi.

**Final Project - Big Data**  
**Kelompok 7**  
**Kelas Big Data B** 

| Nama                             | NRP        |
|----------------------------------|------------|
| Daffa Rajendra P                 | 5027231009 |
| Muhamad Arrayyan                 | 5027231014 |
| Naufal Syafi' Hakim              | 5027231022 |
| RM. Novian Malcolm Bayuputra     | 5027231035 |
| Dzaky Faiq Fayyadhi              | 5027231047 |

---

## 📖 Daftar Isi

1. [Identifikasi Masalah](#-identifikasi-masalah-nyata)
2. [Arsitektur dan Data Flow](#️-arsitektur-dan-data-flow)
3. [Struktur Proyek](#-struktur-proyek)
4. [Quick Start](#-quick-start)
5. [Detail Implementasi](#-detail-implementasi)
6. [Testing & Validasi](#-testing-dan-validasi)
7. [Deployment](#-deployment)
8. [Monitoring & Analytics](#-monitoring--analytics)
9. [Troubleshooting](#-troubleshooting)

---

## 🎯 Identifikasi Masalah Nyata

### _Industri_: Platform Streaming dan Hiburan Digital (Film)

### _Tantangan Bisnis_:

Platform streaming film menghadapi tantangan dalam memberikan rekomendasi film yang personal dan akurat kepada pengguna. Masalah utama yang dihadapi:

1. **📊 Volume Data Besar**: Dataset film dengan atribut kompleks seperti judul, genre, rating, dll.
2. **⚡ Real-time Processing**: Kebutuhan untuk memproses aktivitas pengguna secara real-time.
3. **🎯 Personalisasi**: Rekomendasi film berdasarkan preferensi pengguna.
4. **📈 Skalabilitas**: Sistem yang mampu menangani pertumbuhan data.
5. **🔍 Discovery**: Membantu pengguna menemukan film baru sesuai minat mereka.

### _Definisi Masalah_

**Jenis dan Volume Data**:

- **Dataset film** dari `final_movies_dataset.csv` dengan atribut seperti judul, genre, rating, dll.
- **Stream data real-time** untuk aktivitas pengguna.
- **Data tidak terstruktur** (gambar poster).
- **Data terstruktur** (judul, genre, rating).

**Teknologi dan Sistem**:

- **Apache Kafka** untuk streaming data real-time.
- **Apache Spark** untuk pemrosesan big data dan machine learning.
- **MinIO** sebagai penyimpanan objek (S3-compatible).
- **Docker** untuk containerization.
- **Streamlit** untuk dashboard visualisasi.

**Tantangan Teknis**:

1. **Data Ingestion**: Streaming data dari dataset secara efisien.
2. **Data Storage**: Penyimpanan batch data yang skalabel.
3. **ML Pipeline**: Training model rekomendasi yang akurat.
4. **Real-time Inference**: Deployment model untuk prediksi real-time.
5. **User Experience**: Interface yang responsif (meskipun belum ada frontend penuh).

---

## 🏗️ Arsitektur dan Data Flow

### **Arsitektur Sistem**
[Dataset: final_movies_dataset.csv]
↓
[Kafka Producer (producer_app/producer.py)]
↓
[Apache Kafka]
↙         ↘
[Streamlit]    [Apache Spark (batch & stream)]
↘         ↓
[ML Models (Collaborative Filtering, Content-based)]
↓
[MinIO Storage]


#### **Penjelasan Arsitektur**
1. **Dataset**: Data awal dari `final_movies_dataset.csv` di direktori `data/`.
2. **Kafka Producer**: Mengirimkan data ke Apache Kafka untuk streaming real-time (`producer_app/producer.py`).
3. **Apache Kafka**: Message broker yang mendistribusikan data ke komponen lain.
4. **Streamlit**: Dashboard untuk memantau data streaming real-time (`streamlit/app.py`).
5. **Apache Spark**: Memproses data batch (`spark/batch/process_models.py`) dan streaming (`spark/stream/consumer.py`) untuk membangun model ML.
6. **ML Models**: Model rekomendasi (misalnya Collaborative Filtering atau Content-based) dihasilkan dari pemrosesan Spark.
7. **MinIO Storage**: Menyimpan data batch atau hasil pemrosesan (`ingestion/` untuk upload).
---

### **Komponen Utama**

| Komponen                   | Deskripsi                                           | Port/URL  | Status |
|----------------------------|---------------------------------------------------- |-----------|--------|
| 📊 **Data Source**         | Dataset film dari `final_movies_dataset.csv`       | -         | ✅     |
| 🌊 **Kafka Producer**      | Streaming data secara real-time                    | 9092      | ✅     |
| 📡 **Apache Kafka**        | Message broker untuk data streaming                | 9092      | ✅     |
| 📱 **Streamlit Dashboard** | Visualisasi dan monitoring real-time               | 8501      | ✅     |
| 🗄 **MinIO**               | Penyimpanan objek untuk batch files                 | 9001      | ✅     |
| ⚡ **Apache Spark**        | Pemrosesan big data dan machine learning           | 8080      | ✅     |

---

## 📁 Struktur Proyek
```
bigdata-final-project/
├── 📄 .gitignore                     # File yang diabaikan oleh Git
├── 📄 docker-compose.yml             # Konfigurasi Docker Compose untuk seluruh services
├── 📄 Dockerfile                     # Dockerfile root (opsional/global build)
│
├── 📁 data/                          # Dataset dan file statis
│   ├── 📄 final_movies_dataset.csv   # Dataset utama film
│   ├── 📄 note.txt                   # Catatan atau dokumentasi data
│   ├── 📁 .minio.sys/                # Metadata internal MinIO
│   ├── 📁 movies/                    # Folder film (konten/data film)
│   └── 📁 posters/                   # Folder poster gambar film
│
├── 📁 ingestion/                     # Inisialisasi dan unggah ke MinIO
│   ├── 📄 set_minio_policy.py        # Mengatur kebijakan akses MinIO
│   └── 📄 upload_to_minio.py         # Script untuk upload file ke MinIO
│
├── 📁 producer_app/                  # Kafka producer untuk streaming
│   ├── 📄 Dockerfile                 # Dockerfile untuk Kafka producer
│   ├── 📄 producer.py                # Script utama Kafka producer
│   └── 📄 requirements.txt           # Dependencies Python producer
│
├── 📁 spark/                         # Aplikasi Spark untuk pemrosesan data
│   ├── 📁 batch/                     # Proses batch (model/ETL)
│   │   └── 📄 process_models.py      # Script untuk proses batch model
│   ├── 📁 stream/                    # Proses streaming (real-time)
│   │   ├── 📄 consumer.py            # Kafka consumer untuk streaming
│   │   ├── 📄 run_setup_and_batch.py # Setup awal dan jalankan pipeline batch
│   │   ├── 📄 Dockerfile             # Dockerfile untuk Spark streaming
│   │   └── 📄 requirements.txt       # Dependencies Spark streaming
│
├── 📁 streamlit/                     # Dashboard visualisasi Streamlit
│   ├── 📄 app.py                     # Aplikasi utama Streamlit
│   ├── 📄 Dockerfile                 # Dockerfile untuk Streamlit
│   └── 📄 requirements.txt           # Dependencies Streamlit
```

### **Penjelasan Detail Komponen**

- **📁 data/**: Berisi dataset utama (`final_movies_dataset.csv`) dan folder pendukung seperti `movies` dan `posters`.
- **📁 ingestion/**: Script untuk mengatur kebijakan MinIO dan mengunggah data.
- **📁 producer_app/**: Komponen Kafka producer untuk streaming data.
- **📁 spark/**: Aplikasi Spark untuk pemrosesan batch dan streaming.
- **📁 streamlit/**: Dashboard untuk visualisasi dan monitoring.

---

## 🚀 Quick Start

### **Prerequisites**

| Requirement        | Version | Cara Install                                      |
|--------------------|---------|--------------------------------------------------|
| **Docker**         | 20.0+   | [Download Docker](https://docker.com/get-started) |
| **Docker Compose** | 2.0+    | Included dengan Docker Desktop                    |
| **Python**         | 3.8+    | [Download Python](https://python.org/downloads)   |
| **RAM**            | 8GB+    | -                                                 |
| **Storage**        | 10GB+   | -                                                 |

### **🎬 Setup Manual**

1. **Clone Repository**:
   - Clone proyek dan navigasi ke direktori proyek.

2. **Setup Infrastructure dengan Docker**:
   - Pastikan Docker dan Docker Compose terinstal.
   - Jalankan: `docker-compose up --build`.

3. **Jalankan Producer**:
   - Navigasi ke `producer_app/` dan jalankan: `python producer.py`.

4. **Jalankan Spark Streaming**:
   - Navigasi ke `spark/stream/` dan jalankan: `python consumer.py`.

5. **Jalankan Dashboard**:
   - Navigasi ke `streamlit/` dan jalankan: `streamlit run app.py`.

### **🎯 Akses Aplikasi**

| Service                 | URL                   | Deskripsi                     |
|-------------------------|-----------------------|-------------------------------|
| **Streamlit Dashboard** | http://localhost:8501 | Monitoring dan visualisasi    |
| **MinIO Storage**       | http://localhost:9001 | Manajemen penyimpanan objek   |
| **Spark UI**            | http://localhost:8080 | Monitoring cluster Spark      |

---

## 📊 Detail Implementasi

### _1. Data Ingestion Layer (Kafka & MinIO)_
- **Kafka Producer** (`producer_app/producer.py`): Mengirimkan data dari `final_movies_dataset.csv` ke Kafka.
- **MinIO** (`ingestion/upload_to_minio.py`): Menyimpan data batch dari proses streaming.

### _2. Processing Layer (Spark)_
- **Batch** (`spark/batch/process_models.py`): Pemrosesan data batch untuk membangun model.
- **Streaming** (`spark/stream/consumer.py`): Pemrosesan data real-time.

### _3. Visualization Layer (Streamlit)_
- **app.py**: Menyediakan dashboard interaktif untuk memantau data.

---

## 🔧 Deployment

- Gunakan `docker-compose.yml` untuk mengatur dan menjalankan semua layanan.
- Pastikan port 9001 (MinIO), 9092 (Kafka), 8080 (Spark), dan 8501 (Streamlit) tersedia.

---

## 📈 Monitoring & Analytics

- **Streamlit Dashboard** (`streamlit/app.py`): Memantau data streaming dan batch processing secara real-time.
- **Spark UI**: Monitoring performa cluster di `http://localhost:8080`.

---

## 🧪 Testing dan Validasi

### **📋 Checklist Testing**
- **Infrastructure**: Verifikasi semua kontainer Docker berjalan (`docker ps`).
- **Data Pipeline**: Pastikan data streaming dan penyimpanan berfungsi.
- **Dashboard**: Uji akses dan visualisasi di `http://localhost:8501`.

---

## 🎉 Kesimpulan

Sistem rekomendasi film ini mengintegrasikan:

- **📊 Big Data Processing**: Apache Spark untuk pemrosesan data.
- **🌊 Real-time Streaming**: Apache Kafka untuk ingestion.
- **📈 Visualisasi**: Streamlit untuk monitoring.
- **🚀 Containerization**: Docker untuk skalabilitas.

**Tech Stack**:
- **Big Data**: Apache Spark, Kafka, MinIO
- **Visualization**: Streamlit
- **Infrastructure**: Docker

---

## 🔧 Troubleshooting

- **Docker Tidak Berjalan**: Pastikan Docker Desktop aktif dan port tidak digunakan oleh aplikasi lain.
- **Error Kafka**: Periksa konfigurasi di `docker-compose.yml` dan pastikan topic telah dibuat.
- **Streamlit Tidak Muncul**: Verifikasi port 8501 dan pastikan `requirements.txt` terinstal.

---- 
![Big Data](https://img.shields.io/badge/Big%20Data-Film-blue) ![Kafka](https://img.shields.io/badge/Apache%20Kafka-Streaming-orange) ![Spark](https://img.shields.io/badge/Apache%20Spark-ML-red) ![Docker](https://img.shields.io/badge/Docker-Containerized-blue) ![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-yellow)
