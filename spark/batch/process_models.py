# File: spark/batch/process_models.py (Versi Final - Membaca Batch CSV)
import pandas as pd
import numpy as np
import pickle
import io
import os
from minio import Minio
from sklearn.metrics.pairwise import cosine_similarity

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, split
from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover
# Impor tipe data yang dibutuhkan untuk mendefinisikan skema
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType

# Mendefinisikan nama bucket sebagai konstanta global
BUCKET_NAME = "movies"

def get_spark_session():
    """Membangun dan mengembalikan Spark Session dengan konfigurasi MinIO."""
    return SparkSession.builder \
        .appName("TrainFromCsvBatches") \
        .config("spark.driver.memory", "4g") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.path.style.access", True) \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def main():
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # --- PERUBAHAN UTAMA: BACA BATCH CSV DENGAN SKEMA EKSPLISIT ---
    input_path = f"s3a://{BUCKET_NAME}/streamed_data/*.csv"
    print(f"Membaca data batch dari MinIO: {input_path}")
    
    try:
        # Definisikan skema secara manual agar tidak ada kesalahan tebak tipe data.
        # Ini harus cocok dengan kolom di file CSV yang Anda simpan dari Streamlit.
        schema = StructType([
            StructField("id", StringType(), True),
            StructField("name", StringType(), True),
            StructField("date", StringType(), True),
            StructField("tagline", StringType(), True),
            StructField("description", StringType(), True),
            StructField("minute", StringType(), True),
            StructField("rating", StringType(), True),
            StructField("genre", StringType(), True),
            StructField("studio", StringType(), True),
            StructField("theme", StringType(), True),
            StructField("country", StringType(), True),
            StructField("actors", StringType(), True),
            StructField("poster_filename", StringType(), True)
        ])

        # Baca semua file CSV di dalam folder dengan skema yang sudah pasti
        movies_df = spark.read.csv(input_path, header=True, schema=schema)
        
        # Konversi kolom yang seharusnya angka
        movies_df = movies_df.withColumn("id", col("id").cast(LongType())) \
                             .withColumn("rating", col("rating").cast(DoubleType()))

        if movies_df.rdd.isEmpty():
            print("Tidak ada data batch untuk diproses. Training dilewati kali ini.")
            spark.stop()
            return
            
    except Exception as e:
        print(f"Gagal membaca data batch atau folder kosong. Training dilewati. Error: {e}")
        spark.stop()
        return

    movies_df.cache()
    print(f"Jumlah data yang akan diproses untuk retraining: {movies_df.count()} baris.")

    # --- SISA PROSES TETAP SAMA SEPERTI SEBELUMNYA ---
    movies_df = movies_df.select("id", "name", "description", "genre", "theme").na.fill("", subset=["description", "genre", "theme"])
    tokenizer = RegexTokenizer(inputCol="description", outputCol="words", pattern="\\W")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    tokenized_df = remover.transform(tokenizer.transform(movies_df))
    tags_df = tokenized_df.withColumn("tags", concat_ws(" ", col("filtered_words"), col("genre"), col("theme"))).withColumn("tags", split(col("tags"), " "))
    
    cv = CountVectorizer(inputCol="tags", outputCol="features", vocabSize=5000, minDF=2)
    vectorized_df = cv.fit(tags_df).transform(tags_df)
    
    pandas_df = vectorized_df.select("id", "name", "features").toPandas()
    n_rows = len(pandas_df); print(f"Menghitung matriks kemiripan {n_rows}x{n_rows}...")
    features_array = np.array([vec.toArray() for vec in pandas_df['features']])
    cosine_sim = cosine_similarity(features_array).astype(np.float32); print("Perhitungan matriks selesai.")
    
    minio_client = Minio("minio:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
    output_folder = "ml_results/sklearn_model/"; temp_dir = "/tmp"
    try:
        df_path = os.path.join(temp_dir, "movies_df.pkl"); pandas_df.to_pickle(df_path)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}movies_df.pkl", df_path); os.remove(df_path)
        print(f"✅ Berhasil menyimpan 'movies_df.pkl'")
        sim_path = os.path.join(temp_dir, "similarity_matrix.npy"); np.save(sim_path, cosine_sim)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}similarity_matrix.npy", sim_path); os.remove(sim_path)
        print(f"✅ Berhasil menyimpan 'similarity_matrix.npy'")
    except Exception as e: print(f"❌ Gagal saat menyimpan hasil: {e}")
    spark.stop(); print("✅ Proses retraining dari data batch selesai.")

if __name__ == "__main__":
    main()