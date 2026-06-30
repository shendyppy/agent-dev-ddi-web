---
product_id: learninghub-cms
product_name: LearningHub CMS
status: active
---

# LearningHub CMS - Feature Context & Guide Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam sistem **LearningHub CMS** beserta panduan fungsional dan teknis alur kerjanya. Dokumen ini dirancang sebagai *context document* untuk membantu agent AI memahami kapabilitas, struktur navigasi, routing, serta modul-modul fungsional yang ada pada platform manajemen pembelajaran (Content Management System) LearningHub.

---

## Teknologi Utama & Arsitektur

- **Core Library:** React.js (v17.0.1) dengan React Router Dom (v5) untuk routing halaman.
- **Visual Builder Integration:** Menggunakan template dan framework `@vb` (Visual Builder React) untuk tata letak UI, sidebar, menu dynamic, dan otentikasi.
- **State Management:** Redux dengan Redux Saga (`src/redux/sagas.js` & `src/redux/reducers.js`). Konfigurasi store menggunakan `redux-persist` untuk menyimpan state `clientProject` di penyimpanan lokal agar tidak hilang saat reload.
- **UI Library:** Ant Design (antd v4) untuk komponen visual (tabel, input, tombol, modal, notifikasi) dikombinasikan dengan Bootstrap (v4.5.3) untuk layouting grid serta SCSS/Styled Components untuk styling kustom.
- **Rich Text Editor:** CKEditor 5 (`@ckeditor/ckeditor5-react` v4.0.0 & `@ckeditor/ckeditor5-build-classic` v38.0.1) untuk pengisian konten artikel dan deskripsi kaya format.
- **Media & Interactive Players:** Menggunakan `h5p-standalone` (v3.6.0) untuk rendering materi interaktif H5P, `scorm-again` (v2.6.8) untuk modul e-learning SCORM, dan `react-player` untuk pemutaran video.
- **Pengecekan Kepatuhan Lingkungan:** Node v14 direkomendasikan untuk pengembangan lokal, dengan instalasi dependensi menggunakan `yarn install --ignore-engines`.

### Integrasi API & Client Axios
- **HTTP Client:** Dikonfigurasi dalam `src/services/axios/index.js` dengan baseURL diarahkan ke `${process.env.REACT_APP_BASE_SERVICE_URL}/rest/admin`.
- **Custom Wrapper API:** Menggunakan fungsi `API` dari wrapper custom untuk melakukan request dengan struktur:
  ```javascript
  const res = await API('course.getCourse', { params })
  ```
  Fungsi ini membaca dot-notation string (seperti `course.getCourse`) yang dicocokkan dengan entri konfigurasi metode dan url di dalam `src/services/axios/endpoints.js`.
- **Dynamic Path Parameters (urlBuilder):** Mendukung penggantian parameter dinamis dalam path URL (contoh: `/secured/.../:id` atau `/secured/.../:templateId`) dengan mendefinisikan objek `query` dalam parameter panggilan `API` (contoh: `API('course.deleteCourse', { query: { id } })`).
- **Otentikasi & Interseptor:**
  - Request Interceptor menyisipkan `idToken` dari local storage ke dalam header `Authorization` untuk setiap request.
  - Response Interceptor menangani error status `401` atau `403` dengan memicu *auto-refresh token* menggunakan `/open/auth/refreshtoken`. Jika token gagal diperbarui, local storage akan dibersihkan, dan sistem mengalihkan pengguna ke halaman logout (`/auth/logout`).

---

## Modul Fungsional & Alur Kerja (SOP)

### 1. Otentikasi & Manajemen Sesi (Authentication & Session)
Modul untuk masuk ke dalam CMS, keluar, pemulihan kata sandi, serta konfigurasi akses role pengguna.
- **Path/Route:**
  - `/auth/login` (Halaman Masuk)
  - `/auth/logout` (Halaman Keluar/Pengalihan)
  - `/auth/forgot-password` (Halaman Lupa Sandi)
  - `/auth/register` (Registrasi Pengguna Baru)
  - `/auth/lockscreen` (Halaman Kunci Layar)
