---
product_id: dash-admin-saas
product_name: DASH Admin SaaS (Assessment Hub — sisi Admin & Assessor)
status: active
---

# DASH Admin SaaS — Feature Context & Tutorial Document

Dokumen ini berisi rangkuman seluruh fitur di dalam **DASH Admin SaaS** (folder repo `ash-front-saas`, nama package `dash-admin-saas`) beserta panduan langkah demi langkah (SOP) cara menggunakannya. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, struktur, dan modul-modul aplikasi ini.

> **Ringkasan satu paragraf:** DASH Admin SaaS adalah aplikasi back office untuk menjalankan **assessment center**. Admin memakainya untuk menyiapkan perusahaan klien, proyek assessment, batch, dan peserta; **Assessor** memakainya untuk mengerjakan tugas penilaian (rating & interview) termasuk memantau peserta lewat proctoring; lalu keduanya menarik hasilnya sebagai laporan. Aplikasi ini adalah **pasangan admin** dari [[dash-participant-saas-doc-context]] — peserta mengerjakan simulasinya di sana, admin dan assessor mengelolanya di sini.

---

## Konsep Domain (baca ini dulu)

Hierarki datanya berlapis. Memahami urutan ini membuat seluruh menu masuk akal:

```
Client Company (perusahaan klien)
  └── Project (satu program assessment)
        └── Batch (satu gelombang pelaksanaan)
              └── Participant (peserta)
                    ├── ditugaskan ke → Assessor
                    ├── mengerjakan → simulasi (di aplikasi Participant)
                    └── dinilai lewat → Rating Task / Interview Task
                          └── menghasilkan → Reports
```

| Istilah | Arti |
|---|---|
| **Client Company** | Perusahaan klien yang pesertanya di-assess |
| **Project** | Satu program assessment milik sebuah client company |
| **Batch** | Gelombang pelaksanaan di dalam sebuah project (punya jadwal sendiri) |
| **Participant** | Peserta yang mengerjakan assessment |
| **Assessor** | Penilai yang ditugaskan ke peserta tertentu |
| **Rating Task** | Tugas menilai peserta berdasarkan kompetensi |
| **Interview Task** | Tugas wawancara peserta |
| **Proctoring** | Pemantauan peserta (rekaman/tayangan) saat mengerjakan |
| **Integration Grid** | Layar konsolidasi nilai lintas aktivitas menjadi nilai akhir kompetensi |
| **Competency** | Aspek yang dinilai pada peserta |

---

## Tech Stack & Cara Menjalankan

- **Framework:** React 18 + Vite (JavaScript/JSX)
- **Node:** 18.17.0
- **UI:** Ant Design v5 + Tailwind CSS + styled-components
- **State:** Redux Toolkit + React Redux
- **Routing:** React Router DOM v7
- **HTTP:** Axios lewat helper `API("<modul>.<aksi>")`
- **Video conference:** **Amazon Chime SDK** (`amazon-chime-sdk-js`, `amazon-chime-sdk-component-library-react`) — dipakai untuk interview & proctoring
- **Kalender:** `react-big-calendar` (Assessment Agenda)
- **Dokumen:** `react-pdf`, `file-saver` (unduh laporan)
- **Markdown:** `react-markdown` + `remark-gfm` (dipakai Chat ACE)
- **Rich text:** CKEditor 5
- **Drag & drop:** `@dnd-kit`
- **Analytics:** Google Tag Manager (`react-gtm-module`)
- **Enkripsi:** `aes-js` untuk data user di storage
- **Env config:** `env-cmd` dengan file `.env-cmdrc`

### Menjalankan di lokal

Aplikasi ini **memerlukan entri hosts**, tidak bisa langsung diakses lewat `localhost`:

1. Gunakan Node 18.17.0.
2. `npm i`
3. Tambahkan baris berikut ke file `hosts` sistem operasi:
   ```
   127.0.0.1 adminlocal.ddiassessment.com
   ```
4. `npm run dev`
5. Akses lewat `adminlocal.ddiassessment.com` pada port `3000`.

Script lain: `npm run build:dev`, `build:staging`, `build:prod`, `npm run lint`.

### Environment

| Environment | `VITE_APP_API_URL` |
|---|---|
| `local` / `development` | `https://service-dash.dlabssaas.io` |
| `production` | `https://intacbpjs-service-dash.odyssey.co.id` |

Variabel lain: `VITE_APP_HOST` (`adminlocal.ddiassessment.com`), `VITE_APP_GTM_ID`, `VITE_APP_SITE_KEY`, `VITE_APP_BASE_SERVICE_REPORT_DASHBOARD_URL` (`https://service-report-dashboard.acelents.com`), `VITE_APP_ENV_METABASE` (endpoint dashboard Metabase yang di-embed).

