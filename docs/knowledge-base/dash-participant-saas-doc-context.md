---
product_id: dash-participant-saas
product_name: DASH Participant SaaS (Assessment Hub — sisi Peserta)
status: active
---

# DASH Participant SaaS — Feature Context & Tutorial Document

Dokumen ini berisi rangkuman seluruh fitur di dalam **DASH Participant SaaS** (folder repo `assessment-hub-participant-saas`, nama package `dash-participant`) beserta panduan langkah demi langkah (SOP) cara menggunakannya. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, struktur, dan modul-modul aplikasi ini.

> **Ringkasan satu paragraf:** DASH Participant adalah aplikasi yang dipakai **peserta** untuk mengerjakan assessment. Peserta login memakai undangan yang dikirim admin, melewati pemeriksaan kompatibilitas perangkat, lalu mengerjakan rangkaian aktivitas — membaca materi, mengisi jawaban, wawancara mandiri via rekaman, sampai video call dengan assessor — semuanya dalam pengawasan (proctoring) dan batas waktu. Ini adalah **pasangan peserta** dari [[dash-admin-saas-doc-context]].

> [!IMPORTANT]
> Jangan tertukar dengan **New Assessment Center Participant** ([[new-assessment-center-participant-doc-context]]). Keduanya sama-sama aplikasi peserta, tetapi produk yang berbeda: yang itu memakai **LiveKit + Socket.IO + TipTap** dengan API `service.aca.*`, sedangkan yang ini memakai **Amazon Chime SDK + i18next** dengan API `service-dash.*`.

---

## Tech Stack & Cara Menjalankan

- **Framework:** React + Vite (JavaScript/JSX)
- **UI:** Ant Design v5 + styled-components + styled-system
- **State:** Redux Toolkit (`src/redux/slices`) + Redux klasik
- **Routing:** React Router DOM v7
- **HTTP:** Axios lewat wrapper di `src/services/axios`
- **Video & audio:** **Amazon Chime SDK** (`amazon-chime-sdk-js`, `amazon-chime-sdk-component-library-react`)
- **Multi-bahasa:** **i18next** + `react-i18next` + `i18next-browser-languagedetector` + `i18next-http-backend` — bahasa terdeteksi otomatis dari browser dan file terjemahan dimuat lewat HTTP
- **Timer:** `worker-timers` — timer berbasis Web Worker supaya hitungan mundur **tetap akurat meskipun tab tidak aktif**; ini krusial untuk assessment berbatas waktu
- **Dokumen:** `react-pdf` (materi berbentuk PDF)
- **Rich text:** CKEditor 5 (jawaban esai)
- **Cek koneksi:** `ping.js` (indikator kualitas jaringan)
- **Analytics:** Google Tag Manager, Google Analytics 4 (`react-ga4`), Microsoft Clarity
- **Enkripsi:** `aes-js`; storage lewat `store` + `js-cookie`
- **Env config:** `env-cmd` dengan file `.env-cmdrc`

### Menjalankan di lokal

```
npm i
npm run dev        # env-cmd -e local vite
```

Script lain: `npm run build:dev`, `build:staging`, `build:prod`, `npm run lint`.

### Environment

| Environment | `VITE_APP_API_URL` |
|---|---|
| `local` / `development` | `https://service-dash.dlabssaas.io` |
| `production` | `https://intacbpjs-service-dash.odyssey.co.id` |

Backend-nya **sama persis** dengan DASH Admin SaaS. Variabel lain: `VITE_APP_GTM_ID`, `VITE_APP_GA`, `VITE_CLARITY_KEY`.

---

## Alur Peserta (Golden Path)

```
Undangan email dari admin
   ↓
Login (/auth/login)
   ↓
Compatibility Check — cek kamera, mikrofon, jaringan
   ↓
Welcome — instruksi & persetujuan NDA
   ↓
Pre/Post Assessment (kuesioner sebelum & sesudah, jika ada)
   ↓
Assessment — rangkaian aktivitas dengan timer & proctoring
   ↓
Assessment Finish
```

Kalau peserta membuka aplikasi di luar jadwal batch, ia diarahkan ke **Batch Not Started** atau **Batch End**, bukan ke halaman assessment.

---

## Peta Route Lengkap

Sumber: `src/router/router.jsx`.

