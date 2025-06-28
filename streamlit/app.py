import streamlit as st
import pandas as pd
from minio import Minio
from kafka import KafkaConsumer
import time
import io
import pickle
import os
import math
import json
from datetime import datetime
import numpy as np

# --- KONFIGURASI DAN KONEKSI (DENGAN CACHING) ---
st.set_page_config(layout="wide", page_title="Movie Data Platform")

@st.cache_resource
def get_minio_client():
    """Membuat koneksi ke MinIO dan menyimpannya di cache."""
    try:
        client = Minio("minio:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
        client.bucket_exists("movies") # Cek koneksi
        return client
    except Exception:
        return None

@st.cache_resource
def get_kafka_consumer():
    """Membuat koneksi ke Kafka dan menyimpannya di cache."""
    try:
        consumer = KafkaConsumer(
            'movie_views',
            bootstrap_servers=['kafka:29092'],
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='streamlit-main-consumer-group',
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            consumer_timeout_ms=1000 # Timeout agar tidak block selamanya
        )
        return consumer
    except Exception:
        return None

MINIO_CLIENT = get_minio_client()
KAFKA_CONSUMER = get_kafka_consumer()
BUCKET_NAME = "movies"
PLACEHOLDER_IMAGE = "https://via.placeholder.com/200x300.png?text=Poster+Not+Found"

# --- FUNGSI-FUNGSI PEMUATAN DATA (BATCH) ---
@st.cache_data(show_spinner="Memuat model rekomendasi...")
def load_model_from_minio(object_name):
    """Membaca file model dari MinIO (.pkl atau .npy)."""
    if MINIO_CLIENT is None: return None
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        data = response.read()
        if object_name.endswith('.pkl'): return pickle.loads(data)
        elif object_name.endswith('.npy'): return np.load(io.BytesIO(data))
    except Exception: return None

@st.cache_data(show_spinner="Memuat dataset utama...")
def load_main_csv_data(object_name="final_movies_dataset.csv"):
    """Membaca data CSV utama dari MinIO."""
    if MINIO_CLIENT is None: return pd.DataFrame()
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        return pd.read_csv(io.BytesIO(response.read()))
    except Exception: return pd.DataFrame()

@st.cache_data(show_spinner="Mengecek ketersediaan poster...")
def get_available_posters(_minio_client, _bucket_name):
    """Mendapatkan set nama file poster yang valid."""
    if _minio_client is None: return set()
    try:
        return {os.path.basename(obj.object_name) for obj in _minio_client.list_objects(_bucket_name, prefix="posters/", recursive=True) if obj.object_name.endswith('.jpg')}
    except Exception: return set()
    
# --- MODIFIKASI: FUNGSI BANTU UNTUK MENAMPILKAN DETAIL ---
# Fungsi ini dibuat agar tidak ada duplikasi kode antara halaman dashboard dan rekomendasi
def display_movie_details(container, movie_row):
    """Menampilkan detail film di dalam container yang diberikan (seperti popover)."""
    container.header(movie_row['name'])
    
    if pd.notna(movie_row['tagline']) and movie_row['tagline']:
        container.caption(f"*{movie_row['tagline']}*")
    
    col1, col2 = container.columns(2)
    
    # Menampilkan Rating dan Durasi dengan penanganan nilai kosong
    rating_text = f"**Rating:** {movie_row['rating']:.1f}/5 ⭐" if pd.notna(movie_row['rating']) else "**Rating:** N/A"
    duration_text = f"**Durasi:** {int(movie_row['minute'])} menit" if pd.notna(movie_row['minute']) else "**Durasi:** N/A"
    col1.markdown(rating_text)
    col2.markdown(duration_text)

    # Menampilkan Genre dan Tanggal Rilis
    genre_text = f"**Genre:** {movie_row['genre']}" if pd.notna(movie_row['genre']) else "**Genre:** N/A"
    date_text = f"**Rilis:** {movie_row['date']}" if pd.notna(movie_row['date']) else "**Rilis:** N/A"
    col1.markdown(genre_text)
    col2.markdown(date_text)
    
    container.markdown("---")
    
    # Menampilkan Aktor, Studio, dan Negara
    if pd.notna(movie_row['actors']):
        container.markdown(f"**Aktor:** {movie_row['actors']}")
    if pd.notna(movie_row['studio']):
        container.markdown(f"**Studio:** {movie_row['studio']}")
    if pd.notna(movie_row['country']):
        container.markdown(f"**Negara:** {movie_row['country']}")
        
    container.markdown("---")
    
    # Menampilkan Deskripsi
    container.subheader("Deskripsi")
    container.write(movie_row['description'] if pd.notna(movie_row['description']) else "Tidak ada deskripsi.")


# --- TAMPILAN UTAMA & NAVIGASI ---
st.sidebar.title("🎬 Movie Data Platform")
st.sidebar.info(f"Status MinIO: **{'Terhubung' if MINIO_CLIENT else 'Gagal'}**")
st.sidebar.info(f"Status Kafka: **{'Terhubung' if KAFKA_CONSUMER else 'Gagal'}**")

# --- TAMBAHAN: Tombol Reconnect ---
if KAFKA_CONSUMER is None:
    st.cache_resource.clear()
    st.rerun()
    
page = st.sidebar.selectbox(
    "Pilih Halaman",
    ["Dashboard & Pencarian", "Rekomendasi Film (Batch)", "Streaming ETL Dashboard"]
)

# ==============================================================================
# HALAMAN 1: DASHBOARD & PENCARIAN
# ==============================================================================
if page == "Dashboard & Pencarian":
    st.header("Dashboard dan Pencarian Film")
    full_movies_df = load_main_csv_data()
    available_posters = get_available_posters(MINIO_CLIENT, BUCKET_NAME)

    if full_movies_df.empty:
        st.error("Data film utama tidak ditemukan. Pastikan proses ingesti sudah berjalan.")
    else:
        search_query = st.text_input("Cari film berdasarkan judul:", "")
        df_filtered = full_movies_df[full_movies_df['name'].str.contains(search_query, case=False, na=False)] if search_query else full_movies_df

        if 'page_number' not in st.session_state or st.session_state.get('search_query', '') != search_query:
            st.session_state.page_number = 1
            st.session_state.search_query = search_query
        
        ITEMS_PER_PAGE = 20
        total_items, total_pages = len(df_filtered), math.ceil(len(df_filtered) / ITEMS_PER_PAGE) if len(df_filtered) > 0 else 1
        if st.session_state.page_number > total_pages: st.session_state.page_number = 1
        start_idx, end_idx = (st.session_state.page_number - 1) * ITEMS_PER_PAGE, st.session_state.page_number * ITEMS_PER_PAGE
        df_page = df_filtered.iloc[start_idx:end_idx]

        if not df_page.empty:
            st.info(f"Menampilkan film {start_idx + 1}-{min(end_idx, total_items)} dari {total_items} hasil.")
            for i in range(0, len(df_page), 5):
                cols = st.columns(5)
                for j, (_, row) in enumerate(df_page.iloc[i:i+5].iterrows()):
                    with cols[j]:
                        # Tampilkan poster dengan caption sebagai fallback jika gambar tidak ada
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                            st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True, caption=row['name'])
                        else:
                            st.image(PLACEHOLDER_IMAGE, use_container_width=True, caption=row['name'])
                        
                        # --- MODIFIKASI: Tambahkan Popover untuk detail ---
                        popover = st.popover("Lihat Detail", use_container_width=True)
                        display_movie_details(popover, row) # Panggil fungsi bantu
        else:
            st.warning("Tidak ada film yang cocok dengan pencarian Anda.")

        if total_items > ITEMS_PER_PAGE:
            st.write("---"); col1, col2, col3 = st.columns([1, 2, 1])
            if col1.button("⬅️ Sebelumnya", disabled=(st.session_state.page_number <= 1)):
                st.session_state.page_number -= 1; st.rerun()
            col2.markdown(f"<div style='text-align: center;'>Halaman {st.session_state.page_number} dari {total_pages}</div>", unsafe_allow_html=True)
            if col3.button("Berikutnya ➡️", disabled=(st.session_state.page_number >= total_pages)):
                st.session_state.page_number += 1; st.rerun()