---

## Alur Kerja Utama (Golden Path)

```
1. Daftarkan perusahaan klien   → Manage Company / Client Company List
2. Buat proyek assessment       → Project List
3. Buat batch                   → Project > Batch
4. Tambahkan peserta            → Batch > Participant
5. Tugaskan assessor            → Participant > Assign Assessor
6. Peserta mengerjakan          → (di aplikasi DASH Participant)
7. Assessor menilai             → Rating Task / Interview Task
8. Konsolidasi nilai            → Evaluation Form > Integration Grid
9. Tarik hasil                  → Reports
```

---

## 1. Authentication (Otentikasi)

- **Path/Route:** `/auth/login`, `/auth/forgot-password`, `/auth/create-password`, `/auth/logout`, `/auth/not-found-404`
- **Tujuan:** Login admin dan assessor, pemulihan password, serta pembuatan password awal.

- **SOP Login:**
  1. Buka `/auth/login`.
  2. Masukkan Email dan Password, klik Login.
  3. Setelah berhasil, sistem mengarahkan ke `/dashboard`.

- **SOP Lupa Password:**
  1. Klik **Forgot Password** di halaman login.
  2. Masukkan email terdaftar, kirim.
  3. Buka email, ikuti link menuju `/auth/create-password` untuk menyetel password baru.

- **SOP Ganti Password:** buka `/change-password`, isi password lama & baru, simpan.

---

## 2. Dashboard

- **Path/Route:** `/dashboard`
- **Tujuan:** Halaman ringkasan setelah login — status proyek dan aktivitas assessment yang sedang berjalan.
- **Sumber kode:** `src/pages/dashboard/`

---

## 3. Manage Project (Proyek, Batch, Peserta)

Ini modul inti operasional. Ada **dua jalur masuk** menuju struktur yang sama:

- **Jalur A — Project List** (`/project-list`): langsung ke daftar proyek.
- **Jalur B — Client Company List** (`/client-company-list`): mulai dari perusahaan klien lalu masuk ke proyeknya.

**Route Jalur A (`/project-list`):**

| Route | Fungsi |
|---|---|
| `/project-list` | Daftar proyek |
| `/project-list/add` | Tambah proyek |
| `/project-list/edit/:projectId` | Edit proyek |
| `/project-list/:projectId/batch` | Daftar batch dalam proyek |
| `/project-list/:projectId/batch/add` | Tambah batch |
| `/project-list/:projectId/batch/:batchId/edit` | Edit batch |
| `/project-list/:projectId/batch/:batchId/participant` | Daftar peserta dalam batch |
| `/project-list/:projectId/batch/:batchId/participant/:participantId` | Detail peserta |
| `.../participant/:participantId/assignAssessor` | Tugaskan assessor ke peserta |
| `.../participant/:participantId/view-proctor/:role` | Lihat rekaman/tayangan proctoring |

**Route Jalur B (`/client-company-list`):** struktur identik, hanya diawali `:companyId` —
`/client-company-list/:companyId/project`, `.../project/add`, `.../project/:projectId/batch`, dan seterusnya sampai `view-proctor/:role`.

- **SOP Membuat Proyek Assessment Lengkap:**
  1. Buka **Project List**, klik **Add**. Isi nama proyek, klien terkait, dan periodenya. Simpan.
  2. Buka proyek → **Batch** → **Add**. Isi nama batch dan jadwal pelaksanaannya. Simpan.
  3. Buka batch → **Participant**. Tambahkan peserta ke batch tersebut.
  4. Pada peserta, jalankan **Assign Assessor** untuk menentukan penilainya.
  5. Kirim undangan ke peserta. Lewat undangan itulah peserta memperoleh akses ke aplikasi DASH Participant.

- **SOP Memantau Peserta (Proctoring):**
  1. Buka batch → **Participant** → pilih peserta.
  2. Buka **View Proctor** (`view-proctor/:role`).
  3. Sistem menampilkan tayangan/rekaman pemantauan peserta melalui Amazon Chime SDK.

---

## 4. Task List (Pekerjaan Assessor)

Menu ini adalah ruang kerja **assessor**, bukan admin.

### A. Rating Task

- **Path/Route dasar:** `/rating-task`
- **Sumber kode:** `src/pages/task-list/rating-task/`

| Route | Fungsi |
|---|---|
| `/rating-task` | Daftar tugas penilaian |
| `/rating-task/:participantId/evaluation-form` | Formulir evaluasi peserta |
| `/rating-task/:participantId/view-proctor/:role` | Tayangan proctoring peserta |
| `.../evaluation-form/:logPostId/competencies-list` | Daftar kompetensi yang dinilai |
| `.../competencies-list/:competencyId/rating-form-activity` | Formulir penilaian per aktivitas |
| `.../competencies-list/integration-grid` | Grid konsolidasi nilai |
| `.../competencies-list/:competencyId/integration-grid/:specFinalId/final` | Penetapan nilai akhir |

