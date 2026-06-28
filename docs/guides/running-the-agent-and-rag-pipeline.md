# Panduan — Menjalankan Agent (Gemini) & Memahami Pipeline RAG

> **Untuk siapa**: teman-teman tim yang baru masuk ke project ini dan mau
> (1) menjalankan agent di lokal, dan (2) paham gimana dokumen kita berubah
> jadi jawaban — alur **chunking → embedding → vector database**.
>
> Dokumen ini sengaja ditulis Bahasa Indonesia biar cepat dicerna. Istilah
> teknis & perintah tetap dibiarkan apa adanya.
>
> **Bacaan pendamping**:
> - [Guide — LLM gateway & provider swapping](./llm-gateway-and-model-swap.md) (kenapa semua call LLM lewat satu pintu, dan cara ganti provider)
> - [ADR 0004 — RAG stack: ChromaDB + fastembed](../adr/0004-rag-stack.md) (kenapa kita pilih tool ini)
> - [`AGENTS.md`](../../AGENTS.md) (aturan main repo)

---

## Bagian A — Menjalankan agent di lokal

### A.0 Gambaran besar dulu

Aplikasi ini punya 2 proses yang jalan barengan + 1 langkah persiapan data:

```
┌─────────────┐      HTTP/SSE       ┌──────────────────┐
│  Frontend   │ ───────────────────▶│  Backend (API)   │
│  Astro+Preact│  POST /api/chat     │  FastAPI + LangGraph
│  :4321      │ ◀───────────────────│  :8000           │
└─────────────┘   stream jawaban     └────────┬─────────┘
                                              │ cari dokumen
                                              ▼
                                     ┌──────────────────┐
                                     │  Vector DB        │
                                     │  ChromaDB         │
                                     │  (.data/chroma)   │
                                     └──────────────────┘
                                       ▲ diisi oleh `just index`
```

- **Frontend** (port `4321`) — UI chat.
- **Backend** (port `8000`) — otak agent: nerima pertanyaan, manggil LLM (Gemini), manggil "skill" (termasuk pencarian dokumen).
- **Vector DB** (ChromaDB) — tempat dokumen yang sudah diprokses disimpan. **Harus diisi dulu** lewat `just index` sebelum agent bisa menjawab dengan benar.

### A.1 Prasyarat (sekali setup)

| Tool | Buat apa | Install |
|---|---|---|
| `just` | command runner (pintu depan semua perintah) | `scoop install just` |
| `uv` | manajer Python (jangan pakai `pip`/venv manual) | lihat docs uv |
| `pnpm` + Node | build & jalanin frontend | lihat docs pnpm |

> OS acuan tim: **Windows 11 + PowerShell**. `just` di sini otomatis pakai PowerShell.

### A.2 Install dependency

```powershell
just bootstrap
```

Ini menjalankan `install-fe` (pnpm), `install-be` (uv sync), dan `install-e2e` (Playwright) sekaligus.

### A.3 Siapkan `.env` (di sinilah Gemini dipilih)

Salin template lalu isi:

```powershell
Copy-Item .env.example .env
```

Lalu edit `.env` — minimal 2 baris ini buat pakai Gemini:

```bash
LITELLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=AIza...kunci_kamu...
```

> 🔑 Ambil API key di **Google AI Studio**: https://aistudio.google.com/apikey
>
> ⚠️ Perhatikan prefix `gemini/` — itu namespace provider milik LiteLLM.
> Tanpa prefix itu, LiteLLM kira kamu mau model OpenAI bernama
> `gemini-2.5-flash` (gak ada) → error 404.

Variabel lain yang relevan (sudah ada default-nya di `.env.example`):

```bash
CHROMA_PERSIST_DIR=./.data/chroma   # lokasi vector DB di disk
FRONTEND_PORT=4321
BACKEND_PORT=8000
# LANGFUSE_* → opsional; buat tracing. Kosong = tracing di-skip, app tetap jalan.
```

> Mau pindah ke Claude/GPT? **Tinggal ganti `LITELLM_MODEL` + API key-nya**, gak ada perubahan kode. Detailnya di [guide LLM gateway](./llm-gateway-and-model-swap.md).

### A.4 Bangun index (WAJIB sebelum chat)

```powershell
just index
```