# ==============================================================================  
# HALAMAN 2: REKOMENDASI FILM (BATCH)  
# ==============================================================================  
elif page == "Rekomendasi Film (Batch)":
    st.header("Temukan Film yang Mirip (Model Batch)")
    st.write("Model ini dibuat menggunakan Scikit-learn pada 5.000-10.000 data.")

    # Inisialisasi waktu refresh model  
    if 'last_model_refresh' not in st.session_state:
        st.session_state.last_model_refresh = time.time()

    # Bersihkan cache model jika sudah lebih dari 900 detik
    if time.time() - st.session_state.last_model_refresh > 900:
        st.cache_data.clear()
        st.session_state.last_model_refresh = time.time()

    # Tambahkan opsi manual refresh
    with st.expander("🔄 Opsi Refresh Model"):
        if st.button("Muat Ulang Model dari MinIO"):
            st.cache_data.clear()
            st.session_state.last_model_refresh = time.time()
            st.success("Model berhasil dimuat ulang.")

    # Muat model dan data
    model_movies_df = load_model_from_minio("ml_results/sklearn_model/movies_df.pkl")
    cosine_sim = load_model_from_minio("ml_results/sklearn_model/similarity_matrix.npy")
    full_movies_df = load_main_csv_data()
    available_posters = get_available_posters(MINIO_CLIENT, BUCKET_NAME)

    if model_movies_df is not None and cosine_sim is not None:
        movie_list = sorted(model_movies_df['name'].tolist())
        selected_movie = st.selectbox("Pilih sebuah film untuk menemukan yang serupa:", movie_list)

        if st.button("Dapatkan Rekomendasi"):
            st.subheader(f"Rekomendasi film yang mirip dengan '{selected_movie}':")
            try:
                idx = model_movies_df[model_movies_df['name'] == selected_movie].index[0]
                sim_scores = sorted(list(enumerate(cosine_sim[idx])), key=lambda x: x[1], reverse=True)
                movie_indices = [i[0] for i in sim_scores[1:6]]

                recommended_movies_info = model_movies_df.iloc[movie_indices]
                final_recs_df = pd.merge(recommended_movies_info, full_movies_df[['id', 'poster_filename', 'name']], on='id', how='left')

                cols = st.columns(5)
                for i, (_, row) in enumerate(final_recs_df.iterrows()):
                    with cols[i]:
                        display_name = row.get('name_y', row['name_x'])
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in available_posters:
                            st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True, caption=display_name)
                        else:
                            st.image(PLACEHOLDER_IMAGE, use_container_width=True, caption=display_name)
            except Exception as e:
                st.error(f"Terjadi error: {e}")
    else:
        st.error("Gagal memuat model rekomendasi. Pastikan Spark Job (batch) telah berhasil dijalankan.")

