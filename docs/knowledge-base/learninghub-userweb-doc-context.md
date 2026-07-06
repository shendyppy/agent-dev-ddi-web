---
product_id: learninghub-userweb
product_name: LearningHub Participant (Userweb)
status: active
default_url: https://learninghub.odyssey.co.id
---

# LearningHub Participant (Userweb) - Feature Context & Guide Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam sistem **LearningHub Participant (Userweb)** beserta panduan fungsional dan teknis alur kerjanya. Dokumen ini dirancang sebagai *context document* untuk membantu agent AI memahami kapabilitas, struktur navigasi, routing, serta modul-modul fungsional yang ada pada portal pembelajaran sisi peserta (Userweb) LearningHub.

---

## Teknologi Utama & Arsitektur

- **Core Library:** React.js (v17.0.1) dengan React Router Dom (v5) untuk routing halaman.
- **Visual Builder Integration:** Menggunakan kerangka kerja `@vb` (Visual Builder React) untuk tata letak UI, otentikasi, dynamic menu, dan visualisasi widget.
- **State Management:** Menggunakan Redux dengan Redux Saga (`src/redux/sagas.js` & `src/redux/reducers.js`) untuk menyimpan status sesi user dan data aplikasi.
- **UI Library:** Ant Design (antd v4) dikombinasikan dengan Bootstrap (v4.5.3) untuk layouting grid yang responsif, serta SCSS untuk styling kustom.
- **Interactive Players & Media:**
  - `h5p-standalone` (v3.6.0) untuk rendering modul materi interaktif H5P.
  - `scorm-again` (v2.6.8) untuk memproses modul e-learning berstandar SCORM.
  - `react-player` untuk rendering pemutaran video secara streaming.
  - `react-slick` dan `slick-carousel` untuk visualisasi slider/carousel pada daftar program pembelajaran.
  - `@react-pdf-viewer/core` & `react-pdf` untuk memvisualisasikan dokumen PDF/Article langsung dalam web.
  - `react-html5-camera-photo` untuk menangkap foto peserta secara langsung saat melakukan absensi kehadiran.

### Integrasi API & Client Axios
- **HTTP Client:** Dikonfigurasi dalam `src/services/axios/index.js` dengan baseURL diarahkan ke `${process.env.REACT_APP_BASE_SERVICE_URL}/rest/web`.
- **Custom Wrapper API:** Menggunakan fungsi `API` dari wrapper custom untuk melakukan request dengan struktur:
  ```javascript
  const res = await API('dashboard.home', { params })
  ```
  Fungsi ini membaca dot-notation string (seperti `dashboard.home`) yang dicocokkan dengan entri konfigurasi metode dan url di dalam `src/services/axios/endpoints.js`.
- **Interseptor Keamanan:**
  - Request Interceptor menyisipkan `idToken` atau `authorized` dari local storage ke dalam header `Authorization` untuk setiap request.
  - Response Interceptor menangani error status `401` atau `403` dengan memicu *auto-refresh token* menggunakan `/open/auth/refreshtoken`. Jika token gagal diperbarui, local storage akan dibersihkan, dan sistem mengalihkan peserta ke halaman logout (`/auth/logout`).

---

## Modul Fungsional & Alur Kerja (SOP)

### 1. Otentikasi & Penerimaan NDA (Authentication & NDA Compliance)
Modul untuk masuk ke dalam portal peserta, menyetujui kebijakan kepatuhan (NDA), serta pemulihan akun.
- **Path/Route:**
  - `/auth/login` (Halaman Masuk Peserta)
  - `/auth/logout` (Halaman Keluar)
  - `/auth/sso-error-login` (Halaman Galat SSO)
  - `/auth/blockscreen` (Halaman Kunci Layar Kepatuhan)