Ini membaca semua dokumen di `docs/` dan mengisinya ke ChromaDB. **Kalau langkah ini dilewat, agent akan jawab "tidak menemukan dokumen"** karena vector DB-nya kosong. Detail apa yang terjadi di sini → **Bagian B**.

### A.5 Jalankan

```powershell
just dev          # FE + BE sekaligus
```

atau pisah (berguna saat debugging):

```powershell
just dev-be       # backend saja, http://localhost:8000
just dev-fe       # frontend saja, http://localhost:4321
```

### A.6 Verifikasi

- Buka **http://localhost:4321**, ketik pertanyaan.
- Atau cek cepat lewat shell:

```powershell
curl http://localhost:8000/api/health      # {"status":"healthy"}
curl http://localhost:8000/api/meta        # {"model":"gemini/gemini-2.5-flash"}
curl http://localhost:8000/api/products    # daftar produk buat picker
```

Kalau `/api/meta` menampilkan model Gemini dan `/api/products` mengembalikan
daftar produk, berarti backend + index sudah benar.

### A.7 Troubleshooting cepat

| Gejala | Kemungkinan sebab & solusi |
|---|---|
| Agent jawab "tidak menemukan" / `/api/products` kosong | Index belum dibangun → jalankan `just index`. |
| Habis ubah prompt/kode tapi gak ngefek | Backend perlu restart (`just dev-be`). Pakai `--reload`, tapi kalau ragu, restart manual. |
| Ganti `product_id` sebuah file tapi metadata lama nyangkut | ChromaDB `upsert` gak hapus key lama → wipe penuh: `rm -rf apps/backend/.data/chroma; just index`. |
| Jawaban gak nyambung / "connection dropped" di UI | Jangan jalanin **dua** backend di port 8000 sekaligus (Windows mengizinkan dua-duanya bind, request jadi ngaco). Pastikan cuma satu. |

---

## Bagian B — Pipeline RAG: chunking → embedding → vector database

### B.0 Kenapa harus repot begini?

LLM **tidak bisa** kita suapi semua dokumen mentah tiap pertanyaan — terlalu
panjang, mahal, lambat. Jadi triknya (namanya **RAG** — Retrieval-Augmented
Generation):

1. Ubah dokumen jadi **angka (vektor)** yang menangkap *makna*-nya.
2. Simpan di database khusus.
3. Saat user nanya, ambil **potongan paling relevan** saja, lalu kasih ke LLM
   buat disusun jadi jawaban + sitasi sumber.

> **Catatan urutan**: judulnya orang sering bilang "embed → chunk", tapi urutan
> sebenarnya adalah **chunk dulu, baru embed**. Kita potong dokumen dulu jadi
> serpihan, baru tiap serpihan di-embed. Logis: kamu gak bisa "meng-angka-kan
> makna" satu dokumen raksasa sekaligus dengan presisi.

Semua tahap di bawah dijalankan oleh **satu perintah**: `just index`
(yang manggil `agent.indexing.build_index()` di
[`apps/backend/src/agent/indexing.py`](../../apps/backend/src/agent/indexing.py)).
Mental model-nya 4 kata:

```
discover → chunk → embed → upsert
```

### B.1 Discover — pilih file mana yang masuk

Di `indexing.py` ada daftar `SOURCE_DISCOVERERS`:

- `discover_top_level_docs()` → `docs/product-catalog.md`, `docs/architecture.md`
- `discover_product_docs()` → semua `.md` di `docs/products/`
- `discover_knowledge_base()` → `docs/knowledge-base/*.md` (di sinilah dok produk kita sekarang)

> Mau nambah sumber? Tambah satu fungsi ke list ini. Itu saja.

### B.2 Chunk — potong dokumen jadi serpihan kecil

Satu file besar dipotong jadi banyak **chunk**. Fungsi `chunk_file()` memotong
dalam **2 lapis**:

1. **`MarkdownHeaderTextSplitter`** — potong berdasarkan heading `#`/`##`/`###`.
   Tujuannya tiap chunk **menghormati batas section**, dan kita bisa mencatat
   "chunk ini dari Section X > Subsection Y" (`heading_path`) buat sitasi.
2. **`RecursiveCharacterTextSplitter`** — kalau satu section masih kebesaran,
   dipotong lagi ke target ~`3200` karakter (`CHUNK_TARGET_CHARS`, ≈800 token)
   dengan **overlap `400`** karakter (`CHUNK_OVERLAP_CHARS`).