- **Tujuan:** Mengamankan akses platform CMS dan melakukan validasi otentikasi admin.
- **SOP Login:**
  1. Admin mengakses halaman `/auth/login`.
  2. Memasukkan Email dan Kata Sandi.
  3. Sistem memicu API `auth.login`. Jika sukses, data token (`idToken`, `accessToken`, `refreshToken`) serta informasi user disimpan di lokal storage.
  4. Pengguna diarahkan ke halaman `/dashboard`.

---

### 2. Manajemen Klien & Perusahaan Klien (Client Company Management)
Modul untuk mengelola data perusahaan eksternal yang menggunakan layanan LearningHub beserta pengelolaan user administratornya.
- **Path/Route:**
  - `/client-company` (Daftar Perusahaan Klien)
  - `/client-company/add` (Tambah Klien Baru)
  - `/client-company/:id/edit` (Ubah Data Klien)
  - `/client-company/:id/manage-admin-client/:companyName` (Kelola User Admin Klien)
  - `/client-company/:id/manage-journey-matrix/:companyName` (Hubungkan Matriks Pembelajaran)
- **Tujuan:** Mendaftarkan entitas perusahaan pihak ketiga dan menentukan siapa administrator utama yang berhak mengelola konten atas nama perusahaan tersebut.
- **SOP Pendaftaran Klien:**
  1. Masuk ke halaman **Client Company** (`/client-company`).
  2. Klik tombol **Add New Client Company**.
  3. Masukkan informasi nama perusahaan, kontak, serta logo perusahaan klien.
  4. Klik **Save**. Setelah tersimpan, gunakan opsi **Manage Admin Client** untuk menunjuk satu atau beberapa user karyawan sebagai Administrator Perusahaan tersebut.
  5. Konfigurasikan matriks perjalanan pembelajaran (Journey Matrix) khusus untuk klien ini melalui **Manage Journey Matrix**.

---

### 3. Manajemen Proyek, Batch & E-Certificate (Project, Batch & E-Certificate Management)
Modul inti untuk mengatur pelaksanaan kegiatan pembelajaran (learning event/project) yang dibagi dalam beberapa kelompok angkatan (batch), serta konfigurasi e-sertifikat untuk kelulusan peserta.
- **Path/Route:**
  - **Client Project:** `/client-project`, `/client-project/:id`, `/client-project/:id/project/create`, `/client-project/:id/project/:projectId/edit`, `/client-project/:id/project/:projectId/batch`, `/client-project/:id/project/:projectId/batch/:batchId`
  - **Internal/Manage Project:** `/manage-project`, `/manage-project/:id/project/create`, `/manage-project/:id/project/:projectId/edit`, `/manage-project/:id/project/:projectId/batch`, `/manage-project/:id/project/:projectId/batch/:batchId`
  - **Sub-Modul Batch & E-Certificate:**
    - `.../batch/:batchId/setup-feedback/:type` (Pengaturan Kuesioner Evaluasi)
    - `.../batch/:batchId/setup-certificate` (Pengaturan Aktivasi E-Sertifikat)
- **Tujuan:** Membuat kerangka kerja pelaksanaan pelatihan, mengelompokkan partisipan ke dalam batch, serta menentukan opsi sertifikat kelulusan per batch.
- **Tipe Proyek & E-Certificate:**
  - **Proyek Tipe Learning Hub (Default):** Peserta mengikuti program belajar terstruktur (course/phase). Kelulusan dan penerbitan sertifikat diproses secara individual berdasarkan penyelesaian aktivitas di platform.
  - **Proyek Tipe Non-Learning Hub (Batch Non-LH):** Proyek eksternal di mana peserta tidak menggunakan modul belajar online LearningHub. Platform ini digunakan semata-mata untuk mengimpor daftar peserta dan memproses pembuatan sertifikat secara kolektif (bulk).
