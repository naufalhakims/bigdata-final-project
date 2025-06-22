from pyspark.sql import SparkSession, Window
from pyspark.ml.feature import HashingTF, IDF, Tokenizer, StopWordsRemover, BucketedRandomProjectionLSH
from pyspark.ml import Pipeline
from pyspark.sql.functions import col, concat_ws, when, split, expr
from pyspark.sql.types import LongType

def get_spark_session():
    """Membangun dan mengembalikan Spark Session dengan konfigurasi MinIO."""
    return SparkSession.builder \
        .appName("MovieRecommendationLSH") \
        .config("spark.driver.memory", "2g") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.path.style.access", True) \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def main():
    spark = get_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    print("Membaca data dari MinIO...")
    df_movies = spark.read.csv("s3a://movies/final_movies_dataset.csv", header=True, inferSchema=True).withColumn("id", col("id").cast(LongType()))
    print("Data CSV berhasil dibaca.")
    
    # --- MENGGUNAKAN SAMPEL 30% SESUAI PERMINTAAN ---
    print("Menggunakan sampel data (30%) untuk proses training...")
    df_movies = df_movies.sample(fraction=0.3, seed=42)
    df_movies.cache()
    print(f"Jumlah data yang akan diproses: {df_movies.count()} baris.")

    potential_text_cols = ["description", "genre", "theme", "actors", "directors", "writers", "tagline", "studio"]
    existing_text_cols = [c for c in potential_text_cols if c in df_movies.columns]
    fill_null_map = {c: "" for c in existing_text_cols}
    df_movies = df_movies.na.fill(fill_null_map)
    print("Pembersihan data null selesai.")

    print("Memulai proses 'Movie Like This' dengan LSH (parameter dilonggarkan)...")
    df_movies_lsh = df_movies.withColumn("text_features", concat_ws(" ", *[col(c) for c in existing_text_cols]))

    tokenizer = Tokenizer(inputCol="text_features", outputCol="words")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    hashingTF = HashingTF(inputCol="filtered_words", outputCol="raw_features", numFeatures=2**16)
    idf = IDF(inputCol="raw_features", outputCol="features")
    
    # --- PERUBAHAN PARAMETER UTAMA DI SINI ---
    # bucketLength dinaikkan dari 2.0 -> 5.0 (memperlebar "lubang jaring")
    # numHashTables diturunkan dari 3 -> 2 (mengurangi "lapisan jaring")
    lsh = BucketedRandomProjectionLSH(inputCol="features", outputCol="hashes", bucketLength=5.0, numHashTables=2)
    
    pipeline = Pipeline(stages=[tokenizer, remover, hashingTF, idf, lsh])
    
    print("Fitting LSH pipeline...")
    model = pipeline.fit(df_movies_lsh)
    print("Pipeline fitting selesai.")
    
    featured_df = model.transform(df_movies_lsh)
    
    print("Mencari pasangan film yang mirip (approxSimilarityJoin)...")
    # Threshold jarak juga kita naikkan sedikit dari 1.0 -> 2.0 untuk menerima pasangan yang 'cukup mirip'
    df_recs = model.stages[-1].approxSimilarityJoin(featured_df, featured_df, 2.0, distCol="distance")
    print("Pencarian pasangan terdekat selesai.")

    # Olah hasil
    df_recs_filtered = df_recs.select(col("datasetA.id").alias("id_A"), col("datasetB.id").alias("id_B"), "distance") \
        .filter(col("id_A") < col("id_B"))

    window = Window.partitionBy("id_A").orderBy(col("distance").asc())
    top_n_recs = df_recs_filtered.withColumn("rank", expr("row_number() over (partition by id_A order by distance asc)")).where(col("rank") <= 5)

    final_recs = top_n_recs.groupBy("id_A").agg(expr("collect_list(id_B) as recommendations"))
    final_recs = final_recs.withColumnRenamed("id_A", "id")
    
    final_recs.write.mode("overwrite").parquet("s3a://movies/ml_results/content_recommendations")
    print("Hasil rekomendasi 'Movie Like This' (LSH) berhasil disimpan ke MinIO.")
    
    spark.stop()
    print("Spark session dihentikan. Proses batch selesai.")

if __name__ == "__main__":
    main()
