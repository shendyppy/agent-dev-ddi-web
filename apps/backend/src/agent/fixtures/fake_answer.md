# Menjalankan proyek di lokal

Fixture jawaban untuk **LLM_FAKE_MODE**. Isinya sengaja memakai setiap
elemen markdown yang bisa muncul di transcript, supaya rendering-nya bisa
dicek tanpa memanggil model sungguhan.

## Langkah cepat

1. Salin `.env.example` menjadi `.env`, lalu isi `GEMINI_API_KEY`.
2. Jalankan `just dev` — perintah ini menyalakan FE, BE, dan MCP sekaligus.
3. Buka `http://localhost:4321`.

Kalau port `4321` sedang dipakai, Astro otomatis pindah ke port berikutnya
dan menuliskannya di log.

## Catatan penting

- Item pendek.
- Item yang jauh lebih panjang, supaya terlihat bagaimana baris kedua
  membungkus dan apakah teksnya tetap rata di bawah dirinya sendiri, bukan
  menyelip ke bawah bullet.
  - Sub-item bersarang.
  - Sub-item kedua dengan `inline code` di tengah kalimat.
- Item terakhir.

> Blockquote dipakai untuk peringatan. Garis emas di kiri adalah satu-satunya
> aksen brand di dalam jawaban.

### Contoh konfigurasi

```bash
# .env
LITELLM_MODEL=gemini/gemini-3.6-flash
LLM_FAKE_MODE=true
```

```python
async def call_llm(state: AgentState) -> dict[str, Any]:
    return await _run_llm(state, offer_tools=True)
```

### Tabel perbandingan

| Mode | Panggil provider | Kuota terpakai | Dipakai untuk |
|---|---|---|---|
| Normal | Ya | 1 per giliran | Jawaban sungguhan |
| `LLM_FAKE_MODE` | Tidak | 0 | Kerja UI dan rendering |
| Eval | Ya | 1 per case | Regresi kualitas |

---

Teks penutup dengan **tebal**, `kode inline`, dan sebuah
[tautan biasa](https://docs.astro.build) di dalam kalimat. Baris ini juga
memuat URL yang sangat panjang tanpa spasi supaya pembungkusan kata bisa
diuji: https://ai.google.dev/gemini-api/docs/rate-limits#free-tier-quota-limits-per-model

Sources:
- https://ai.google.dev/gemini-api/docs/rate-limits
- https://docs.astro.build/en/guides/server-side-rendering/
- https://tailwindcss.com/docs/theme