- **SOP Menilai Seorang Peserta:**
  1. Buka **Rating Task**. Daftar peserta yang ditugaskan kepadamu akan tampil.
  2. Klik peserta → **Evaluation Form**.
  3. Buka **Competencies List** untuk melihat kompetensi apa saja yang harus dinilai.
  4. Untuk tiap kompetensi, buka **Rating Form Activity** dan berikan penilaian per aktivitas.
  5. Setelah seluruh aktivitas dinilai, buka **Integration Grid** — layar ini mengonsolidasikan nilai lintas aktivitas.
  6. Tetapkan nilai akhir kompetensi lewat layar **Final**.
  7. Kalau perlu memeriksa perilaku peserta saat mengerjakan, buka **View Proctor**.

### B. Interview Task

- **Path/Route:** `/interview-task`, `/interview-task/:participantUrlId`
- **SOP:**
  1. Buka **Interview Task**, pilih peserta.
  2. Sesi wawancara berjalan lewat Amazon Chime SDK.
  3. Isi catatan/penilaian wawancara, lalu simpan.

### C. History

- **Path/Route:**
  - `/h-rating-task`, `/h-rating-task/:participantId/history-evaluation-form`, `/h-rating-task/:participantId/history-view-proctor/:role`
  - `/h-interview-task`
- **Tujuan:** Melihat kembali tugas yang sudah selesai beserta formulir dan rekaman proctoring-nya. Bersifat **baca saja**.

---

## 5. Assessment Program & Agenda

- **Path/Route:** `/assessment-agenda`
- **Tujuan:** Melihat jadwal pelaksanaan assessment dalam tampilan kalender.
- **Sumber kode:** `src/pages/assessment-program/assessment-agenda/` (memakai `react-big-calendar`)

- **SOP:** buka **Assessment Agenda**, pilih tampilan kalender (bulan/minggu/hari), klik agenda untuk melihat detail batch terkait.

---

## 6. Reports (Laporan)

- **Path/Route dasar:** `/reports/assessments/...`
- **Sumber kode:** `src/pages/reports/assessments/`

| Jenis laporan | Route |
|---|---|
| Individual Report PDF | `/reports/assessments/individual-report-pdf` |
| Individual Report ZIP | `/reports/assessments/individual-report-zip` |
| XLS Participant Group Report | `/reports/assessments/xls-participant-group-report` |
| XLS Group Report | `/reports/assessments/xls-group-report` |
| Integration Grid Report | `/reports/assessments/integration-grid-report` |
| Feedback Report | `/reports/assessments/feedback-report` |
| Participant Status Monitoring | `/reports/assessments/participant-status-monitoring` |

- **SOP Mengunduh Laporan:**
  1. Buka menu **Reports**, pilih jenis laporan yang dibutuhkan.
  2. Tentukan filter (proyek, batch, peserta) sesuai kebutuhan.
  3. Jalankan generate, lalu unduh hasilnya (PDF/ZIP/XLS, ditangani `file-saver`).

- **Kapan memakai yang mana:**
  - **Individual PDF** — hasil satu peserta.
  - **Individual ZIP** — banyak laporan individual sekaligus dalam satu arsip.
  - **XLS Group / Participant Group** — data tabular untuk diolah lebih lanjut.
  - **Integration Grid Report** — nilai kompetensi hasil konsolidasi.
  - **Feedback Report** — umpan balik peserta.
  - **Participant Status Monitoring** — pemantauan progres pengerjaan, bukan hasil penilaian.

---

## 7. Explore & Insights (Analitik)

### A. Explore + Nine Box Grid

- **Path/Route:** `/analytics/ex` (Explore), `/analytics/ex/nine-grid-box` (9-Box Grid)
- **Sumber kode:** `src/pages/explore/`, `src/pages/explore/nine-box-grid/`
- **SOP:**
  1. Buka **Explore**.
  2. Masuk ke **Nine Grid Box** untuk memetakan peserta pada matriks 3×3.
  3. Gunakan **Filter Modal** untuk mempersempit populasi yang ditampilkan.
  4. Klik sebuah kotak untuk melihat kartu peserta di dalamnya.

### B. Insights (Metabase)

- **Path/Route:** `/analytics/:metabaseId`
- **Tujuan:** Menyematkan dashboard Metabase ke dalam aplikasi.
- **Catatan:** Membuka `/analytics` tanpa `:metabaseId` akan diarahkan ke halaman 404 — dashboard hanya bisa diakses lewat id spesifik. URL embed berasal dari `VITE_APP_ENV_METABASE`.

