from pyspark.sql import SparkSession
from pyspark.ml.feature import HashingTF, IDF, Tokenizer, StopWordsRemover, CountVectorizer
from pyspark.ml.classification import LogisticRegression
from pyspark.ml import Pipeline
from pyspark.sql.functions import col, udf, concat_ws, when, split  # <-- PENAMBAHAN FUNGSI DI SINI
from pyspark.sql.types import ArrayType, StringType
from pyspark.ml.linalg import SparseVector
from pyspark.ml.feature import VectorAssembler

def get_spark_session():
    """Membangun dan mengembalikan Spark Session dengan konfigurasi MinIO."""
    return SparkSession.builder \
        .appName("MovieBatchProcessing") \
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
    # Baca data dari MinIO
    df_movies = spark.read.csv("s3a://movies/final_movies_dataset.csv", header=True, inferSchema=True)
    
    # Membersihkan data null untuk kolom yang akan diproses
    df_movies = df_movies.na.fill({
        "description": "",
        "genre": "",
        "theme": "",
        "minute": 0,
        "rating": 0.0
    })
    print("Data berhasil dibaca dan dibersihkan.")

    # --- Fitur 1: Movie Like This (Content-Based) ---
    print("Memulai proses 'Movie Like This'...")
    # Menggabungkan kolom teks menjadi satu fitur
    df_movies = df_movies.withColumn("text_features", concat_ws(" ", col("description"), col("genre"), col("theme")))
    
    # Membuat pipeline NLP
    tokenizer = Tokenizer(inputCol="text_features", outputCol="words")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    hashingTF = HashingTF(inputCol="filtered_words", outputCol="raw_features")
    idf = IDF(inputCol="raw_features", outputCol="features")
    
    pipeline_similarity = Pipeline(stages=[tokenizer, remover, hashingTF, idf])
    model_similarity = pipeline_similarity.fit(df_movies)
    featured_df = model_similarity.transform(df_movies)
    
    # Simpan hasil (vektor fitur) ke MinIO
    featured_df.select("id", "name", "features").write.mode("overwrite").parquet("s3a://movies/ml_results/similarities")
    print("Model 'Movie Like This' selesai diproses dan hasilnya disimpan di MinIO.")

    # --- Fitur 2: Recomended by Audience Age (Klasifikasi) ---
    print("Memulai proses 'Recomended by Audience Age'...")
    # Membuat label dummy karena tidak ada di dataset
    df_movies = df_movies.withColumn("audience_age", 
        when((col("rating") > 7) & (~col("genre").rlike("Horror|Thriller")), "Semua Umur")
        .otherwise("Dewasa")
    )
    
    # Kita tidak akan melatih model klasifikasi kompleks di sini, hanya membuat label
    # dan menyimpannya. Pelatihan model sebenarnya akan lebih rumit.
    # Untuk prototipe, menyimpan label ini sudah cukup.
    df_movies.select("id", "name", "audience_age", "poster_filename").write.mode("overwrite").parquet("s3a://movies/ml_results/audience_predictions")
    print("Model 'Audience Age' selesai diproses dan hasilnya disimpan di MinIO.")

    spark.stop()
    print("Spark session dihentikan. Proses batch selesai.")

if __name__ == "__main__":
    main()