# ==============================================================================
# HALAMAN 3: STREAMING ETL DASHBOARD
# ==============================================================================
# Bagian ini tidak diubah karena tidak ada permintaan.
elif page == "Streaming ETL Dashboard":
    st.header("Streaming ETL: Kafka ke MinIO")
    st.write("Aplikasi ini secara live menerima data dari Kafka, mengumpulkannya, dan menyimpannya sebagai file CSV per batch ke MinIO.")

    if KAFKA_CONSUMER is None:
        st.error("Gagal terhubung ke Kafka. Tidak bisa menampilkan data streaming.")
    else:
        if 'movie_batch' not in st.session_state: st.session_state.movie_batch = []
        if 'last_save_time' not in st.session_state: st.session_state.last_save_time = time.time()
        if 'total_processed' not in st.session_state: st.session_state.total_processed = 0

        def save_batch_to_minio(data_list):
            if not data_list or MINIO_CLIENT is None: return
            df = pd.DataFrame(data_list)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes = csv_buffer.getvalue().encode('utf-8')
            filename = f"streamed_data/batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            try:
                MINIO_CLIENT.put_object("movies", filename, io.BytesIO(csv_bytes), len(csv_bytes))
                st.toast(f"✅ Batch berisi {len(data_list)} film disimpan ke MinIO.")
            except Exception as e:
                st.toast(f"Gagal menyimpan batch ke MinIO: {e}")
        
        st.info("Memulai pengambilan data dari Kafka... Halaman akan auto-refresh.")
        
        placeholder = st.empty()

        while True:
            raw_messages = KAFKA_CONSUMER.poll(timeout_ms=1000, max_records=100)
            
            if not raw_messages:
                pass
            else:
                for topic_partition, messages in raw_messages.items():
                    for msg in messages:
                        movie = msg.value
                        st.session_state.movie_batch.append(movie)
                        st.session_state.total_processed += 1
            
            current_time = time.time()
            if current_time - st.session_state.last_save_time >= 120:
                if st.session_state.movie_batch:
                    save_batch_to_minio(st.session_state.movie_batch)
                    st.session_state.movie_batch = []
                st.session_state.last_save_time = current_time

            with placeholder.container():
                col1, col2 = st.columns(2)
                col1.metric("Total Film Diterima Sejak Halaman Dimuat", st.session_state.total_processed)
                col2.metric("Film di Batch Saat Ini", len(st.session_state.movie_batch))
                
                st.subheader("Log Data Masuk (5 Terakhir)")
                if st.session_state.movie_batch:
                    df_log = pd.DataFrame(st.session_state.movie_batch).tail(5)
                    st.dataframe(df_log[['name', 'genre', 'rating']], use_container_width=True)
                else:
                    st.info("Menunggu data berikutnya dari Kafka...")
            
            time.sleep(0.1)