**Kenapa overlap?** Biar konsep yang kebetulan jatuh di perbatasan potongan
tidak terpotong separuh — tepi antar-chunk sedikit tumpang tindih.

**Kenapa serpihan kecil?** Pencarian jadi presisi (yang diambil cuma bagian
relevan, bukan seluruh dokumen), dan muat di context window LLM.

Tiap chunk juga dapat **metadata**: `source` (path file), `product_id` +
`product_name`, `heading_path`, `chunk_index`, dan `chunk_id` deterministik
berformat `"<source>::<index>"`.

### B.3 Embed — ubah teks chunk jadi vektor

Fungsi `_embed_texts()` memakai **fastembed** dengan model
`BAAI/bge-small-en-v1.5`. Tiap teks chunk → jadi **list angka** (vektor,
ratusan dimensi).

**Apa itu embedding?** Bayangkan tiap potongan teks dikasih "koordinat makna"
di ruang berdimensi tinggi. Aturannya: **teks yang maknanya mirip → koordinat
(vektor)-nya berdekatan**. Itulah yang bikin "pencarian berbasis makna"
(bukan cocok kata persis) jadi mungkin.

Model ini jalan **lokal** (gratis, tanpa API key); download sekali (~50MB),
lalu di-cache.

> ⚠️ **Invariant terpenting**: model embedding di **index-time** dan
> **query-time WAJIB sama**. Vektor dari model berbeda tidak sebanding →
> ranking jadi ngawur. Makanya `EMBEDDING_MODEL_NAME` muncul di dua tempat
> (`indexing.py` dan `search_docs/handler.py`) dengan komentar "ganti satu,
> ganti dua-duanya, lalu reindex".

### B.4 Upsert — simpan ke vector database

`collection.upsert(ids, documents, metadatas, embeddings)` menyimpan semuanya
ke **ChromaDB**. Dua sifat penting:

- **Idempoten** — karena `chunk_id` deterministik, menjalankan `just index` 2x
  tidak bikin duplikat; yang sama ditimpa.
- **Prune stale** — `_prune_stale_chunks()` menghapus chunk dari file yang
  sudah dihapus/rename, agar index selalu cermin isi disk.

### B.5 Saat user nanya (retrieval) — melengkapi gambaran

Ada di [`search_docs/handler.py`](../../apps/backend/src/mcp_servers/search_docs/handler.py):

1. Query user **di-embed pakai model yang SAMA**.
2. ChromaDB mencari **tetangga terdekat** (nearest-neighbor) dari vektor query →
   chunk yang maknanya paling mirip.
3. Bisa dibatasi per produk via `where={"product_id": ...}` (fitur scope picker).
4. Chunk hasil dikasih ke LLM → disusun jadi jawaban + `Sources:`.

```
User: "cara membuat project baru di PortrAI"
   │  embed query (model sama)
   ▼
ChromaDB: cari vektor chunk terdekat (+ filter product_id=portrai-cms)
   │
   ▼  3-5 chunk paling relevan
LLM (Gemini): susun jawaban dari chunk + cantumkan sumber
```

---

## Bagian C — Vector database itu di mana, dan beda gak sih sama Neon/Supabase?

### C.1 Di mana letaknya?

Vector DB kita = **ChromaDB**, dan di setup ini dia **embedded + lokal di disk**:

- Lokasi: folder `.data/chroma` (diatur env `CHROMA_PERSIST_DIR`, default
  `./.data/chroma` relatif ke backend).
- Nama collection: `"docs"`.
- **Tidak ada server database terpisah** yang harus dinyalakan. ChromaDB di sini
  jalan *di dalam* proses backend dan baca/tulis file di folder itu — mirip pola
  SQLite (file-based), bukan layanan jaringan.

Artinya: hapus folder `.data/chroma` = hapus seluruh index. Bangun lagi dengan
`just index`. Tidak ada "cloud" yang perlu di-manage untuk dev lokal.

### C.2 Apakah sama dengan database biasa (Neon/Supabase)?

Jawaban singkat: **beda tujuan, tapi garisnya makin kabur.** Ini perbandingannya:

