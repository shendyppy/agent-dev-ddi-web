import os
import re
import numpy as np
from google import genai
from google.genai import types
from .settings import REPO_ROOT

def cosine_similarity(a, b):
    """Menghitung cosine similarity antara dua vektor."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)

def load_and_chunk_document(folder_path):
    """Membaca semua file .md dari sebuah folder dan memecahnya menjadi bagian (chunks) berdasarkan heading markdown.
    
    Dengan membaca seluruh folder, kita bisa menambahkan file doc-context baru
    tanpa perlu mengubah kode — cukup taruh file .md baru di folder tersebut.
    """
    all_chunks = []
    
    md_files = sorted(folder_path.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"Tidak ada file .md ditemukan di folder {folder_path}")
    
    for md_file in md_files:
        print(f"[RAG] Loading document: {md_file.name}")
        with open(md_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Memecah berdasarkan heading markdown (## atau ###) agar konteks section tetap utuh
        chunks = re.split(r'\n(?=#{2,3} )', text)
        file_chunks = [c.strip() for c in chunks if c.strip()]
        all_chunks.extend(file_chunks)
    
    print(f"[RAG] Total {len(all_chunks)} chunks loaded from {len(md_files)} file(s)")
    return all_chunks

class PortraiCMSAgent:
    def __init__(self):
        self.docs_folder = REPO_ROOT / "docs" / "knowledge-base"
        self.chunks = []
        # CEK DULU DATABASE EMBEDDING, JIKA SUDAH ADA MAKA LOAD, JIKA BELUM MAKA PROSES EMBEDDING DOKUMEN
        self.chunk_embeddings = []
        self.client = None
        self.chat_session = None
        
        self.system_instruction = (
            "Anda adalah asisten AI yang ramah dan cerdas. "
            "Anda sedang berinteraksi dalam sebuah percakapan, jadi ingatlah selalu identitas pengguna dan histori chat sebelumnya. "
            "Pada setiap pesan pengguna, sistem mungkin akan menyertakan 'Konteks Tambahan' dari dokumen panduan PortrAI. "
            "Gunakan konteks tambahan tersebut HANYA JIKA relevan untuk menjawab pertanyaan tentang sistem PortrAI (CMS maupun Participant) atau DDI. "
            "Jika pengguna menanyakan hal di luar konteks dokumen (misalnya tentang diri mereka, atau obrolan santai), "
            "jawablah secara natural berdasarkan histori percakapan atau pengetahuan umum Anda, tanpa perlu menyebutkan "
            "bahwa itu di luar dokumen resmi (kecuali jika benar-benar ditanya tentang fakta spesifik perusahaan). "
            "Walaupun jawaban yang didapat mengacu dari dokumen, tidak perlu menjelaskan ke user kalo data yang didapat dari dokumen yang ada. "
            "Jawab dengan optimasi yang baik agar tidak terlalu panjang."
        )

    def _initialize(self):
        if self.client is not None and self.chat_session is not None:
            return # Sudah terinisialisasi
        
        # Inisialisasi Google GenAI client (akan secara otomatis mengambil dari environment GEMINI_API_KEY)
        # Jika environment GEMINI_API_KEY tidak ada atau belum valid, harap pastikan sudah diset
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            env_path = REPO_ROOT / ".env"
            if env_path.exists():
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("GEMINI_API_KEY="):
                            val = line.strip().split("=", 1)[1].strip()
                            if val.startswith(('"', "'")) and val.endswith(('"', "'")):
                                val = val[1:-1]
                            if val:
                                api_key = val
                            break
        
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client()
        
        if not self.docs_folder.exists() or not self.docs_folder.is_dir():
            raise FileNotFoundError(f"Folder dokumen konteks {self.docs_folder} tidak ditemukan.")
            
        self.chunks = load_and_chunk_document(self.docs_folder)
        
        # Mendapatkan embeddings untuk isi dokumen secara batch (untuk performa dan menghindari rate limit/503)
        contents = [types.Content(parts=[types.Part.from_text(text=c)]) for c in self.chunks]
        resp = self.client.models.embed_content(
            model='gemini-embedding-2',
            contents=contents,
        )
        self.chunk_embeddings = [emb.values for emb in resp.embeddings]
        
        # Inisialisasi sesi Gemini Chat (opsional bisa dibuat per session/request, di sini 1 session global untuk kesederhanaan)
        self.chat_session = self.client.chats.create(
            model="gemini-2.5-flash",
            config={
                "system_instruction": self.system_instruction,
                "temperature": 0.5
            }
        )

    def get_response(self, user_input: str) -> str:
        """Mendapatkan respon RAG untuk query dari user."""
        # Pastikan sudah diinisialisasi
        self._initialize()
        
        if not user_input.strip():
            return "Mohon masukkan pertanyaan yang valid."

        # 1. RAG (Retrieval)
        # Embed pertanyaan pengguna
        query_embed_response = self.client.models.embed_content(
            model='gemini-embedding-2',
            contents=user_input,
        )
        query_embedding = query_embed_response.embeddings[0].values

        # Hitung kesamaan (similarity) kosinus
        similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in self.chunk_embeddings]
        
        # Ambil maksimal 2 chunk paling relevan
        top_k = 2
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        
        # Debug log
        print(f"[RAG Debug] Top indices: {top_indices}")
        for i in top_indices:
            print(f"[RAG Debug] Chunk {i} similarity: {similarities[i]}")

        # Gabungkan chunk yang relevan sebagai konteks (dengan threshold similarity diturunkan)
        # Karena query seringkali memiliki sinonim, threshold dibuat lebih longgar atau kita ambil yang terbaik saja
        retrieved_chunks = [self.chunks[i] for i in top_indices if similarities[i] > 0.4]
        retrieved_context = "\n\n".join(retrieved_chunks)
        print(f"[RAG Debug] Retrieved {len(retrieved_chunks)} chunks for context.")

        # 2. Augmentasi Prompt
        if retrieved_context:
            augmented_prompt = (
                f"[Konteks Tambahan (hanya gunakan jika relevan dengan pertanyaan): {retrieved_context}]\n\n"
                f"{user_input}"
            )
        else:
            augmented_prompt = user_input

        # 3. Generation
        response = self.chat_session.send_message(augmented_prompt)
        return response.text

# Buat instance global agar chunk_embeddings hanya dijalankan sekali di awal (lazy load)
portrai_agent = PortraiCMSAgent()