- **Konfigurasi E-Certificate:**
  Pada halaman `/setup-certificate`, administrator dapat mengatur:
  - **Show Certificate (Tampilkan Sertifikat):** Menentukan apakah e-sertifikat diaktifkan untuk batch tersebut (`Yes` (1) / `No` (0)).
  - **Show Company Logo (Tampilkan Logo Perusahaan Klien):** Opsi lanjutan jika sertifikat diaktifkan untuk menyertakan logo perusahaan klien pada desain sertifikat (`Yes` (1) / `No` (0)).
- **SOP Pengelolaan Proyek & Batch:**
  1. Akses menu **Manage Project** (atau **Client Project** jika untuk perusahaan eksternal tertentu).
  2. Buat proyek baru dengan memasukkan nama, rentang tanggal pelaksanaan, dan perusahaan klien penanggung jawab.
  3. Masuk ke detail proyek tersebut dan klik **Create Batch** untuk menambahkan angkatan/gelombang pelatihan.
  4. Pada setiap batch, klik opsi aksi **Setup Certificate** (ikon sertifikat) untuk diarahkan ke halaman `/setup-certificate`.
  5. Atur pilihan **Show Certificate** dan **Show Company Logo** sesuai kebutuhan kelulusan batch, lalu klik **Save** untuk memperbarui konfigurasi sertifikat.

---

### 4. Manajemen Partisipan & Grup (Participant & Group Management)
Modul untuk mengelola data peserta di setiap batch pembelajaran, pengelompokan peserta untuk diskusi/proyek kelompok, serta pengunduhan dokumen kelulusan peserta (e-sertifikat).
- **Path/Route:**
  - `.../batch/:batchId/participant/create` (Daftar Peserta Manual)
  - `.../batch/:batchId/participant/:participantId` (Detail Profil Peserta)
  - `.../batch/:batchId/participant/:participantId/edit` (Ubah Data Peserta)
  - `.../batch/:batchId/group/create` (Buat Kelompok Baru)
  - `.../batch/:batchId/group/:batchForumGroupId/edit` (Edit Data Kelompok)
- **Tujuan:** Memetakan peserta yang berhak mengikuti program pembelajaran, membagi mereka ke dalam kelompok interaksi yang lebih terarah, serta menyalurkan e-sertifikat yang telah dikonfigurasi.
- **SOP Pendaftaran & Kelola Peserta:**
  1. Pada halaman detail **Batch**, buka tab **Participant List**.
  2. Klik **Add Participant** untuk memasukkan data peserta baru secara manual, atau gunakan import file jika tersedia.
  3. Untuk membagi peserta ke kelompok belajar, masuk ke tab **Group List**, buat kelompok baru (misal: Kelompok A), dan centang nama-nama peserta yang akan dimasukkan ke dalam kelompok tersebut.
- **SOP Pengunduhan E-Sertifikat Peserta (Proyek Learning Hub):**
  Jika tipe proyek adalah Learning Hub dan konfigurasi sertifikat pada batch tersebut aktif (`Show Certificate: Yes`), maka:
  - **Unduh Per Peserta:** Di dalam tabel list peserta pada halaman detail batch, administrator dapat mengeklik tombol **Download Certificate** di kolom *Action* paling kanan untuk mengunduh e-sertifikat peserta bersangkutan secara individu dalam bentuk file PDF.
  - **Unduh Massal (Download All):** Di halaman detail batch (bagian atas tabel peserta), administrator dapat mengeklik tombol **Download All Certificate** untuk mengunduh seluruh berkas e-sertifikat peserta yang ada di dalam batch tersebut secara bersamaan.