---

## 8. Chat ACE (Asisten AI)

- **Path/Route:** `/chat-ace`
- **Sumber kode:** `src/pages/chat-ace/index.jsx`, komponen `AiBubble` & `HumanBubble`
- **Tujuan:** Antarmuka percakapan untuk bertanya tentang data organisasi dengan bahasa natural.

**Karakteristik implementasi:**
- Percakapan berbasis **`threadId`**, sehingga konteks tetap terjaga antar-pesan.
- Jawaban dirender sebagai **Markdown** (`react-markdown` + `remark-gfm`).
- **Pertanyaan rekomendasi berbeda-beda tergantung `roleId` user** — tersedia beberapa set, misalnya set HR ("Berapa budget rekrutmen tahun 2023?"), set pendidikan ("Berapa jumlah siswa aktif yang ada di sekolah kami?"), dan set keuangan ("Apa beban biaya yang paling besar?").

- **SOP:** buka **Chat ACE**, klik salah satu pertanyaan rekomendasi atau ketik pertanyaan sendiri, lalu kirim.

---

## 9. Master Data & Manage

Seluruh modul berikut ada di `src/pages/manage/` dan mengikuti pola CRUD standar.

| Modul | Route | Add | Edit / lainnya |
|---|---|---|---|
| Manage Company | `/manage-company` | `/add` | `/edit/:companyId`, `/manage-admin-client/:companyId`, `/manage-assessment-design/:companyId`, `/manage-subscription/:companyId` |
| Manage Employee | `/manage-employee` | `/add` | `/edit/:employeeId`, `/detail/:employeeId` |
| Manage Assessor | `/manage-assessor` | — | — |
| Manage Industry | `/manage-industry` | `/add` | `/edit/:id` |
| Manage Division | `/manage-division` | `/add` | `/edit/:divisionId` |
| Manage Position | `/manage-position` | `/add` | `/edit/:positionId`, `/set-competency/:positionId` |
| Manage Role | `/manage-role` | `/add` | `/edit/:roleId`, `/setting-menu-access/:roleId` |
| Manage User Role | `/manage-user-role` | `/add` | — |
| Manage Menu | `/manage-menu` | `/add` | `/edit/:id` |

- **SOP Menetapkan Kompetensi pada Sebuah Posisi:**
  1. Buka **Manage Position**, pilih posisi.
  2. Buka **Set Competency** (`/manage-position/set-competency/:positionId`).
  3. Pilih kompetensi yang berlaku untuk posisi tersebut, simpan. Kompetensi inilah yang nanti muncul di formulir penilaian assessor.

- **SOP Mengatur Hak Akses Menu:**
  1. Buat menu di **Manage Menu**.
  2. Buka **Manage Role → Setting Menu Access** untuk role yang dituju.
  3. Centang menu yang boleh diakses, simpan.

- **SOP Mengatur Assessment Design sebuah Company:**
  1. Buka **Manage Company** → aksi **Manage Assessment Design** (`/manage-company/manage-assessment-design/:companyId`).
  2. Susun rancangan assessment untuk company tersebut, simpan.

---

## 10. Application Settings

| Modul | Route | Add | Edit |
|---|---|---|---|
| Email Template | `/email-template` | `/add` | `/edit/:id`, `/detail/:id` |
| FAQ | `/faq` | `/add` | `/edit/:faqId` |
| Privacy Policy | `/privacy-policy` | `/add` | `/edit/:id` |
| Terms & Conditions | `/tnc` | `/add` | `/edit/:tncTemplateId` |

Isi diedit lewat CKEditor 5. Halaman `/maintenance` ditampilkan saat aplikasi sedang dalam masa pemeliharaan.

---

## Catatan Penting untuk Developer & Support

1. **Wajib lewat hosts entry.** Tanpa `127.0.0.1 adminlocal.ddiassessment.com`, dev server tidak bisa dipakai sebagaimana mestinya.
2. **Dua jalur menuju proyek** (`/project-list` dan `/client-company-list/:companyId/project`) menampilkan data yang sama — jangan bingung menganggapnya dua modul berbeda.
3. **Amazon Chime SDK** menangani interview dan proctoring. Masalah kamera/mikrofon hampir selalu berasal dari izin browser atau perangkat, bukan dari aplikasi.
4. **Insights butuh `:metabaseId`.** Membuka `/analytics` polos memang dirancang untuk redirect ke 404.
5. **Route Explore agak menjebak:** base path-nya `analytics/ex`, sehingga 9-box grid berada di `/analytics/ex/nine-grid-box`.
6. **Aplikasi ini berpasangan** dengan DASH Participant — peserta yang ditambahkan di sini akan login di aplikasi peserta. Lihat [[dash-participant-saas-doc-context]].
