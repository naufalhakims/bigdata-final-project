import pandas as pd
import numpy as np
import pickle
import io
import os
from minio import Minio

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, split
from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover
from sklearn.metrics.pairwise import cosine_similarity

# Mendefinisikan nama bucket sebagai konstanta global
BUCKET_NAME = "movies"

def get_spark_session():
    """Membangun dan mengembalikan Spark Session dengan konfigurasi MinIO."""
    return SparkSession.builder \
        .appName("MovieRecommendationBatchTrainer") \
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

    # 1. BACA DATA AWAL DARI MINIO
    # Menggunakan limit(5000) untuk stabilitas di mesin dengan RAM terbatas.
    # Anda bisa menaikkan angka ini untuk eksperimen jika sumber daya mencukupi.
    input_path = f"s3a://{BUCKET_NAME}/final_movies_dataset.csv"
    print(f"Membaca data dari MinIO: {input_path}")
    movies_df = spark.read.csv(input_path, header=True, inferSchema=True).limit(5000)
    movies_df.cache()
    print(f"Jumlah data yang akan diproses: {movies_df.count()} baris.")

    # 2. FEATURE ENGINEERING DENGAN SPARK
    movies_df = movies_df.select("id", "name", "description", "genre", "theme")
    movies_df = movies_df.na.fill("", subset=["description", "genre", "theme"])
    
    tokenizer = RegexTokenizer(inputCol="description", outputCol="words", pattern="\\W")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    tokenized_df = remover.transform(tokenizer.transform(movies_df))
    
    tags_df = tokenized_df.withColumn("tags", concat_ws(" ", col("filtered_words"), col("genre"), col("theme"))) \
                          .withColumn("tags", split(col("tags"), " "))
    
    print("Membuat vektor fitur dengan CountVectorizer...")
    cv = CountVectorizer(inputCol="tags", outputCol="features", vocabSize=5000, minDF=2)
    vectorized_df = cv.fit(tags_df).transform(tags_df)

    # 3. KALKULASI MODEL DENGAN SKLEARN (SINGLE-NODE)
    print("PERINGATAN: Mengumpulkan data ke Driver dengan toPandas().")
    pandas_df = vectorized_df.select("id", "name", "features").toPandas()
    print("Data berhasil dikonversi ke Pandas DataFrame.")

    n_rows = len(pandas_df)
    print(f"Menghitung matriks kemiripan {n_rows}x{n_rows}...")
    features_array = np.array([vec.toArray() for vec in pandas_df['features']])
    # Ubah ke float32 untuk menghemat memori
    cosine_sim = cosine_similarity(features_array).astype(np.float32) 
    print("Perhitungan matriks kemiripan selesai.")
    
    # 4. SIMPAN HASIL MODEL KE MINIO (METODE AMAN UNTUK MEMORI)
    minio_client = Minio("minio:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
    output_folder = "ml_results/sklearn_model/"
    temp_dir = "/tmp" 

    try:
        # Simpan DataFrame info film (relatif kecil)
        df_path = os.path.join(temp_dir, "movies_df.pkl")
        pandas_df.to_pickle(df_path)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}movies_df.pkl", df_path)
        os.remove(df_path)
        print(f"✅ Berhasil menyimpan 'movies_df.pkl' ke MinIO.")
        
        # Simpan matriks kemiripan (besar) menggunakan format asli numpy
        sim_path = os.path.join(temp_dir, "similarity_matrix.npy")
        np.save(sim_path, cosine_sim)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}similarity_matrix.npy", sim_path)
        os.remove(sim_path)
        print(f"✅ Berhasil menyimpan 'similarity_matrix.npy' ke MinIO.")

    except Exception as e:
        print(f"❌ Gagal saat menyimpan hasil ke MinIO. Error: {e}")

    spark.stop()
    print("✅ Proses training batch dengan scikit-learn selesai.")

if __name__ == "__main__":
    main()