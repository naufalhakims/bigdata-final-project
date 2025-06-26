from pyspark.sql import SparkSession
from pyspark.sql.functions import col, concat_ws, split
from pyspark.ml.feature import CountVectorizer, RegexTokenizer, StopWordsRemover
from pyspark.ml import Pipeline

def get_spark_session():
    return SparkSession.builder \
        .appName("TrainVectorizerModel") \
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

    print("Membaca seluruh data dari MinIO untuk training model...")
    movies_df = spark.read.csv("s3a://movies/final_movies_dataset.csv", header=True, inferSchema=True)
    
    print("Membersihkan dan mempersiapkan data...")
    movies_df = movies_df.select("description", "genre", "theme")
    movies_df = movies_df.na.fill("", subset=["description", "genre", "theme"])
    
    # Feature Engineering Pipeline
    tokenizer = RegexTokenizer(inputCol="description", outputCol="words", pattern="\\W")
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")
    # Gabungkan fitur teks
    movies_df = movies_df.withColumn("tags", concat_ws(" ", col("filtered_words"), col("genre"), col("theme")))
    movies_df = movies_df.withColumn("tags", split(col("tags"), " "))
    
    # Vectorizer
    cv = CountVectorizer(inputCol="tags", outputCol="features", vocabSize=5000, minDF=5)
    
    # Buat pipeline feature engineering
    feature_pipeline = Pipeline(stages=[tokenizer, remover, cv])
    
    print("Memulai training pipeline model...")
    # Latih model pada seluruh data
    pipeline_model = feature_pipeline.fit(movies_df)
    print("Training selesai.")
    
    # Simpan seluruh pipeline model yang sudah terlatih ke MinIO
    model_path = "s3a://movies/ml_models/vectorizer_pipeline_model"
    print(f"Menyimpan model ke {model_path}...")
    pipeline_model.write().overwrite().save(model_path)
    
    print(f"✅ Model pipeline berhasil disimpan ke MinIO.")
    spark.stop()

if __name__ == "__main__":
    main()