| Aspek | DB relasional (Neon / Supabase = Postgres) | Vector DB (ChromaDB) |
|---|---|---|
| **Model data** | Tabel: baris & kolom | Vektor (list angka) + metadata + teks |
| **Pertanyaan khas** | "SELECT ... WHERE umur > 20" (cocok persis / range / JOIN) | "cari 5 vektor paling *mirip* dengan ini" (kemiripan makna) |
| **Tipe query** | Eksak, deterministik (SQL) | Aproksimasi tetangga terdekat (ANN) — berbasis kemiripan |
| **Index di balik layar** | B-tree, hash | ANN seperti HNSW |
| **Cocok untuk** | Data aplikasi terstruktur (user, order, transaksi) | Pencarian semantik (RAG, rekomendasi, gambar mirip) |
| **Deploy di repo ini** | (n/a) | Embedded, file lokal `.data/chroma` |
| **Deploy Neon/Supabase** | Postgres ter-manage di cloud | (n/a) |

Intinya:

- **Neon / Supabase = Postgres ter-manage.** Itu database **relasional** —
  jago menjawab "ambil baris yang nilainya = X", JOIN antar-tabel, transaksi
  ACID. Buat data aplikasi (akun user, pesanan, dsb).
- **ChromaDB = purpose-built vector DB.** Jago satu hal: "diberi sebuah vektor,
  temukan vektor-vektor lain yang paling mirip, cepat". Itu yang RAG butuh.

### C.3 Plot twist: mereka tidak saling eksklusif

Ini bagian yang sering bikin "oh!":

- **Postgres bisa jadi vector DB** lewat ekstensi **`pgvector`**. Dan
  **Supabase mendukung pgvector** secara bawaan — jadi kamu *bisa* menyimpan
  embedding + melakukan similarity search **langsung di Supabase**, di tabel
  yang sama dengan data relasional kamu.
- Jadi pilihannya bukan "vector DB ATAU Postgres", melainkan **tool khusus
  (Chroma/Qdrant/Pinecone) vs Postgres+pgvector**.

**Kenapa repo ini pakai Chroma, bukan Supabase+pgvector?** Lihat
[ADR 0004](../adr/0004-rag-stack.md). Ringkasnya: untuk skala & kebutuhan dev
lokal kita, Chroma = **nol infrastruktur** (embedded, file lokal, tanpa server,
tanpa akun cloud). Kalau nanti datanya membesar atau butuh dipakai banyak
service, pindah ke vector store ter-manage (atau Postgres+pgvector) adalah
keputusan ber-ADR tersendiri — dan kode pencariannya terisolasi di satu skill
(`search_docs`), jadi migrasinya terlokalisir.

---

## Rekap satu layar

- **Jalanin**: `just bootstrap` → isi `.env` (`LITELLM_MODEL=gemini/gemini-2.5-flash` + `GEMINI_API_KEY`) → `just index` → `just dev`.
- **Pipeline RAG** = `discover → chunk → embed → upsert`, semua via `just index`.
- **Chunk dulu, baru embed.** Embedding = "koordinat makna"; teks mirip → vektor berdekatan.
- **Model embedding index-time & query-time WAJIB sama.**
- **Vector DB kita** = ChromaDB, embedded & lokal di `.data/chroma` (mirip SQLite, bukan server terpisah).
- **Beda dari Neon/Supabase**: itu Postgres relasional (query eksak/SQL); vector DB buat pencarian kemiripan. Tapi **Supabase pun bisa vektor** via `pgvector` — garisnya kabur.

---

## See also

- [Guide — LLM gateway & provider swapping](./llm-gateway-and-model-swap.md)
- [ADR 0004 — RAG stack: ChromaDB + fastembed](../adr/0004-rag-stack.md)
- [`apps/backend/src/agent/indexing.py`](../../apps/backend/src/agent/indexing.py) — pipeline indexing (baca docstring-nya)
- [`apps/backend/src/mcp_servers/search_docs/handler.py`](../../apps/backend/src/mcp_servers/search_docs/handler.py) — sisi retrieval
- [`AGENTS.md`](../../AGENTS.md) — aturan main repo
- [pgvector](https://github.com/pgvector/pgvector) · [Supabase Vector](https://supabase.com/docs/guides/ai) — kalau penasaran soal "Postgres jadi vector DB"
