import pandas as pd
from kafka import KafkaProducer
import json
import time

KAFKA_TOPIC = "movie_views"
KAFKA_SERVER = "localhost:9092"
CSV_FILE_PATH = "../../data/final_movies_dataset.csv"
CHUNK_SIZE = 100  # Jumlah baris yang akan dibaca per batch

# Inisialisasi Producer
try:
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_SERVER,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    print("Berhasil terhubung ke Kafka.")
except Exception as e:
    print(f"Gagal terhubung ke Kafka: {e}")
    exit()

# Membaca file CSV dalam bentuk iterator dengan chunksize
print(f"Mulai membaca {CSV_FILE_PATH} dalam batch berisi {CHUNK_SIZE} baris...")
csv_iterator = pd.read_csv(CSV_FILE_PATH, chunksize=CHUNK_SIZE)

# Loop untuk setiap batch (chunk) di dalam file CSV
batch_num = 1
for chunk_df in csv_iterator:
    # Mengubah setiap baris di dalam chunk menjadi dictionary
    messages = chunk_df.to_dict(orient="records")
    
    # Mengirim setiap baris sebagai pesan terpisah ke Kafka
    for message in messages:
        producer.send(KAFKA_TOPIC, message)
    
    # Pastikan semua pesan dalam batch ini terkirim
    producer.flush()
    
    print(f"Batch #{batch_num}: Mengirim {len(chunk_df)} data film ke Kafka.")
    
    # Jeda untuk mensimulasikan waktu antar batch
    time.sleep(5) 
    batch_num += 1

# Tutup koneksi producer setelah semua data terkirim
producer.close()
print("\nSemua data dari file CSV telah berhasil dikirim ke Kafka. Producer berhenti.")