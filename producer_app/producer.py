from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import json
import time
import pandas as pd

def json_serializer(data):
    return json.dumps(data, default=str).encode('utf-8')

# Logika koneksi yang tangguh
producer = None
print("Mencoba terhubung ke Kafka di kafka:29092...")
while producer is None:
    try:
        producer = KafkaProducer(
            bootstrap_servers=['kafka:29092'],
            value_serializer=json_serializer,
            api_version_auto_timeout_ms=10000
        )
        print("✅ Berhasil terhubung ke Kafka.")
    except NoBrokersAvailable:
        print("Kafka belum siap, mencoba lagi dalam 5 detik...")
        time.sleep(5)

# Baca dataset
try:
    df = pd.read_csv('final_movies_dataset.csv')
    print(f"Berhasil memuat {len(df)} baris dari CSV.")

    # Kirim setiap baris sebagai pesan
    for index, row in df.iterrows():
        message = row.to_dict()
        producer.send('movie_views', message)
        print(f"Sent: {message.get('name', 'N/A')}")
        time.sleep(0.5) # Jeda untuk mensimulasikan aliran data

except FileNotFoundError:
    print("❌ FATAL: file final_movies_dataset.csv tidak ditemukan di dalam kontainer.")
except Exception as e:
    print(f"❌ Terjadi error: {e}")
finally:
    if producer:
        producer.close()
    print("Producer berhenti.")