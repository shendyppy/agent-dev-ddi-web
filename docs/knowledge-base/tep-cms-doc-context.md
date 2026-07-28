---
product_id: tep-cms
product_name: TEP CMS (Acelents — Talent Excellence Platform)
status: active
---

# TEP CMS — Feature Context & Tutorial Document

Dokumen ini berisi rangkuman seluruh fitur di dalam **TEP CMS** (repo `tep-cms`, brand **Acelents**) beserta panduan langkah demi langkah (SOP) cara menggunakannya. Dokumen ini dirancang sebagai _context document_ untuk membantu agent AI memahami kapabilitas, struktur, dan modul-modul aplikasi ini.

> **Ringkasan satu paragraf:** TEP CMS adalah aplikasi admin (back office) untuk **Talent Excellence Platform**. Fungsinya: menyimpan data organisasi & karyawan sebuah perusahaan, mendefinisikan **profil kebutuhan setiap posisi (Position Profile)**, lalu membiarkan sistem **mencocokkan karyawan dengan posisi** untuk menghasilkan **Talent Pool** dan **Successor** — yaitu kandidat pengganti untuk posisi-posisi kunci. Hasilnya divisualisasikan sebagai **Succession Org Chart**, **9-Box Grid**, dan dashboard status suksesi. Aplikasi ini multi-tenant (banyak company) dan berbasis langganan (subscription).

---

## Cara Membaca Dokumen Ini