- **Tujuan:** Menjamin keabsahan akses peserta ke materi pelatihan serta pencatatan kepatuhan NDA.
- **SOP Login & Persetujuan NDA:**
  1. Peserta mengakses `/auth/login` dan memasukkan kredensial (Email/Password) atau masuk melalui Single Sign-On (SSO).
  2. Saat login pertama kali, sistem memicu API `setting.getNDAContent`. Jika peserta belum menyetujui dokumen NDA, layar akan diblokir oleh halaman persetujuan.
  3. Peserta membaca klausul NDA, mencentang persetujuan, lalu mengeklik tombol setuju yang memicu API `setting.agreeNDA` (`/secured/users/nda/accept`).
  4. Setelah sukses, token disimpan di local storage dan peserta diarahkan ke `/dashboard`.

---

### 2. Beranda & Daftar Program (Dashboard & Journey Overview)
Modul utama yang menyajikan rangkuman perkembangan belajar peserta serta katalog program pelatihan yang sedang diikuti.
- **Path/Route:**
  - `/dashboard` (Halaman Dashboard Utama)
  - `/journey-all` (Daftar Seluruh Program)
  - `/current-activity` (Aktivitas Belajar Berjalan)
- **Tujuan:** Memberikan gambaran umum mengenai progres program belajar berjalan (dashboard widgets) serta akses cepat ke aktivitas terdekat.
- **SOP Menjelajahi Program:**
  1. Setelah masuk, peserta disajikan halaman `/dashboard` yang menampilkan widget statistik (progres perjalanan belajar, poin, peringkat, serta aktivitas yang harus segera dikerjakan).
  2. Peserta dapat melihat daftar lengkap program pelatihan melalui `/journey-all` (memanggil API `dashboard.journey`).
  3. Klik salah satu kartu program belajar untuk masuk ke halaman detail kurikulum.

---

### 3. Detail Perjalanan Belajar (Journey Detail & Phase)
Modul kurikulum terstruktur yang menjabarkan fase-fase belajar (Phase) serta urutan aktivitas pembelajaran di dalamnya.
- **Path/Route:**
  - `/journey-detail/:participantId` (Detail Kurikulum Peserta)
- **Tujuan:** Menyajikan jalur belajar berurutan (peta jalan belajar) yang wajib diselesaikan oleh peserta.
- **SOP Mengikuti Jalur Belajar:**
  1. Peserta membuka halaman detail perjalanan belajar untuk id partisipan tertentu `/journey-detail/:participantId`.
  2. Halaman ini memuat data kurikulum dari API `journeyDetail.journey` dan `journeyDetail.getCourseActivity`.
  3. Peserta melihat daftar fase belajar (misal: *Fase 1*, *Fase 2*). Di dalam fase tersebut terdapat berbagai aktivitas seperti Kuis, Video, Artikel, Tugas, atau Weblink.
  4. Aktivitas terkunci (tidak bisa diklik) jika ada prasyarat aktivitas sebelumnya yang belum diselesaikan oleh peserta (berdasarkan urutan kurikulum).

---

### 4. Pengerjaan Kuis Interaktif (Quiz Activity)
Modul asesmen pilihan ganda untuk mengukur pemahaman peserta terhadap kursus yang diikuti.
- **Path/Route:**
  - `/activities/quiz/:activityId/:participantActivityId`
- **Tujuan:** Melakukan uji pemahaman kognitif dengan batasan pengerjaan dan penilaian otomatis.
- **SOP Pengerjaan Kuis:**
  1. Peserta mengklik aktivitas kuis pada halaman Journey Detail.
  2. Sistem memicu API `activities.startQuiz` (`/secured/quiz/start-quiz-activity`) untuk memulai sesi kuis dan mencatat waktu mulai (timer berjalan).
  3. Peserta menjawab pertanyaan pilihan ganda satu per satu. Setiap jawaban dikirim secara real-time ke server menggunakan `activities.submitAnswerSelection` atau `activities.changeAnswerSelection` untuk menghemat data.
  4. Setelah semua dijawab atau waktu habis, peserta mengeklik **Finish Quiz** yang memicu API `activities.finishQuiz` dan memanggil `activities.calculateQuiz` untuk kalkulasi nilai.
  5. Hasil nilai akhir dan status kelulusan langsung ditampilkan. Jika diperbolehkan oleh admin, peserta dapat mengklik **Retake Quiz** (API `activities.retakeQuiz`) untuk mencoba kembali.

