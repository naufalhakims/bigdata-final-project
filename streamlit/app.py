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
            group_id='streamlit-main-consumer-group-details',
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
    if MINIO_CLIENT is None: return None
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        data = response.read()
        if object_name.endswith('.pkl'): return pickle.loads(data)
        elif object_name.endswith('.npy'): return np.load(io.BytesIO(data))
    except Exception: return None

@st.cache_data(show_spinner="Memuat dataset utama...")
def load_main_csv_data(object_name="final_movies_dataset.csv"):
    if MINIO_CLIENT is None: return pd.DataFrame()
    try:
        response = MINIO_CLIENT.get_object(BUCKET_NAME, object_name)
        return pd.read_csv(io.BytesIO(response.read()))
    except Exception: return pd.DataFrame()

@st.cache_data(show_spinner="Mengecek ketersediaan poster...")
def get_available_posters(_minio_client, _bucket_name):
    if _minio_client is None: return set()
    try:
        return {os.path.basename(obj.object_name) for obj in _minio_client.list_objects(_bucket_name, prefix="posters/", recursive=True) if obj.object_name.endswith('.jpg')}
    except Exception: return set()

# --- GANTI SELURUH FUNGSI INI DENGAN VERSI FINAL ---
def display_movie_details(movie_id, df_full_data):
    """Fungsi untuk menampilkan dialog detail film."""
    try:
        # Cari data film berdasarkan ID
        movie_data = df_full_data[df_full_data['id'] == movie_id].iloc[0]
        
        # Panggil st.dialog() untuk membuat dialog kosong.
        # Semua perintah st. berikutnya akan otomatis masuk ke dalam dialog ini.
        st.dialog(f"Detail: {movie_data['name']}")

        # Sekarang kita isi kontennya
        col1, col2 = st.columns([1, 2])
        
        with col1:
            if pd.notna(movie_data['poster_filename']) and movie_data['poster_filename'] in st.session_state.available_posters:
                st.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{movie_data['poster_filename']}")
            else:
                st.image(PLACEHOLDER_IMAGE)
        
        with col2:
            st.markdown(f"**Tahun:** `{int(movie_data['date'])}`" if pd.notna(movie_data['date']) and movie_data['date'] != 0 else "")
            st.markdown(f"**Rating:** `⭐ {movie_data['rating']}`" if pd.notna(movie_data['rating']) else "")
            st.markdown(f"**Durasi:** `{int(movie_data['minute'])} menit`" if pd.notna(movie_data['minute']) else "")
            st.markdown(f"**Genre:** `{movie_data['genre']}`" if pd.notna(movie_data['genre']) else "")
            
            st.subheader("Deskripsi")
            st.write(movie_data['description'] if pd.notna(movie_data['description']) else "Tidak ada deskripsi.")
            
            with st.expander("Lihat detail lainnya"):
                st.write(f"**Tagline:** *{movie_data['tagline']}*")
                st.write(f"**Studio:** {movie_data['studio']}")
                st.write(f"**Aktor:** {str(movie_data['actors'])[:300]}...")

    except (IndexError, KeyError):
        # Untuk menampilkan error, kita juga panggil dialog lalu st.error
        st.dialog("Error")
        st.error("Gagal menemukan detail untuk film ini.")
    except Exception as e:
        st.dialog("Error")
        st.error(f"Terjadi error tak terduga: {e}")

# --- TAMPILAN UTAMA & NAVIGASI ---
st.sidebar.title("🎬 Movie Data Platform")
st.sidebar.info(f"Status MinIO: **{'Terhubung' if MINIO_CLIENT else 'Gagal'}**")
st.sidebar.info(f"Status Kafka: **{'Terhubung' if KAFKA_CONSUMER else 'Gagal'}**")