| Kalau kamu mau tahu… | Baca bagian… |
|---|---|
| Aplikasi ini sebenarnya untuk apa | [Konsep Domain](#konsep-domain-baca-ini-dulu) |
| Cara jalanin di lokal | [Tech Stack & Cara Menjalankan](#tech-stack--cara-menjalankan) |
| Alur kerja utama end-to-end | [Alur Kerja Utama](#alur-kerja-utama-golden-path) |
| Daftar semua halaman/route | [Peta Route Lengkap](#peta-route-lengkap) |
| SOP per fitur | Bagian bernomor 1–11 |

---

## Konsep Domain (baca ini dulu)

Tanpa memahami istilah di bawah, sebagian besar menu akan terasa acak. Enam istilah ini adalah inti produknya:

- **Company** — perusahaan klien (tenant). Semua data lain berada di bawah satu Company. Hampir seluruh endpoint membawa `:companyId`.
- **Employee** — karyawan di dalam Company. Punya data Personal, Employment, dan skor Capability.
- **Position** — jabatan/kursi di dalam organisasi. Position punya dua status: **Unpublished** (masih disusun) dan **Published** (sudah aktif dipakai untuk pencocokan).
- **Position Profile** — "spesifikasi" sebuah posisi: kriteria apa saja yang harus dipenuhi kandidat. Kriteria diambil dari tiga dimensi: **Personal**, **Employment**, dan **Capability**. Ini yang membuat sistem bisa mencocokkan orang ke posisi secara otomatis.
- **Talent Pool** — daftar karyawan yang **lolos kriteria** sebuah Position Profile. Dihasilkan sistem, bukan diinput manual.
- **Successor** — karyawan dari Talent Pool yang **dipilih admin** sebagai calon pengganti resmi untuk posisi tersebut.

**Relasi antar konsep:**

```
Company
  └── Employee ──(punya skor)──> Capability Data
  └── Position (Unpublished) ──publish──> Position (Published)
         └── Position Profile (kriteria Personal + Employment + Capability)
                └── kalkulasi sistem
                       └── Talent Pool (karyawan yang cocok)
                              └── Successor (dipilih admin dari Talent Pool)
                                     └── Status Suksesi posisi
```

### Status Suksesi (Succession Status)

Setiap posisi kunci punya salah satu dari 5 status. Ini muncul di org chart, dashboard, dan banner. Sumber: `src/constants/successionStatus.js`.

| Status | Artinya | Rekomendasi sistem |
|---|---|---|
| **Secured** (hijau) | Punya successor yang sudah siap | Pertahankan pengembangan successor agar tetap siap jangka panjang |
| **At Risk** (kuning) | Punya successor, tapi belum ada yang benar-benar siap | Berikan program pengembangan untuk successor terpilih |
| **Pending** (oranye) | Ada kandidat di talent pool, tapi belum ada yang dipilih jadi successor | Review kandidat, lalu pilih beberapa sebagai successor |
| **Exposed** (merah) | Tidak ada kandidat sama sekali di talent pool | Review position profile-nya, atau pertimbangkan rekrut dari luar |
| **Not Started** (abu-abu) | Posisi belum punya position profile | Lengkapi profil posisi supaya kandidat mulai muncul |

### Role & Hak Akses

Sumber: `src/constants/roles.js`.

| Role | ID | Karakteristik |
|---|---|---|
| **Administrator** | `1` | Admin sistem (pihak Odyssey/DLabs). **Dikecualikan dari pengecekan subscription.** Bisa kelola semua Company. |
| **Super Admin Client** | `2` | Admin tertinggi di sisi klien. Satu-satunya role yang boleh mengajukan perpanjangan langganan saat subscription tidak aktif. |
| **Admin Client** | `41` | Admin operasional klien. Cakupannya terbatas pada company-nya sendiri. |

Helper `isAdminClient()` mendeteksi role berdasarkan `roleName` yang mengandung `"Admin Client"`.

> [!IMPORTANT]
> **Menu sidebar bersifat dinamis, bukan hardcoded.** Struktur menu diambil dari API dan diatur lewat **Manage Menu**, lalu hak lihat per role diatur di **Manage Role → Setting Menu Access**. Jadi kalau sebuah menu tidak muncul untuk user tertentu, penyebabnya hampir selalu konfigurasi menu access — bukan bug routing.

---

## Tech Stack & Cara Menjalankan

- **Framework:** React 18 + Vite 6 (JavaScript/JSX, bukan TypeScript)
- **Node:** 18.17.0
- **UI:** Ant Design v5 + Tailwind CSS v3 + `@ant-design/icons` + `@heroicons/react`
- **State:** Redux Toolkit + React Redux
- **Routing:** React Router DOM v7 (`createBrowserRouter`)
- **HTTP:** Axios, dibungkus helper `API("<modul>.<aksi>")`
- **Realtime:** STOMP over SockJS (`@stomp/stompjs`, `sockjs-client`) — dipakai untuk notifikasi
- **Chart:** ECharts, `react-organizational-chart` (org chart), radar chart kustom
- **Rich text:** CKEditor 5
- **Drag & drop:** `@dnd-kit`
- **Enkripsi:** `aes-js` — dipakai untuk mengenkripsi `userData` sebelum disimpan
- **Storage:** `store` (localStorage wrapper) + `js-cookie`
- **Firebase:** push notification & analytics
- **Font:** Plus Jakarta Sans
- **Env config:** `env-cmd` dengan file `.env-cmdrc` (bukan `.env`)
- **Arsitektur komponen:** Atomic Design — `atoms` → `molecules` → `organism` → `templates` → `pages`

### Menjalankan di lokal

```
npm i
npm run dev        # env-cmd -e local vite
```

Script lain: `npm run dev:prod`, `npm run build:dev`, `npm run build:staging`, `npm run build:prod`, `npm run lint`.

### Environment

Dikonfigurasi di `.env-cmdrc`, dipilih lewat flag `-e <env>`.

| Environment | `VITE_APP_API_URL` | `VITE_APP_AI_API_URL` |
|---|---|---|
| `local` / `development` | `https://service-tep.dlabssaas.io` | `https://service-tep-ai.dlabssaas.io` |
| `production` | `https://service-tep.odyssey.co.id` | `https://service-tep-ai.dlabssaas.io` |

Port dev: `3000` (`VITE_APP_PORT`). Firebase project: `acelent-e55df`.

### Struktur Folder Penting

| Folder | Isi |
|---|---|
| `src/router/index.jsx` | Perakitan seluruh route |
| `src/router/routes.constants.js` | Konstanta base path (`ROUTE_PATHNAME`) |
| `src/router/routes/*.jsx` | Definisi child route per modul |
| `src/api/*.js` | Fungsi pemanggil API + notifikasi sukses/gagal |
| `src/services/axios/endpoints/*.js` | Registry URL + method tiap endpoint |
| `src/pages/**` | Halaman, dikelompokkan per domain |
| `src/pages/**/_components/` | Komponen khusus halaman tersebut |
| `src/constants/` | Konstanta domain (roles, status, brand) |
| `src/hooks/` | Hook lintas fitur (subscription, trusted browser, notifikasi) |

---

## Alur Kerja Utama (Golden Path)

Ini urutan yang membuat semua fitur "nyambung". Kalau ada pertanyaan "kenapa talent pool saya kosong?", jawabannya hampir selalu ada langkah di bawah yang terlewat.

```
1. Setup Company            → Manage Company
2. Setup struktur organisasi → Division, Department, Branch, Level, Job Family, Position
3. Input karyawan            → Manage Employee
4. Input data kapabilitas    → Manage Capability Data (upload/assessment)
5. Susun posisi              → Unpublished Position → isi data → Finalize → Publish
6. Definisikan kriteria      → Detail posisi > tab Position Profile → Set Criteria
7. Jalankan kalkulasi        → Start Now (langsung) atau Scheduler (terjadwal)
8. Sistem menghasilkan       → Detail posisi > tab Talent Pool
9. Admin memilih             → Detail posisi > tab Succession
10. Pantau                   → Succession Dashboard + Published Position > Organization View
```

> [!IMPORTANT]
> Langkah 6–9 semuanya terjadi **di dalam satu halaman**: detail posisi (`/published-position/detail/:id`), cukup berpindah tab. Ini titik yang paling sering bikin bingung — tidak ada menu terpisah untuk "position profile" atau "talent pool" di sidebar.

> [!TIP]
> **Troubleshooting cepat:** posisi berstatus **Not Started** artinya langkah 6 belum dilakukan. Berstatus **Exposed** artinya langkah 6 sudah, tapi tidak ada karyawan yang lolos kriteria — kriterianya mungkin terlalu ketat, atau data kapabilitas (langkah 4) belum masuk.

---

## 1. Authentication (Otentikasi)

- **Path/Route:** `/auth/login`, `/auth/forgot-password`, `/auth/create-password`, `/auth/logout`, `/auth/not-found-404`
- **Tujuan:** Menangani login, OTP, penandaan perangkat tepercaya, lupa password, dan pembuatan password.
- **API Terkait:** `auth.changePassword`, `auth.createPassword`
- **Komponen:** `src/pages/auth/login/_components/FormLogin/` — `index.jsx` (form email+password), `FormOTP.jsx`, `TrustedWeb.jsx`

Login TEP CMS **bertingkat tiga**, bukan sekadar email + password:

- **SOP Login:**
  1. Buka `/auth/login`. Root `/` otomatis redirect ke sini.
  2. Masukkan Email dan Password, klik Login.
  3. **Tahap OTP** — sistem menampilkan form OTP. Masukkan kode yang dikirim ke email/nomor terdaftar. Tersedia aksi *resend*.
  4. **Tahap Trusted Browser** — setelah OTP valid, muncul pilihan:
     - **Trust this browser** — browser ini disimpan sebagai tepercaya; login berikutnya dari browser yang sama bisa melewati OTP.
     - **Don't trust this browser** — ditandai untrusted; OTP akan diminta lagi lain kali.
     - **Skip for now** — tidak menyimpan keputusan apa pun.
  5. Setelah salah satu dipilih, `finalizeLogin()` dijalankan: token (`idToken`, `accessToken`, `refreshToken`) dan data user dienkripsi (AES) lalu disimpan, `activeRole` diisi dari `roleUsers[0]`.
  6. Sistem mengecek subscription (lihat bagian 11), lalu mengarahkan user ke Dashboard atau ke halaman blokir.

- **Catatan teknis Trusted Browser** (`src/hooks/useTrustedBrowser.js`, ref. tiket AC-1766):
  Status disimpan **per email** di `localStorage` dengan bentuk `{ email, status: "trusted" | "untrusted", savedAt }`. Karena berbasis localStorage, membersihkan browser data akan menghapus status ini dan OTP akan diminta lagi.

- **SOP Lupa Password:**
  1. Dari halaman login, klik **Forgot Password**.
  2. Masukkan email terdaftar, kirim.
  3. Buka email, ikuti link untuk membuat password baru di `/auth/create-password`.

- **SOP Ganti Password (sudah login):**
  1. Buka `/change-password`.
  2. Isi password lama dan password baru, simpan.

---

## 2. Talent Overview & Dashboard

- **Path/Route:** `/dashboard`, `/notification`, `/succession-dashboard`
- **Tujuan:** Halaman ringkasan setelah login, notifikasi, dan dashboard khusus kondisi suksesi organisasi.
- **Sumber kode:** `src/pages/talent-overview/dashboard`, `.../notification`, `.../succession`

- **SOP Melihat Ringkasan Suksesi:**
  1. Buka menu **Succession Dashboard** (`/succession-dashboard`).
  2. Sistem menampilkan kartu-kartu ringkasan:
     - **Key Position Status** — sebaran posisi kunci per status (Secured / At Risk / Pending / Exposed / Not Started).
     - **Secured Key Position** — daftar posisi yang sudah aman.
     - **Successor Talent Categorization** — sebaran kategori talenta para successor.
  3. Klik kartu/posisi untuk masuk ke detail posisi terkait.

- **SOP Melihat Notifikasi:**
  1. Buka `/notification` atau ikon lonceng di topbar.
  2. Notifikasi masuk **realtime via STOMP/SockJS** (`src/services/stomp`, `src/contexts/NotificationContext.jsx`), jadi tidak perlu refresh halaman.

---

## 3. Manage Company (Manajemen Perusahaan Klien)

- **Path/Route:** `/manage-company`, `/manage-company/add`, `/manage-company/detail/:id`, `/manage-company/edit/:id`, `/manage-company/manage-admin-client/:id`
- **Tujuan:** Mengelola perusahaan klien (tenant) beserta admin dan langganannya. Ini menu paling awal — tanpa Company, modul lain tidak punya konteks.
- **Sumber kode:** `src/pages/user-management/manage-company/`

- **SOP Menambah Company:**
  1. Buka **Manage Company**, klik **Add**.
  2. Isi data perusahaan (nama, industri, dan detail lain pada form).
  3. Simpan. Company baru muncul di tabel.

- **SOP Menambah Admin Client untuk sebuah Company:**
  1. Dari tabel Company, buka aksi **Manage Admin Client** (`/manage-company/manage-admin-client/:id`).
  2. Tambahkan user admin untuk company tersebut.
  3. Simpan. Admin ini nanti login dengan cakupan data company-nya sendiri.

### Sub-modul: Manage Subscription (dikelola dari sisi Company)

- **Path/Route:**
  - `/manage-company/manage-subscription/:companyId` — daftar langganan company
  - `.../add` — tambah paket langganan
  - `.../view/:subscriptionId` — lihat detail
  - `.../edit/:subscriptionId` — ubah
  - `.../extend/:subscriptionId` — perpanjang
  - `.../client-request/:requestId` — tinjau permintaan dari klien
  - `.../add-on-history/:planId` — riwayat add-on

- **SOP Memberikan/ Memperpanjang Langganan:**
  1. Buka Company terkait → **Manage Subscription**.
  2. Klik **Add** untuk paket baru, atau **Extend** pada paket yang ada untuk memperpanjang.
  3. Isi detail paket dan periode, simpan.
  4. Jika perpanjangan berasal dari permintaan klien, buka **Client Request** untuk meninjau dan memprosesnya.

---

## 4. Master Data Organisasi

Sekumpulan modul CRUD sederhana yang menjadi fondasi data. Semua mengikuti pola CRUD yang sama (lihat [Pola CRUD Standar](#pola-crud-standar)).

| Modul | Route dasar | Add | Edit | Gunanya |
|---|---|---|---|---|
| Manage Industry | `/manage-industry` | `/add` | `/edit/:id` | Klasifikasi industri perusahaan |
| Manage Division | `/manage-division` | `/add` | `/edit/:id` | Divisi dalam organisasi |
| Manage Department | `/manage-department` | `/add` | `/edit/:id` | Departemen di bawah divisi |
| Manage Branch | `/manage-branch` | `/add` | `/edit/:id` | Cabang/lokasi kerja |
| Manage Level | `/manage-level` | `/add` | `/edit/:id` | Jenjang/level jabatan |
| Manage Job Family | `/manage-job-family` | `/add` | `/edit/:id` | Rumpun jabatan |
| Manage Position | `/manage-position` | `/add` | `/edit/:id` | Master jabatan |
| Manage Talent Category | `/manage-talent-category` | `/add` | `/edit/:id` | Kategori talenta (dipakai 9-box) |
| Manage Tag | `/manage-tag` | `/add` | `/edit/:groupTagId`, `/detail/:id` | Penanda/label karyawan |
| Employment Setup | `/employment-setup` | — | — | Employment Type & Employment Status dalam satu halaman |

**Nilai bawaan Employment** (`src/constants/employmentStatus.js`):
- Status: `Active`, `Terminated by Cause`, `Voluntarily Terminated`
- Type: `Full Time`, `Part Time`, `Contract`

> [!NOTE]
> **Urutan input itu penting.** Position membutuhkan Division/Department/Level/Job Family. Employee membutuhkan Position. Jadi isi master data organisasi **sebelum** menambahkan karyawan, kalau tidak dropdown-nya akan kosong.

---

## 5. Manage Employee (Manajemen Karyawan)

- **Path/Route dasar:** `/manage-employee`
- **Tujuan:** Mengelola seluruh data karyawan — data pribadi, data kepegawaian, dan skor kapabilitas. Data inilah yang dicocokkan dengan Position Profile.
- **Sumber kode:** `src/pages/user-management/manage-employee/`

**Route lengkap modul ini:**

| Route | Fungsi |
|---|---|
| `/manage-employee` | Daftar karyawan |
| `/manage-employee/add` | Tambah karyawan |
| `/manage-employee/detail/:id` | Detail karyawan |
| `/manage-employee/edit/:id` | Edit karyawan |
| `/manage-employee/edit/:id/basic-information/:subDimensionId` | Edit informasi dasar |
| `/manage-employee/edit/:id/education/:subDimensionId` | Edit pendidikan |
| `/manage-employee/edit/:id/certification/:subDimensionId` | Edit sertifikasi |
| `/manage-employee/edit/:id/employment/:subDimensionId` | Edit data kepegawaian |
| `/manage-employee/edit/:id/performance/:subDimensionId` | Edit performa |
| `/manage-employee/edit/:id/experience/:subDimensionId` | Edit pengalaman kerja |
| `/manage-employee/edit/:id/:subDimension/:variableName/:dimensionId` | Edit variabel dinamis |
| `/manage-employee/add-score/:id` | Tambah skor kapabilitas |
| `/manage-employee/view-details-score/:id/:capVariableId` | Detail skor per variabel |
| `/manage-employee/development-guidelines/:id` | Panduan pengembangan karyawan |
| `/manage-employee/adjust-development-focus/:id` | Menyesuaikan fokus pengembangan |

- **SOP Menambah Karyawan:**
  1. Buka **Manage Employee**, klik **Add**.
  2. Isi data kepegawaian (company, division, department, position, level, employment type & status).
  3. Isi data pribadi (nama, kontak, pendidikan, dan seterusnya).
  4. Simpan.

- **SOP Melengkapi Data Karyawan (penting untuk pencocokan):**
  1. Buka **Detail** karyawan.
  2. Lengkapi tiap bagian lewat tombol edit masing-masing: Basic Information, Education, Certification, Employment Data, Performance, Work Experience.
  3. Bagian yang kosong berpotensi membuat karyawan **tidak lolos** kriteria Position Profile.

- **SOP Menambah Skor Kapabilitas Karyawan:**
  1. Dari detail karyawan, buka **Add Score** (`/manage-employee/add-score/:id`).
  2. Pilih variabel kapabilitas dan isi skornya.
  3. Simpan. Untuk memeriksa hasilnya, buka **View Details Score**.

- **SOP Melihat Development Guidelines:**
  1. Dari detail karyawan, buka **Development Guidelines** (`/manage-employee/development-guidelines/:id`).
  2. Untuk mengubah area yang jadi prioritas pengembangan, buka **Adjust Development Focus** (`/manage-employee/adjust-development-focus/:id`).

---

## 6. Capability & Sub Dimension (Kerangka Penilaian)

Modul ini mendefinisikan **apa saja yang diukur** dari seorang karyawan. Ada tiga dimensi: **Personal**, **Employment**, dan **Capability**.

### A. Manage Sub Dimension

- **Path/Route dasar:** `/manage-sub-dimension`

| Route | Fungsi |
|---|---|
| `/manage-sub-dimension/personal/add-sub-dimension` | Tambah sub-dimensi Personal |
| `/manage-sub-dimension/personal/edit-sub-dimension/:id` | Edit sub-dimensi Personal |
| `/manage-sub-dimension/employment/add-sub-dimension` | Tambah sub-dimensi Employment |
| `/manage-sub-dimension/employment/edit-sub-dimension/:id` | Edit sub-dimensi Employment |
| `/manage-sub-dimension/capability/add-sub-dimension` | Tambah sub-dimensi Capability |
| `/manage-sub-dimension/capability/edit-sub-dimension` | Edit sub-dimensi Capability |
| `/manage-sub-dimension/capability/:capabilityId/dashboard` | Dashboard sebuah kapabilitas |
| `/manage-sub-dimension/capability/:capabilityId/add-variable` | Tambah variabel kapabilitas |
| `/manage-sub-dimension/capability/:capabilityId/edit-variable/:capVariableId` | Edit variabel kapabilitas |

- **SOP Menambah Variabel Kapabilitas:**
  1. Buka **Manage Sub Dimension** → tab **Capability**.
  2. Pilih kapabilitas, buka **Dashboard**-nya.
  3. Klik **Add Variable**, isi definisi variabel, simpan.
  4. Variabel ini kemudian bisa dipakai sebagai kriteria di Position Profile dan sebagai kolom skor di Manage Employee.

### B. Manage Capability Data

- **Path/Route:** `/manage-capability-data`, `/manage-capability-data/:capabilityDataId/dashboard`
- **Tujuan:** Mengelola **sumber data** kapabilitas — termasuk unggah massal lewat template dan mengambil dari hasil assessment.
- **API Terkait:** `manageCapabilityData.getDataListCapabilityData`, `.createCapabilityData`, `.lookUpAssessmentCapabilityData`, `.deleteCapabilityData`, `.getUploadListCapabilityData`, `.downloadTemplate`

- **SOP Upload Data Kapabilitas Massal:**
  1. Buka **Manage Capability Data**.
  2. **Download Template** terlebih dahulu — jangan membuat format sendiri.
  3. Isi template dengan data skor karyawan.
  4. Unggah kembali file tersebut.
  5. Periksa hasilnya di daftar upload; buka **Dashboard** capability data untuk melihat ringkasannya.

- **SOP Mengambil Data dari Assessment:**
  1. Buka **Manage Capability Data** → **Add**.
  2. Pilih sumber assessment yang tersedia (lookup assessment).
  3. Simpan — skor dari assessment tersebut masuk sebagai capability data.

---

## 7. Position Management (Unpublished → Published)

Ini modul yang paling sering disalahpahami. Sebuah posisi harus melewati siklus **disusun → difinalisasi → dipublikasikan** sebelum bisa dipakai untuk suksesi.

### A. Unpublished Position (posisi yang masih disusun)

- **Path/Route:** `/unpublished-position`, `/add`, `/edit/:id`, `/detail/:id`, `/detail/:id/finalize-position`
- **Sumber kode:** `src/pages/positions/unpublished/`
- **API Terkait:** `unpublishedPosition.getDataList`, `.createData`, `.readDataById`

- **SOP Membuat dan Mempublikasikan Posisi:**
  1. Buka **Unpublished Position**, klik **Add**.
  2. Isi data posisi (nama, level, division/department, job family, atasan, dan seterusnya).
  3. Simpan. Posisi tersimpan dalam keadaan belum terbit.
  4. Buka **Detail** posisi tersebut, lalu masuk ke **Finalize Position** (`/detail/:id/finalize-position`).
  5. Periksa kembali seluruh data pada layar finalisasi.
  6. Konfirmasi publikasi lewat **Publish Confirmation Modal**.
  7. Posisi berpindah ke daftar **Published Position**.

### B. Published Position (posisi aktif)

- **Path/Route:** `/published-position/detail/:id`, `/published-position/organization-view`
- **Sumber kode:** `src/pages/positions/published/`

- **SOP Melihat Organization View (bagan suksesi):**
  1. Buka **Published Position** → **Organization View** (`/published-position/organization-view`).
  2. Bagan organisasi tampil sebagai kanvas yang bisa di-zoom dan digeser (`ZoomableCanvas` + `ZoomControls`).
  3. Setiap node posisi diwarnai sesuai **status suksesi** — lihat [tabel status](#status-suksesi-succession-status). Inilah tampilan utama untuk memantau kesehatan suksesi organisasi.
  4. **Data Banner** dan **Number Stats** di atas kanvas menampilkan ringkasan jumlah per status beserta tip tindakannya.
  5. Klik sebuah node untuk membuka **Position Detail Sheet** di samping.
  6. Tersedia juga **Classic View** berupa tabel (endpoint `getClassicViewList`) bagi yang lebih nyaman dengan daftar.

- **SOP Menganalisis Detail Posisi:**
  1. Buka **Detail** sebuah posisi (`/published-position/detail/:id` atau `/unpublished-position/detail/:id`).
  2. Halaman detail memakai komponen bersama `src/components/pages/DetailPosition.jsx` dengan **5 tab**:

     | Tab (`key`) | Isi |
     |---|---|
     | `employee` | Karyawan yang saat ini menempati posisi |
     | `subordinate` | Bawahan posisi tersebut, termasuk rasio performa (**hanya published position**) |
     | `positionProfile` | Kriteria pencocokan posisi — lihat [bagian 8](#8-position-profile-kriteria-pencocokan) |
     | `talentPool` | Kandidat hasil pencocokan sistem |
     | `succession` | Successor yang sudah dipilih |

  3. Tab aktif dapat dibuka langsung lewat query param, misalnya `?section=talentPool`.
  4. Tiap tab (selain Position Profile) punya beberapa mode tampilan: **tabel**, **talent box grid** (9-box), **capability comparison**, dan **performance comparison**.

> [!NOTE]
> Halaman detail unpublished dan published berbagi komponen yang sama, tetapi unpublished **tidak punya tab Subordinate** — hanya `employee`, `talentPool`, dan `succession` yang dipetakan ke API.

- **API Terkait (published position):**
  - Header & tabel: `publishedPosition.getDetailHeader`, `.getDetailTable`
  - 9-box: `.getTalentBoxGrid`, `.getTalentBoxGridEmployee`, `.getTalentBoxGridSubordinate`, `.getTalentBoxGridTalentPool`, `.getTalentBoxGridSuccession`
  - Perbandingan: `.getCapabilityComparison`, `.getPerformanceComparison` (tersedia varian Subordinate, TalentPool, Succession)
  - Talent Pool: `.getDetailTableTalentPool`, `.putAsSuccession`, `.putAsAnEmployeeOnTalentPool`, `.deleteTalentPool`, `.putIsNewTalentPool`
  - Succession: `.getDetailTableSuccession`, `.putAsAnEmployeeOnSuccession`
  - Lookup: `.getDataTalentCategoryLookup`, `.getDataTagsLookup`

- **SOP Mempromosikan Kandidat Jadi Successor:**
  1. Buka detail published position → tab **Talent Pool**.
  2. Bandingkan kandidat lewat 9-box grid, capability comparison, dan performance comparison.
  3. Pilih kandidat, jalankan aksi **Select as Succession** (memanggil `putAsSuccession`).
  4. Kandidat berpindah ke tab **Succession**, dan status suksesi posisi ikut berubah (misalnya dari **Pending** menjadi **At Risk** atau **Secured**).
  5. Untuk mengembalikan successor menjadi kandidat biasa, gunakan aksi *select as employee* pada tab Succession.

---

## 8. Position Profile (Kriteria Pencocokan)

Inilah "otak" pencocokan. Tanpa Position Profile, posisi berstatus **Not Started** dan talent pool-nya kosong.

- **Letak di UI:** tab **Position Profile** di dalam halaman detail posisi — `/published-position/detail/:id` atau `/unpublished-position/detail/:id`.
- **Sumber kode:** `src/components/organism/PositionProfile/`, `.../DimensionSettings/`, `.../HeaderPositionProfile/`, `.../TalentReadiness/`, dengan modal `ModalAddCriteria`, `ModalSetCriteria`, `ModalSetCriteriaFinal`
- **API Terkait (`positionProfile.*`):**
  - Lihat kriteria: `getDimentionList`, `getPersonalFilterList`, `getEmploymentFilterList`, `getCapabilityFilterList`
  - Tambah kriteria: `addCriteriaPersonal`, `addCriteriaEmployment`, `addCriteriaCapability`
  - Set kriteria: `getSetCriteriaNonCapability`, `postSetCriteriaNonCapability`, `getSetCriteriaCapability`, `postSetCriteriaCapability`
  - Finalisasi & kalkulasi: `getSetCriteriaFinal`, `postSetCriteriaFinalNow`, `postSetCriteriaFinalSystem`
  - Pemantauan: `getProgressCalculation`, `getValidationButtonSetCriteria`
  - Kriteria terhapus: `getRemovedCriteria`, `getRemovedCounterCriteria`

- **SOP Menyusun Position Profile:**
  1. Buka **Detail** posisi (`/published-position/detail/:id` atau `/unpublished-position/detail/:id`), lalu pilih tab **Position Profile**.
  2. Sistem menampilkan daftar dimensi yang tersedia (**Dimension Settings**).
  3. Tambahkan kriteria untuk tiap dimensi yang relevan lewat modal **Add Criteria**:
     - **Personal** — misalnya pendidikan, sertifikasi.
     - **Employment** — misalnya masa kerja, level, performa.
     - **Capability** — variabel kapabilitas beserta skor minimumnya.
  4. Untuk tiap kriteria, buka modal **Set Criteria** dan tentukan nilai/ambang batasnya.
  5. Sistem memvalidasi kelengkapan lewat `getValidationButtonSetCriteria` — tombol lanjut baru aktif bila kriteria sudah sah.
  6. Buka modal **Set Criteria Final** untuk meninjau seluruh kriteria.
  7. Jalankan kalkulasi dengan salah satu cara:
     - **Start Now** (`postSetCriteriaFinalNow`) — dijalankan langsung saat itu juga.
     - **Scheduler** (`postSetCriteriaFinalSystem`) — dijadwalkan oleh sistem.
  8. Pantau progres lewat `getProgressCalculation`. Setelah selesai, pindah ke tab **Talent Pool** pada halaman detail yang sama untuk melihat karyawan yang lolos.

> [!WARNING]
> Mengubah kriteria **tidak otomatis** memperbarui talent pool. Kalkulasi harus dijalankan ulang (Start Now atau Scheduler) setiap kali kriteria berubah.

---

## 9. Application Setting (Pengaturan Aplikasi)

Seluruh modul di bawah berada di `src/pages/application-setting/` dan mengikuti pola CRUD standar.

| Modul | Route | Add | Edit |
|---|---|---|---|
| Email Template | `/email-template` | `/add` | `/edit/:emailId` |
| Notification Template | `/notification-template` | `/add` | `/edit/:notifId` |
| Maintenance Schedule | `/maintenance-schedule` | `/add` | `/edit/:maintenanceScheduleId` |
| App Config | `/app-config` | `/add` | `/edit/:id` |
| Manage FAQ | `/manage-faq` | `/add` | `/edit/:id` |
| Manage TnC | `/manage-tnc` | `/add` | `/edit/:id` |
| Manage Privacy Policy | `/manage-privacy` | `/add` | `/edit/:id` |
| Manage NDA | `/manage-nda` | `/add` | `/edit/:id` |

> Perhatikan: route privacy policy adalah `/manage-privacy`, **bukan** `/manage-privacy-policy`.

- **SOP Mengedit Template Email/Notifikasi:**
  1. Buka **Email Template** atau **Notification Template**.
  2. Klik edit pada template yang dituju.
  3. Ubah isinya menggunakan editor (CKEditor 5). Variabel dinamis tetap dipertahankan.
  4. Simpan.

- **SOP Menjadwalkan Maintenance:**
  1. Buka **Maintenance Schedule** → **Add**.
  2. Tentukan waktu mulai dan selesai beserta pesannya.
  3. Simpan. Saat jadwal aktif, user diarahkan ke halaman `/maintenance` (ditangani komponen `AutoMaintenance` di layout).

- **SOP Mengubah Dokumen Legal (TnC / Privacy Policy / NDA / FAQ):**
  1. Buka menu yang sesuai.
  2. Edit isi lewat rich text editor.
  3. Simpan. Versi publiknya dapat diakses tanpa login di `/open/tnc`, `/open/privacy-policy`, `/open/faq`.

---

## 10. Subscription & Halaman Blokir

- **Path/Route (sisi klien):**
  - `/subscription` — ringkasan langganan
  - `/subscription/plan-details/:clientCompanyPartitionSubsId` — detail paket
  - `/subscription/service-request/add` — ajukan permintaan layanan
  - `/subscription/service-request/view-request/:subsReqId` — lihat status permintaan
- **Halaman blokir:** `/access-restricted`, `/expired`, `/subscription-inactive`
- **Sumber kode:** `src/hooks/useSubscription.js`, `src/pages/subscription/`, `src/pages/block-screen/`

**Cara kerja pengecekan langganan** (`useSubscription`):

1. Kalau role user adalah **Administrator** (`roleId === 1`), pengecekan **dilewati sepenuhnya** dan seluruh flag blokir dibersihkan.
2. Selain itu, sistem memanggil `checkSubscriptionPlan` dengan `companyId` user.
3. Langganan dianggap aktif bila `subscriptionStatus` bernilai `Active` **atau** `NO DATA`.
4. Kalau tidak aktif:
   - Bila user **Super Admin Client** dan company punya langganan tidak aktif tanpa langganan aktif → flag `subscriptionInactive` → user diarahkan ke `/subscription-inactive`, di mana ia **boleh mengajukan perpanjangan**.
   - Selain itu → flag `accessRestricted` → user diarahkan ke `/access-restricted` dan **tidak bisa** mengajukan apa pun.

> [!TIP]
> Ini penjelasan kenapa dua user dari company yang sama bisa melihat halaman blokir yang berbeda: hanya **Super Admin Client** yang mendapat jalur perpanjangan; role lain hanya melihat layar akses dibatasi.

- **SOP Mengajukan Perpanjangan Langganan (Super Admin Client):**
  1. Login. Bila langganan tidak aktif, sistem mengarahkan ke `/subscription-inactive`.
  2. Baca peringatan pada layar tersebut, lalu isi **Form Request Subscription**.
  3. Kirim. Flag `hasRequestedRenewPlan` menjadi aktif sehingga form tidak bisa dikirim berulang.
  4. Admin sistem meninjau permintaan tersebut dari **Manage Company → Manage Subscription → Client Request**.
  5. Setelah disetujui, muncul layar **Success Renew Subscription** dan akses kembali normal.

---

## 11. Administrasi Akses (Role, Menu, User Role)

| Modul | Route | Fungsi |
|---|---|---|
| Manage Role | `/manage-role`, `/add`, `/edit/:roleId`, `/setting-menu-access/:roleId` | Membuat role dan mengatur menu mana yang boleh diakses |
| Manage Menu | `/manage-menu`, `/add`, `/edit/:menuId` | Mendefinisikan struktur menu sidebar |
| Manage User Role | `/manage-user-role`, `/add` | Menetapkan role ke user |
| Manage Admin | `/manage-admin` | Mengelola akun admin |

- **SOP Menampilkan Menu Baru untuk Sebuah Role:**
  1. Buka **Manage Menu** → **Add**. Tentukan label, ikon, dan route tujuannya. Simpan.
  2. Buka **Manage Role** → pilih role → **Setting Menu Access** (`/manage-role/setting-menu-access/:roleId`).
  3. Centang menu yang baru dibuat untuk role tersebut. Simpan.
  4. User dengan role itu perlu login ulang (atau menyegarkan data menu) agar sidebar-nya ter-update.

- **SOP Mengubah Role Seorang User:**
  1. Buka **Manage User Role**.
  2. Cari user yang dituju, ubah role-nya.
  3. Simpan. Perubahan berlaku pada sesi login berikutnya.

---

## Peta Route Lengkap

Disusun dari `src/router/index.jsx` + `src/router/routes.constants.js` + `src/router/routes/*.jsx`.

| Base path | Modul |
|---|---|
| `/` | Redirect ke `/auth/login` |
| `/auth` | Login, logout, forgot-password, create-password, not-found-404 |
| `/open/faq`, `/open/privacy-policy`, `/open/tnc` | Halaman legal publik (tanpa login) |
| `/dashboard`, `/notification` | Talent Overview |
| `/succession-dashboard` | Dashboard suksesi |
| `/subscription` | Langganan sisi klien |
| `/access-restricted`, `/expired`, `/subscription-inactive` | Layar blokir |
| `/change-password` | Ganti password |
| `/manage-company` | Company + admin client + subscription |
| `/manage-employee` | Karyawan |
| `/manage-industry`, `/manage-division`, `/manage-department`, `/manage-branch`, `/manage-level`, `/manage-job-family`, `/manage-position`, `/manage-talent-category`, `/manage-tag` | Master data |
| `/employment-setup` | Employment type & status |
| `/manage-sub-dimension` | Personal / Employment / Capability |
| `/manage-capability-data` | Sumber data kapabilitas |
| `/unpublished-position`, `/published-position` | Siklus hidup posisi + position profile + talent pool + suksesi |
| `/manage-role`, `/manage-menu`, `/manage-user-role`, `/manage-admin` | Administrasi akses |
| `/email-template`, `/notification-template`, `/maintenance-schedule`, `/app-config`, `/manage-faq`, `/manage-tnc`, `/manage-privacy`, `/manage-nda` | Application setting |
| `/analytics/:metabaseId` | Dashboard Metabase yang di-embed |
| `/design-system/:componentId` | Katalog komponen internal |
| `/maintenance` | Halaman maintenance |
| `*` | 404 |

---

## Pola CRUD Standar

Sebagian besar modul di CMS ini memakai pola UI yang seragam. Memahami satu modul berarti memahami hampir semuanya.

- **Read** — halaman utama berupa tabel Ant Design dengan pencarian, filter, dan paginasi.
- **Create** — tombol **Add** di kanan atas tabel, membuka halaman `/add` tersendiri (bukan modal).
- **Update** — ikon edit di kolom Action paling kanan, menuju `/edit/:id`.
- **Delete** — ikon hapus di kolom Action, dengan modal konfirmasi.
- **Notifikasi** — sukses/gagal ditampilkan lewat `notification` Ant Design, diatur terpusat di `src/api/*.js` melalui `handleApiError`.

**Anatomi pemanggilan API:**

```js
// src/api/<modul>.js
const res = await API("manageCapabilityData.getDataListCapabilityData", {
  query: { companyId },   // mengisi placeholder :companyId di URL
  params: params,         // query string
  data: payload,          // request body
});
```

URL sebenarnya berada di `src/services/axios/endpoints/<modul>.js`. Jadi untuk melacak sebuah endpoint: **halaman → `src/api/<modul>.js` → `src/services/axios/endpoints/<modul>.js`**.

---

## Catatan Penting untuk Developer & Support

1. **Hampir semua endpoint memerlukan `companyId`.** Nilainya diambil dari `userData` terenkripsi di storage. Kalau sebuah halaman menampilkan data kosong, periksa dulu apakah `companyId` terisi pada sesi tersebut.
2. **`userData` dienkripsi AES** sebelum disimpan (lihat `finalizeLogin`), jadi isinya tidak bisa dibaca langsung dari localStorage — gunakan helper `decrypt`/`getUserData`.
3. **Status trusted browser bersifat per-email dan lokal.** Ganti browser atau bersihkan storage → OTP diminta lagi. Ini perilaku yang diharapkan, bukan bug.
4. **Menu tidak muncul ≠ route tidak ada.** Cek Setting Menu Access untuk role tersebut lebih dulu.
5. **Talent pool tidak terisi otomatis.** Butuh Position Profile lengkap **dan** kalkulasi yang dijalankan.
6. **Route legal ada dua bentuk:** publik (`/open/...`, tanpa login) dan admin (`/manage-...`, perlu login).
7. **Aplikasi mendukung multi-brand** (`src/constants/brands.js`) — logo dan latar login dapat menyesuaikan subdomain. Saat ini hanya brand default (Acelents) yang aktif; BPJS dan Alfamart masih dikomentari.

---

## Glosarium Singkat

| Istilah | Arti |
|---|---|
| **TEP** | Talent Excellence Platform |
| **Acelents** | Nama brand produk (logo `acelent-logo.svg`) |
| **Position Profile** | Kumpulan kriteria yang harus dipenuhi kandidat sebuah posisi |
| **Talent Pool** | Karyawan yang lolos kriteria sebuah posisi (dihasilkan sistem) |
| **Successor** | Kandidat yang dipilih admin sebagai calon pengganti |
| **9-Box / Talent Box Grid** | Matriks 3×3 pemetaan performa × potensi |
| **Sub Dimension** | Pengelompokan hal yang diukur, di bawah dimensi Personal/Employment/Capability |
| **Capability Variable** | Butir terukur di dalam sebuah kapabilitas |
| **Set Criteria** | Proses menetapkan nilai ambang tiap kriteria di Position Profile |
| **Finalize Position** | Langkah verifikasi sebelum sebuah posisi dipublikasikan |