- **SOP Unggah & Unduh E-Sertifikat Massal (Proyek Non-Learning Hub / Batch Non-LH):**
  Jika tipe proyek adalah **"Non Learning Hub"**, manajemen peserta dan sertifikat menggunakan alur berikut:
  1. **Unduh Template Non-LH:** Unduh file spreadsheet template (`template_upload_participant_non_lhub.xlsx`) dengan mengklik tombol unduh template yang memicu API `downloadTemplateParticipantNonLhub`.
  2. **Unggah Daftar Peserta:** Isi data peserta luar lalu unggah file melalui tombol **+ Upload Participant** (pantau prosesnya pada menu **Upload List**).
  3. **Pengecekan Status Generate:** Platform memuat daftar peserta menggunakan API `getParticipantNonLH` (`/secured/manage-client-project/batch-non-lh/get-all-participants`) dan membaca status boolean `isAllCertGenerated` dari server. Status ini menandakan apakah seluruh e-sertifikat peserta batch non-LH tersebut sudah selesai digenerate secara lengkap oleh sistem backend.
  4. **Download All Certificate (ZIP):** Setelah status `isAllCertGenerated` bernilai `true`, tombol **All Certificate** akan aktif. Administrator dapat mengkliknya untuk memicu API `downloadCertificateNonLH` (`/secured/manage-client-project/batch-non-lh/certificates/download`) yang akan mengunduh seluruh e-sertifikat peserta yang digenerate dalam satu file ZIP (`certificates_${batchId}.zip`).

---

### 5. Perpustakaan Kursus & Konten (Course & Material Library)
Modul penyimpanan global untuk membuat materi pembelajaran dasar (artikel, video, tautan luar, aktivitas interaktif H5P/SCORM) serta merangkumnya menjadi modul Kursus (Course).
- **Path/Route:**
  - **Course:** `/course`, `/course/add`, `/course/:courseId/edit`, `/course/:courseId` (Detail)
  - **Video:** `/video`, `/video/add`, `/video/:videoId/edit`
  - **Article:** `/article`, `/article/create`, `/article/:articleId/edit`
  - **Weblink:** `/weblink`, `/weblink/add`, `/weblink/:weblinkId/edit`
  - **Activity Library:** `/activity/activity-library/add`, `/activity/activity-library/:activityId/edit`
- **Tujuan:** Menyediakan materi ajar terstandarisasi yang dapat dipakai berulang-ulang di berbagai modul program pembelajaran.
- **SOP Pengisian Konten:**
  1. Unggah materi dasar terlebih dahulu melalui menu masing-masing (misal: buat artikel di **Article** dengan editor tulisan CKEditor, atau upload video mp4 ke dalam pustaka **Video**).
  2. Buka menu **Course Library** dan buat Kursus baru.
  3. Tambahkan materi-materi dasar yang sudah dibuat tadi ke dalam susunan kurikulum Kursus tersebut sebagai aktivitas belajar.
  4. Simpan kursus agar dapat dimasukkan ke dalam peta jalan belajar (Journey).

---

### 6. Manajemen Perjalanan Belajar & Matriks (Journey, Matrix & Phase)
Modul untuk menyusun alur belajar berurutan (Journey) berdasarkan tahapan waktu (Phase) dan mendistribusikannya ke entitas klien/batch.
- **Path/Route:**
  - **Journey:** `/journey`, `/journey/create`, `/journey/:journeyId/edit`, `/journey/:journeyId` (Detail)
  - **Journey Matrix:** `/journey-matrix`, `/journey-matrix/add`, `/journey-matrix/edit`
  - **Phase:** `/phase`, `/phase/create`, `/phase/:phaseId/edit`
- **Tujuan:** Mendesain kurikulum komprehensif berurutan yang menggabungkan banyak kursus dan aktivitas di bawah timeline yang terstruktur.
- **SOP Penyusunan Kurikulum:**
  1. Buat beberapa tahapan pembelajaran melalui menu **Phase** (misalnya: *Fase 1: Orientasi*, *Fase 2: Pembelajaran Utama*, *Fase 3: Ujian Evaluasi*).
  2. Buka menu **Journey** dan buat program perjalanan baru.
  3. Masukkan fase-fase tersebut ke dalam Journey, dan tautkan Kursus (Course) dari pustaka ke dalam masing-masing Fase yang sesuai.
  4. Gunakan **Journey Matrix** untuk memetakan program Journey ini agar aktif dan dapat diakses oleh perusahaan klien atau batch tertentu.

