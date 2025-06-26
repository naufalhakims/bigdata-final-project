# File: spark/batch/process_models.py (Versi Final dengan Penyimpanan Aman)
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, split
from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pickle
import io
import os
from minio import Minio
BUCKET_NAME = "movies"

def get_spark_session():
    return SparkSession.builder \
        .appName("MovieRecommendationSingleNode") \
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

    movies_df = spark.read.csv("s3a://movies/final_movies_dataset.csv", header=True, inferSchema=True).limit(10000)
    movies_df.cache()
    print(f"Jumlah data yang akan diproses: {movies_df.count()} baris.")

    # Include 'theme' in the selected columns and fill NaNs
    movies_df = movies_df.select("id", "name", "description", "genre", "theme")
    movies_df = movies_df.na.fill("", subset=["description", "genre", "theme"])
    
    tokenizer = RegexTokenizer(inputCol="description", outputCol="words", pattern="\\W")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    movies_df = remover.transform(tokenizer.transform(movies_df))
    # Concatenate 'filtered_words', 'genre', AND 'theme'
    movies_df = movies_df.withColumn("tags", concat_ws(" ", movies_df["filtered_words"], movies_df["genre"], movies_df["theme"]))
    movies_df = movies_df.withColumn("tags", split(movies_df["tags"], " "))
    
    print("Membuat vektor fitur dengan CountVectorizer...")
    cv = CountVectorizer(inputCol="tags", outputCol="features", vocabSize=5000, minDF=2)
    vectorized_df = cv.fit(movies_df).transform(movies_df)

    print("Mengumpulkan data ke Driver dengan toPandas()...")
    pandas_df = vectorized_df.select("id", "name", "features").toPandas()
    print("Data berhasil dikonversi ke Pandas DataFrame.")

    n_rows = len(pandas_df)
    print(f"Menghitung matriks kemiripan {n_rows}x{n_rows}...")
    features_array = np.array([vec.toArray() for vec in pandas_df['features']])
    cosine_sim = cosine_similarity(features_array)
    print("Perhitungan matriks kemiripan selesai.")
    
    minio_client = Minio("minio:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
    output_folder = "ml_results/sklearn_model/"
    temp_dir = "/tmp" 

    try:
        # Simpan movies_df.pkl
        df_path = os.path.join(temp_dir, "movies_df.pkl")
        pandas_df.to_pickle(df_path)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}movies_df.pkl", df_path)
        os.remove(df_path) 
        print(f"✅ Berhasil menyimpan 'movies_df.pkl' ke MinIO.")
        
        # Simpan similarity_matrix.pkl
        sim_path = os.path.join(temp_dir, "similarity_matrix.pkl")
        with open(sim_path, 'wb') as f:
            pickle.dump(cosine_sim, f)
        minio_client.fput_object(BUCKET_NAME, f"{output_folder}similarity_matrix.pkl", sim_path)
        os.remove(sim_path) # Hapus file sementara
        print(f"✅ Berhasil menyimpan 'similarity_matrix.pkl' ke MinIO.")

    except Exception as e:
        print(f"❌ Gagal saat menyimpan hasil ke MinIO. Error: {e}")

    spark.stop()
    print("✅ Proses training dengan scikit-learn selesai.")

if __name__ == "__main__":
    main()