---

### 5. Media & Konten Pembelajaran (Video, Article & Weblink)
Modul untuk membaca artikel, menonton video tutorial, atau membuka tautan eksternal yang dipersyaratkan dalam materi belajar.
- **Path/Route:**
  - `/activities/video/:activityId/:participantActivityId` (Nonton Video)
  - `/activities/article/:activityId/:participantActivityId` (Baca Artikel)
  - `/activities/weblink/:activityId/:participantActivityId` (Buka Tautan Luar)
- **Tujuan:** Menyajikan konten edukasi kaya format langsung di dalam platform.
- **SOP Membaca/Menonton Materi:**
  1. Peserta membuka aktivitas (misal: Video). Sistem memicu `startActivity.startVideo` untuk mencatat waktu mulai belajar.
  2. Untuk video, peserta memutar video menggunakan pemutar media terintegrasi.
  3. Setelah selesai menonton hingga durasi yang ditentukan atau selesai membaca seluruh artikel PDF, sistem memicu API `activities.finishVideo` atau `activities.finishArticle` untuk mengubah status aktivitas menjadi **Selesai (Completed)**.
  4. Untuk Weblink, peserta mengeklik tombol **Open Link** (memicu `activities.startWeblink` dan `activities.finishWeblink`) untuk membuka halaman eksternal di tab baru sambil menandai aktivitas tersebut selesai secara otomatis.

---

### 6. Pengumpulan Tugas & Proyek Mandiri (Assignment Mission)
Modul untuk mengunduh instruksi tugas esai/proyek mandiri dan mengunggah dokumen jawaban peserta.
- **Path/Route:**
  - `/activities/assignment-mission/:activityId/:participantActivityId`
- **Tujuan:** Memberikan ruang bagi peserta untuk mengumpulkan tugas fisik/digital untuk dinilai secara manual oleh Fasilitator/Coach.
- **SOP Pengumpulan Tugas:**
  1. Peserta membuka menu tugas dan membaca instruksi pengerjaan (diambil melalui API `assignment.getAssignment` atau `assignment.getAssignmentNonHl`).
  2. Peserta mengunduh lembar soal atau panduan tugas jika ada.
  3. Setelah tugas dikerjakan, peserta mengunggah file dokumen jawaban menggunakan API `assignment.uploadAssignment` (`/secured/assignment/upload`).
  4. Peserta mengisi deskripsi tambahan pada form, kemudian menekan tombol **Submit Response** (API `assignment.submitAssignment`).
  5. Aktivitas ditandai selesai setelah peserta mengonfirmasi pengiriman lewat API `assignment.finishAssignment`.

---

### 7. Pengisian Umpan Balik (Feedback & Peer-Feedback)
Modul bagi peserta untuk memberikan penilaian terhadap program pelatihan (evaluasi) atau memberikan penilaian umpan balik kepada rekan kerja satu batch (peer feedback).
- **Path/Route:**
  - `/assignment-feedback/give-feedback/activity-type/:activityId/:participantActivityId/:projectType/:batchActivityTimelineId` (Isi Feedback Aktivitas)
  - `/assignment-feedback/give-feedback/question-type/:activityId/:participantActivityId/:projectType/:batchActivityTimelineId` (Isi Kuesioner Pertanyaan)
  - `/assignment-feedback/view-feedback/activity-type/:activityId/:participantActivityId/:projectType` (Lihat Rangkuman Feedback)