| Route | Halaman | Keterangan |
|---|---|---|
| `/` | Welcome | Halaman pembuka |
| `/auth/login` | Login | Masuk sebagai peserta |
| `/auth/forgot-password` | Forgot Password | Permintaan reset password |
| `/auth/reset-password` | Reset Password | Menyetel password baru |
| `/auth/logout` | — | Redirect ke `/auth/login` |
| `/auth/maintenance` | System Maintenance | Saat sistem dalam pemeliharaan |
| `/auth/not-found-404` | 404 | Halaman tidak ditemukan |
| `/public/compatibility-check` | Compatibility Check | Cek perangkat **tanpa perlu login** |
| `/private/compatibility-check` | Compatibility Check | Cek perangkat setelah login |
| `/manage-profile` | Manage Profile | Profil peserta |
| `/pre-post-assessment` | Pre/Post Assessment | Kuesioner sebelum/sesudah |
| `/pre-post-assessment/activity` | Activity | Aktivitas dalam kuesioner |
| `/assessment` | Assessment | Layar utama pengerjaan |
| `/preview/:token` | Assessment (mode preview) | Pratinjau assessment lewat token |
| `/assessment-finish` | Assessment Finish | Layar selesai |
| `/batch-not-started` | Batch Not Started | Batch belum dimulai |
| `/batch-end` | Batch End | Batch sudah berakhir |
| `/faq` | FAQ | Pertanyaan umum |
| `/privacy` | Privacy | Kebijakan privasi |
| `/terms-and-conditions` | Terms & Conditions | Syarat & ketentuan |
| `*` | — | Redirect ke 404 |

**Layout yang dipakai** (`src/layouts/`): `Auth`, `Main`, `AssessmentLayout`, `PrePostAssessmentLayout`, `FactsheetLayout`.

---

## 1. Authentication (Otentikasi)

- **Path/Route:** `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`
- **Tujuan:** Peserta masuk memakai kredensial dari undangan admin.

- **SOP Login:**
  1. Buka link dari email undangan, atau akses `/auth/login`.
  2. Masukkan email dan password dari undangan.
  3. Setelah berhasil, sistem mengarahkan sesuai kondisi batch: ke Welcome/Assessment bila sedang berjalan, atau ke Batch Not Started / Batch End bila di luar jadwal.

- **SOP Lupa Password:** klik **Forgot Password** → masukkan email → buka email → setel password baru di `/auth/reset-password`.

---

## 2. Compatibility Check (Pemeriksaan Perangkat)

- **Path/Route:** `/public/compatibility-check` (tanpa login), `/private/compatibility-check` (setelah login)
- **Tujuan:** Memastikan perangkat peserta siap sebelum assessment dimulai.
- **Sumber kode:** `src/pages/compatibility-check/`, `src/components/CompabilityCheck/`, `src/components/__Shared/DevicePermissionPropmpt/`, `.../DeviceSelection/`, `.../MicrophoneActivityBar/`, `.../NetworkIndicator/`

- **SOP:**
  1. Buka halaman compatibility check.
  2. Berikan izin kamera dan mikrofon saat browser meminta.
  3. Pilih perangkat kamera/mikrofon yang akan dipakai lewat **Device Selection**.
  4. Periksa **Microphone Activity Bar** — bar harus bergerak saat kamu berbicara.
  5. Periksa **Network Indicator** untuk memastikan koneksi memadai.
  6. Lanjutkan bila seluruh pemeriksaan lolos.

> [!TIP]
> Versi `/public/...` sengaja dibuat agar peserta bisa menguji perangkatnya **jauh sebelum hari pelaksanaan**, tanpa harus login lebih dulu. Sarankan ini ke peserta yang ragu soal kesiapan perangkatnya.

---

## 3. Welcome & Persetujuan

- **Path/Route:** `/`
- **Sumber kode:** `src/pages/welcome/`, `src/components/Welcome/`, `src/components/__Shared/NdaAgreement/`, `.../CookieConsent/`
- **SOP:**
  1. Baca instruksi pelaksanaan pada halaman Welcome.
  2. Setujui **NDA Agreement** bila diminta — tanpa ini assessment tidak bisa dimulai.
  3. Setujui **Cookie Consent**.
  4. Lanjutkan ke assessment.

---

## 4. Assessment (Layar Pengerjaan Utama)

- **Path/Route:** `/assessment`
- **Sumber kode:** `src/pages/assessment/`, `src/components/Assessment/`, `src/layouts/AssessmentLayout/`

**Jenis aktivitas yang didukung** (satu komponen per jenis, di `src/components/Assessment/`):

| Aktivitas | Isi |
|---|---|
| **Welcome** | Pengantar sebelum sebuah aktivitas dimulai |
| **Contents** | Materi bacaan/dokumen yang harus dipelajari peserta |
| **ActivityDefault** | Aktivitas standar berupa pertanyaan dan jawaban |
| **SelfInterview** | Wawancara mandiri — peserta merekam jawabannya sendiri |
| **VideoCall** | Sesi tatap muka dengan assessor via Amazon Chime |
| **VisionSpeech** | Aktivitas berbasis penglihatan/ucapan |
| **ExternalLink** | Mengarahkan peserta ke alat/sistem di luar aplikasi |
| **Cap** | Aktivitas bertipe cap |
| **Break** | Jeda istirahat terjadwal di antara aktivitas |
| **Feedback** | Umpan balik peserta atas pelaksanaan |

**Komponen pendukung selama pengerjaan** (`src/components/__Shared/`):