---

### 7. Asesmen Mandiri & Evaluasi (Quiz, Assignment, Survey)
Modul pembuatan lembar ujian pilihan ganda (Quiz), tugas esai/unggah berkas mandiri (Assignment), dan survei kepuasan pelanggan (Survey).
- **Path/Route:**
  - **Quiz:** `/quiz`, `/quiz/template/add`, `/quiz/template/:templateId/edit`, `/quiz/question/add`
  - **Assignment:** `/assignment`, `/assignment/question-template/add`, `/assignment/question-template/:assigmentTemplateId/edit`
  - **Survey:** `/survey`, `/survey/question-template/add`, `/survey/scale-template/create`, `/survey/survey-scale/create`
- **Tujuan:** Melakukan penilaian terhadap tingkat pemahaman materi oleh peserta (kuis dan tugas) serta mengumpulkan data evaluasi program pembelajaran (survei).
- **SOP Pembuatan Asesmen:**
  1. Buat template kuesioner/soal di menu masing-masing (misal: **Quiz Template**).
  2. Tambahkan daftar pertanyaan atau butir soal kuis (multi-choice beserta kunci jawaban).
  3. Untuk survei, tentukan skala penilaian Likert terlebih dahulu di menu **Scale Template** sebelum menyusun kuesioner pertanyaan.
  4. Tautkan template Quiz, Assignment, atau Survey tersebut sebagai salah satu aktivitas di dalam Kursus atau Fase Journey.

---

### 8. Penjadwalan & Instruktur (Coaching & Schedule)
Modul untuk mengelola data instruktur (Coach) dan merencanakan jadwal sesi konsultasi tatap muka online/offline dengan peserta.
- **Path/Route:**
  - **Coach:** `/coach`, `/coach/create`, `/coach/:id/update`, `/coach/:id/schedule` (Atur Jadwal Kerja Coach)
  - **Schedule Template:** `/schedule-template`, `/schedule-template/add`, `/schedule-template/:id/edit`
  - **Schedule Pattern:** `/schedule-pattern/:id` (Pola Jadwal Berulang)
- **Tujuan:** Memudahkan alokasi waktu pelatih, pendaftaran sesi bimbingan oleh peserta, dan standarisasi slot penjadwalan.
- **SOP Pengelolaan Jadwal Coach:**
  1. Daftarkan profil pelatih baru di menu **Coach**.
  2. Masuk ke halaman detail coach dan pilih menu **Schedule** untuk mengaktifkan slot waktu kosong pelatih tersebut.
  3. Anda dapat menggunakan **Schedule Template** & **Schedule Pattern** untuk membuat pola jadwal rutin otomatis (misal: setiap hari Senin jam 09.00 - 12.00) tanpa perlu menginput tanggal satu per satu.

---

### 9. Forum Diskusi & Moderasi (Forum & Discussion)
Modul interaksi sosial untuk melihat dan memoderasi pertukaran pesan antar peserta di dalam platform.
- **Path/Route:**
  - `/forum` (Katalog Forum)
  - `/discussion` (Melihat Semua Diskusi)
  - `/discussion/:isGroup/:id/comment` (Halaman Komentar Diskusi)
- **Tujuan:** Memberikan wadah tanya jawab interaktif dan memantau konten komentar peserta.
- **SOP Moderasi Forum:**
  1. Admin membuka menu **Forum**.
  2. Masuk ke topik diskusi atau kelompok diskusi tertentu.
  3. Tinjau komentar yang diposting oleh para peserta. Admin dapat menghapus komentar yang tidak pantas atau memberikan tanggapan resmi.

---