- **Tujuan:** Mengumpulkan data evaluasi pelatihan dan penilaian kolaboratif antar peserta (360-degree/peer review).
- **SOP Memberikan Peer Feedback:**
  1. Peserta membuka menu feedback berjalan dan melihat daftar rekan peserta yang harus dinilai (diambil dari API `feedback.participantPeerFeedback`).
  2. Peserta memilih salah satu nama rekan, lalu mengisi formulir penilaian evaluasi.
  3. Jawaban disimpan ke server dengan memicu API `feedback.submitFeedback`.

---

### 8. Kehadiran Sesi & Kelas (Attendance Check)
Modul untuk melakukan absensi kehadiran peserta pada sesi kelas tatap muka atau webinar secara real-time.
- **Path/Route:**
  - `/activities/attendance-check/:activityId/:participantActivityId`
- **Tujuan:** Melakukan validasi kehadiran peserta menggunakan foto selfie kamera langsung (selfie verification).
- **SOP Melakukan Absensi Kehadiran:**
  1. Saat jadwal kelas dimulai, peserta membuka menu **Attendance Check**.
  2. Sistem meminta izin akses kamera browser (menggunakan `react-html5-camera-photo`).
  3. Peserta mengambil foto selfie wajahnya secara langsung.
  4. Foto diunggah menggunakan API `activities.uploadFotoAttendance` (`/secured/journey/class/upload`).
  5. Peserta menekan tombol konfirmasi kehadiran yang memicu API `activities.submitFotoAttendance` dan menandai kehadiran telah terverifikasi.

---

### 9. Kompetisi & Poin (Leaderboard & Points)
Modul gamifikasi yang menampilkan daftar peringkat poin peserta dalam program pelatihan.
- **Path/Route:**
  - `/leader-board` (Halaman Papan Peringkat)
- **Tujuan:** Meningkatkan antusiasme dan keterlibatan peserta melalui kompetisi skor belajar.
- **SOP Melihat Peringkat:**
  1. Peserta membuka menu **Leaderboard** (`/leader-board`).
  2. Peserta dapat melihat daftar peringkat peserta lain berdasarkan perolehan poin kumulatif (API `leaderboard.getLeaderboard`).
  3. Gunakan filter perjalanan belajar (`getJourneyLov`) atau batch (`getBatchLov`) untuk melihat leaderboard kelompok tertentu.
  4. Klik **Detail My Point** (`getDetailMyPoint`) untuk melihat riwayat aktivitas apa saja yang memberikan poin kepada dirinya beserta informasi aturan poin (`getRulebook`).

---

### 10. Pengunduhan E-Sertifikat Publik (Public E-Certificate)
Halaman sertifikat digital peserta yang bersifat publik dan dapat diunduh atau dibagikan ke media sosial (LinkedIn/Twitter).
- **Path/Route:**
  - `/eCertificate/:programName/:participantId`
- **Tujuan:** Menyediakan bukti fisik kelulusan peserta yang terverifikasi dan dapat diakses secara publik tanpa perlu login.
- **SOP Mengakses Sertifikat:**
  1. Setelah peserta menyelesaikan program dan dinyatakan lulus, tautan sertifikat publik akan terbuat (contoh: `/eCertificate/Program-A/12345`).
  2. Peserta atau pihak luar mengakses URL tersebut secara langsung (publik).
  3. Halaman mengambil data sertifikat dari API `activities.getEcertificate` (`/open/e-certificate/:participantId`) tanpa proteksi token login.
  4. Halaman menampilkan visual sertifikat digital peserta beserta nama, program, tanggal kelulusan, dan tombol **Download PDF** untuk diunduh.

---

> [!TIP]
> **Pola Navigasi Kunci (State On-Activities):**
> Saat peserta masuk ke halaman pengerjaan materi/aktivitas belajar (seperti mengerjakan Kuis, menonton Video, atau absensi), sistem secara otomatis mengeset state `onActivities: true` di local storage. State ini berfungsi untuk mengunci navigasi sidebar agar peserta tidak sengaja keluar atau menutup halaman pengerjaan materi tanpa menyimpannya terlebih dahulu (mencegah hilangnya progres pengerjaan kuis/tugas di tengah jalan).
