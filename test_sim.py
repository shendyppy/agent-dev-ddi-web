import os
from google import genai
import numpy as np

def cosine_similarity(a, b):
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    return np.dot(a, b) / (norm_a * norm_b)

client = genai.Client()

query = "bagaimana cara agar participant mendapatkan email untuk mengerjakan portrai?"
doc = """### B. Participants (`/participants`)
- **Tujuan:** Mengelola peserta yang akan di-assess, serta mengundang mereka ke Web PortrAI Participant.
- **SOP Cara Mengundang Participant Mengerjakan Simulasi / Soal di Web PortrAI Participant:**

  Terdapat dua skenario alur kerja berdasarkan jenis *Company* (Internal vs External):
  
  **1. Untuk Participant Internal Company:**
  - **Langkah 1:** Input data participant (sebagai karyawan) melalui menu **Manage Employee** terlebih dahulu.
  - **Langkah 2:** Masuk ke menu **Manage Project**. Buat project baru jika belum ada. Jika project sudah ada, klik tombol **Detail** di baris tabel project yang sesuai.
  - **Langkah 3:** Di dalam detail project, buat **Batch** jika belum ada. Jika batch sudah ada, klik tombol **Detail** di baris tabel batch tersebut.
  - **Langkah 4:** Tambahkan participant (add participant) ke dalam batch tersebut.
  - **Langkah 5:** Setelah berhasil ditambahkan ke batch, kirimkan email ke participant tersebut. Melalui email inilah participant akan mendapatkan akses / link untuk mengerjakan simulasi di Web PortrAI Participant.

  **2. Untuk Participant External Company:**
  - Berbeda dengan internal, participant eksternal **tidak perlu diinput** di menu Manage Employee terlebih dahulu.
  - Anda bisa langsung menuju menu/halaman **Manage Client Project** sisanya seperti pada langkah di internal company, lalu ke **Participant** dan langsung menambahkan data participant-nya di sana, kemudian langsung mengirimkan undangan (email)."""

try:
    q_emb = client.models.embed_content(model='models/embedding-001', contents=query).embeddings[0].values
    d_emb = client.models.embed_content(model='models/embedding-001', contents=doc).embeddings[0].values
    print("models/embedding-001 Similarity:", cosine_similarity(q_emb, d_emb))
except Exception as e:
    print("embedding-001 failed:", e)

try:
    q_emb = client.models.embed_content(model='text-embedding-004', contents=query).embeddings[0].values
    d_emb = client.models.embed_content(model='text-embedding-004', contents=doc).embeddings[0].values
    print("text-embedding-004 Similarity:", cosine_similarity(q_emb, d_emb))
except Exception as e:
    print("text-embedding-004 failed:", e)