### 10. Pelaporan & Analitik (Reporting & Analytics)
Modul pengumpulan dan ekspor data seluruh perkembangan belajar, nilai kuis, berkas penugasan, serta tingkat kepuasan peserta.
- **Path/Route:**
  - `/journey-progress-report` (Laporan Progres Perjalanan Belajar)
  - `/summary-quiz-report` (Rangkuman Nilai Kuis Peserta)
  - `/feedback-report` (Laporan Hasil Survei Umpan Balik)
  - `/summary-participant-status-report` (Laporan Status Kelulusan)
  - `/completion-report/project` (Progres di tingkat Proyek)
  - `/completion-report/journey` (Progres di tingkat Journey)
  - `/download-answer-assignment` (Unduh Berkas Jawaban Tugas Mandiri)
- **Tujuan:** Menyediakan data analitis yang terperinci bagi tim manajemen dan perusahaan klien untuk menilai efektivitas pelatihan.
- **SOP Penarikan Laporan:**
  1. Akses salah satu menu laporan, misalnya **Journey Progress Report**.
  2. Pilih filter proyek, nama perusahaan klien, nama batch, atau nama perjalanan belajar.
  3. Sistem memuat pratinjau tabel pencapaian peserta.
  4. Klik tombol **Export to Excel** atau **Download Report** untuk mengunduh file laporan fisik.

---

### 11. Pengaturan Sistem & Kepatuhan Legal (Admin settings)
Modul pengelolaan data dasar sistem, RBAC (Role-Based Access Control), template surat menyurat, dan kepatuhan hukum platform.
- **Path/Route:**
  - `/manage-employee` (Staf Internal/Daftar Karyawan)
  - `/manage-company` (Manajemen Profil Korporasi/Mitra)
  - `/manage-menu` (Pengaturan Sidebar Navigasi Dinamis)
  - `/manage-role` & `/user-role` (Konfigurasi RBAC & Menu Hak Akses)
  - `/frequently-asked-questions` (Kelola Daftar FAQ Peserta)
  - `/terms-condition` (Kelola Dokumen Syarat & Ketentuan)
  - `/privacy-policy` (Kelola Dokumen Kebijakan Privasi)
  - `/nda-template` (Kelola Dokumen NDA)
  - `/notification-template` & `/email-template` (Pengaturan Template Notifikasi/Surel)
  - `/maintenance-schedule` (Jadwal Pemeliharaan Aplikasi)
  - `/configuration` (Pengaturan Global & Parameter Sistem)
- **Tujuan:** Menjaga kepatuhan legal sistem, mengatur hak akses operasional CMS, serta melakukan pemeliharaan rutin.
- **SOP Pengolahan Data Legal:**
  1. Pilih modul legal yang ingin diperbarui (misal: **NDA Template**).
  2. Edit konten dokumen hukum di editor CKEditor yang disediakan.
  3. Simpan perubahan. Dokumen NDA baru akan langsung disajikan sebagai syarat persetujuan wajib yang muncul di layar peserta saat masuk ke platform pembelajaran.
- **SOP Konfigurasi Dynamic Menu Sidebar:**
  1. Akses menu **Manage Menu**.
  2. Admin dapat menambahkan entitas menu baru, mengatur nama menu multi-bahasa, ikon, alamat route URL tujuan, serta memilih role pengguna mana saja yang berhak melihat menu tersebut pada sidebar.
  3. Simpan untuk memperbarui struktur sidebar secara langsung.

---

> [!TIP]
> **Pola Operasi Tabel Standard (CRUD Pattern):**
> Hampir seluruh tabel data di dalam CMS ini didesain menggunakan pola Ant Design Table yang seragam:
> - **Pencarian & Filter:** Terletak di bagian atas tabel menggunakan debounce waktu tunda input teks sebesar 500ms (`lodash.debounce`) agar menghemat beban query server.
> - **Penambahan Data Baru:** Tombol biru dengan tulisan `Add New...` atau ikon tambah (`PlusOutlined`) selalu diletakkan di sudut kanan atas halaman di samping judul modul.
> - **Aksi Baris Tabel:** Tombol edit, pratinjau detail, duplikasi data (duplicate), dan hapus (delete/deactivate) disediakan secara konsisten di kolom aksi tabel sebelah kanan dengan popup konfirmasi hapus demi menghindari kesalahan klik.