| Komponen | Fungsi |
|---|---|
| `Proctoring` | Merekam/memantau peserta selama mengerjakan |
| `MeetingControl`, `EndMeetingControl` | Kontrol sesi video (mute, kamera, akhiri) |
| `AlertSkipChime` | Peringatan saat sesi video dilewati |
| `LostFocus` | Mendeteksi peserta berpindah dari tab/jendela assessment |
| `DuplicateTab` | Mencegah assessment dibuka di lebih dari satu tab |
| `Disconnected` | Penanganan saat koneksi terputus |
| `NetworkIndicator` | Indikator kualitas jaringan berjalan |
| `RTEForm`, `EditorForm` | Formulir jawaban berbasis rich text |
| `ButtonNavigation` | Navigasi antar aktivitas |
| `CardNotif` | Notifikasi dalam layar |

- **SOP Mengerjakan Assessment:**
  1. Setelah Welcome, sistem menampilkan aktivitas pertama.
  2. Kerjakan sesuai jenisnya — baca materi, isi jawaban, rekam wawancara, atau ikuti video call.
  3. Perhatikan **timer**. Timer berjalan di Web Worker, jadi tetap menghitung walau tab tidak sedang dibuka.
  4. Gunakan tombol navigasi untuk lanjut ke aktivitas berikutnya.
  5. Ikuti jeda **Break** bila muncul di rangkaian.
  6. Setelah seluruh aktivitas selesai, peserta diarahkan ke `/assessment-finish`.

> [!WARNING]
> Selama pengerjaan berlaku beberapa pembatasan: berpindah tab terdeteksi oleh `LostFocus`, membuka assessment di tab kedua diblokir oleh `DuplicateTab`, dan proctoring berjalan di latar belakang. Sampaikan hal ini ke peserta di awal agar tidak panik saat peringatan muncul.

- **Mode Preview:** `/preview/:token` membuka layar assessment yang sama memakai token pratinjau — berguna bagi admin yang ingin memeriksa susunan assessment tanpa mengerjakannya sebagai peserta sungguhan.

---

## 5. Pre/Post Assessment

- **Path/Route:** `/pre-post-assessment`, `/pre-post-assessment/activity`
- **Sumber kode:** `src/pages/pre-post-assessment/`, `src/pages/activity/`, `src/services/prepost/`
- **Tujuan:** Kuesioner yang dikerjakan sebelum dan/atau sesudah assessment inti.
- **SOP:** buka halaman pre/post assessment → kerjakan tiap aktivitas → kirim.

---

## 6. Status Batch

| Halaman | Route | Muncul kapan |
|---|---|---|
| Batch Not Started | `/batch-not-started` | Peserta masuk sebelum jadwal batch dimulai |
| Batch End | `/batch-end` | Peserta masuk setelah batch berakhir |
| Assessment Finish | `/assessment-finish` | Seluruh aktivitas sudah diselesaikan |
| System Maintenance | `/auth/maintenance` | Sistem sedang dalam pemeliharaan (`AutoMaintenance`) |

> [!TIP]
> Keluhan "peserta tidak bisa masuk ke assessment" paling sering berujung pada jadwal batch, bukan kredensial. Cek dulu jadwal batch-nya di DASH Admin SaaS.

---

## 7. Manage Profile

- **Path/Route:** `/manage-profile`
- **Sumber kode:** `src/pages/manage-profile/`, `src/components/ManageProfile/`
- **SOP:** buka Manage Profile → perbarui data diri → simpan.

---

## 8. Halaman Informasi

| Halaman | Route |
|---|---|
| FAQ | `/faq` |
| Privacy Policy | `/privacy` |
| Terms & Conditions | `/terms-and-conditions` |

Isi halaman-halaman ini dikelola dari **DASH Admin SaaS** (menu Application Settings), bukan hardcoded di aplikasi peserta.

---

## Catatan Penting untuk Developer & Support

1. **Aplikasi ini berbagi backend dengan DASH Admin SaaS** (`service-dash.*`). Peserta yang ditambahkan admin di sanalah yang bisa login di sini.
2. **`worker-timers` dipakai dengan sengaja.** `setInterval` biasa akan di-throttle browser pada tab yang tidak aktif, yang berarti timer assessment jadi tidak akurat. Jangan menggantinya dengan timer biasa.
3. **i18next memuat terjemahan lewat HTTP** (`i18next-http-backend`), jadi teks yang tidak muncul bisa berarti file terjemahannya gagal dimuat, bukan salah kunci terjemahan.
4. **Compatibility check tersedia dalam versi publik**, dan itu memang disengaja untuk pengujian perangkat sebelum hari-H.
5. **Amazon Chime menangani seluruh media.** Masalah kamera/mikrofon hampir selalu berasal dari izin browser atau pilihan perangkat — arahkan peserta ke compatibility check lebih dulu.
6. **Jangan tertukar dengan New Assessment Center Participant** — beda stack, beda backend. Lihat [[new-assessment-center-participant-doc-context]].