# Inisialisasi session state untuk dialog detail
if 'show_detail_for_id' not in st.session_state:
    st.session_state.show_detail_for_id = None

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
    st.session_state.available_posters = get_available_posters(MINIO_CLIENT, BUCKET_NAME)

    if st.session_state.show_detail_for_id:
        display_movie_details(st.session_state.show_detail_for_id, full_movies_df)
        # Reset state agar dialog tidak muncul lagi setelah ditutup/refresh
        st.session_state.show_detail_for_id = None

    if full_movies_df.empty:
        st.error("Data film utama tidak ditemukan. Pastikan proses ingesti sudah berjalan.")
    else:
        search_query = st.text_input("Cari film berdasarkan judul:", "")
        df_filtered = full_movies_df[full_movies_df['name'].str.contains(search_query, case=False, na=False)] if search_query else full_movies_df

        if 'page_number' not in st.session_state or st.session_state.get('search_query', '') != search_query:
            st.session_state.page_number = 1; st.session_state.search_query = search_query
        
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
                        container = st.container(border=True)
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in st.session_state.available_posters:
                            container.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                        else:
                            container.image(PLACEHOLDER_IMAGE, use_container_width=True)
                        container.caption(row['name'])
                        # Tombol detail di dalam kontainer
                        if container.button("Lihat Detail", key=f"detail_{row['id']}"):
                            st.session_state.show_detail_for_id = row['id']
                            st.rerun() # Refresh halaman untuk menampilkan dialog
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
    st.write("Model ini dibuat menggunakan Scikit-learn.")

    # --- DATA LOADING ---
    model_movies_df = load_model_from_minio("ml_results/sklearn_model/movies_df.pkl")
    cosine_sim = load_model_from_minio("ml_results/sklearn_model/similarity_matrix.npy")
    full_movies_df = load_main_csv_data()
    st.session_state.available_posters = get_available_posters(MINIO_CLIENT, BUCKET_NAME)

    # --- INITIALIZE SESSION STATE FOR THIS PAGE ---
    if 'last_recommendations' not in st.session_state:
        st.session_state.last_recommendations = pd.DataFrame()

    # --- DIALOG DISPLAY LOGIC (RUNS FIRST) ---
    # This logic now correctly shows the dialog without re-rendering the whole page underneath it.
    if st.session_state.show_detail_for_id:
        display_movie_details(st.session_state.show_detail_for_id, full_movies_df)
        # Reset the state so the dialog doesn't pop up again on the next interaction.
        st.session_state.show_detail_for_id = None

    # --- MAIN PAGE CONTENT ---
    if model_movies_df is not None and cosine_sim is not None and not full_movies_df.empty:
        movie_list = sorted(model_movies_df['name'].tolist())
        selected_movie = st.selectbox("Pilih sebuah film untuk menemukan yang serupa:", movie_list)

        if st.button("Dapatkan Rekomendasi"):
            st.subheader(f"Rekomendasi film yang mirip dengan '{selected_movie}':")
            try:
                # --- RECOMMENDATION LOGIC ---
                idx = model_movies_df[model_movies_df['name'] == selected_movie].index[0]
                sim_scores = sorted(list(enumerate(cosine_sim[idx])), key=lambda x: x[1], reverse=True)
                movie_indices = [i[0] for i in sim_scores[1:6]]
                
                recommended_movies_info = model_movies_df.iloc[movie_indices][['id', 'name']] # Get ID and name from model data
                # Merge with the full dataset to get poster and other details
                final_recs_df = pd.merge(recommended_movies_info, full_movies_df, on='id', how='left')
                
                # Save the results to session state
                st.session_state.last_recommendations = final_recs_df

            except Exception as e:
                st.error(f"Terjadi error saat mencari rekomendasi: {e}")
                st.session_state.last_recommendations = pd.DataFrame() # Clear old results on error

        # --- DISPLAY RESULTS (moved outside the button 'if' block) ---
        # Always try to display the last recommendations stored in the session state.
        # This ensures they persist across reruns (like when opening/closing a dialog).
        if not st.session_state.last_recommendations.empty:
            cols = st.columns(5)
            # Use the DataFrame stored in the session state
            for i, (_, row) in enumerate(st.session_state.last_recommendations.iterrows()):
                    with cols[i]:
                        container = st.container(border=True)
                        # Use the correct 'name' column from the merge (name_y is from full_movies_df)
                        display_name = row.get('name_y', row['name_x']) 
                        
                        if pd.notna(row['poster_filename']) and row['poster_filename'] in st.session_state.available_posters:
                            container.image(f"http://localhost:9000/{BUCKET_NAME}/posters/{row['poster_filename']}", use_container_width=True)
                        else:
                            container.image(PLACEHOLDER_IMAGE, use_container_width=True)
                        
                        container.caption(display_name)
                        
                        # The key must be unique for each button
                        if container.button("Lihat Detail", key=f"rec_detail_{row['id']}"):
                            st.session_state.show_detail_for_id = row['id']
                            st.rerun() # Rerun to trigger the dialog display logic at the top

    else:
        st.error("Gagal memuat model rekomendasi atau data film utama. Pastikan Spark Job (batch) dan proses ingesti telah berhasil dijalankan.")

# ==============================================================================
# HALAMAN 3: STREAMING ETL DASHBOARD
# ==============================================================================
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
            df = pd.DataFrame(data_list); csv_buffer = io.StringIO(); df.to_csv(csv_buffer, index=False)
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
            raw_messages = KAFKA_CONSUMER.poll(timeout_ms=1000, max_records=50)
            
            if raw_messages:
                for topic_partition, messages in raw_messages.items():
                    for msg in messages:
                        st.session_state.movie_batch.append(msg.value)
                        st.session_state.total_processed += 1
            
            current_time = time.time()
            if current_time - st.session_state.last_save_time >= 30:
                if st.session_state.movie_batch:
                    save_batch_to_minio(st.session_state.movie_batch)
                    st.session_state.movie_batch = []
                st.session_state.last_save_time = current_time

            with placeholder.container():
                col1, col2 = st.columns(2)
                col1.metric("Total Film Diterima", st.session_state.total_processed)
                col2.metric("Film di Batch Saat Ini", len(st.session_state.movie_batch))
                
                st.subheader("Log Data Masuk (5 Terakhir)")
                if st.session_state.movie_batch:
                    df_log = pd.DataFrame(st.session_state.movie_batch).tail(5)
                    st.dataframe(df_log[['name', 'genre', 'rating']], use_container_width=True)
                else:
                    st.info("Menunggu data berikutnya dari Kafka...")
            
            time.sleep(1)