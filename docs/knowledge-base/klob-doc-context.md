---
product_id: klob
product_name: Klob.id
status: active
---

# Klob.id (Klob Frontend) - Feature Context & Guide Document

Dokumen ini berisi rangkuman seluruh fitur yang ada di dalam platform pencarian kerja dan pemetaan potensi diri **Klob.id** beserta panduan fungsional dan teknis alur kerjanya. Dokumen ini dirancang sebagai *context document* untuk membantu agent AI memahami kapabilitas, struktur navigasi, routing, serta modul-modul fungsional yang ada pada aplikasi pencari kerja (jobseeker) Klob.id.

---

## Teknologi Utama & Arsitektur
- **Core Library:** React.js (v16.14.0) dengan React Router Dom (v5) untuk routing halaman.
- **State Management:** Custom State Store (`CombinedContext`) menggabungkan Context Provider (seperti `UsersAuth`, `LoginProvider`, `NotifProvider`, `HelpMessageProvider`, dll) untuk mengelola data global tanpa dependensi Redux eksternal yang besar.
- **Styling:** Menggunakan kombinasi SCSS (`sass/index.scss`) dan `styled-components` untuk kustomisasi UI yang dinamis.
- **Integrasi Cloud & Pihak Ketiga:** AWS Amplify untuk integrasi cloud, Midtrans sebagai payment gateway pembayaran paket/voucher, Google Analytics 4 (GA4), dan Google Tag Manager (GTM).

---

## 1. Otentikasi & Verifikasi (Authentication & Verification)
Modul untuk mengelola proses pendaftaran, login, integrasi single sign-on (SSO), serta verifikasi identitas pengguna.
- **Path/Route:** 
  - `/login` (Halaman Masuk)
  - `/daftar` (Halaman Registrasi)
  - `/forgotpassword` (Halaman Lupa Kata Sandi)
  - `/verification` (Verifikasi Email Akun Baru)
  - `/emailverification` (Verifikasi Email Tambahan/Perubahan)
  - `/sso` (Single Sign-On SSO)
  - `/invitationlink/:id` (Halaman link undangan registrasi/event)
- **Tujuan:** Menjamin akses akun yang aman dan integrasi otentikasi eksternal (LinkedIn / Google).
- **SOP Pendaftaran & Login:**
  1. Pengguna mengakses halaman `/daftar` untuk mendaftarkan akun baru atau masuk ke `/login`.
  2. Pengguna dapat memilih login menggunakan email/password tradisional, LinkedIn PopUp, atau Google Login.
  3. Setelah melakukan pendaftaran, pengguna akan diarahkan ke halaman `/verification` untuk memasukkan kode verifikasi yang dikirimkan ke email mereka sebelum dapat mengakses aplikasi penuh.

---

## 2. Rangkuman Aktivitas Pengguna (Kloboard Dashboard)
Modul dashboard utama setelah pengguna berhasil masuk (logged-in).
- **Path/Route:** `/home/kloboard` (atau `/home`)
- **Tujuan:** Memberikan gambaran ringkas (overview) tentang profil karier pengguna, status lamaran, dan rekomendasi aktivitas terdekat.
- **Struktur Tampilan (Widgets):**
  - **Progress bar kelengkapan profil:** Memunculkan popup `PopupProfileCompleteness` jika ada data wajib profil yang masih kosong.
  - **Info Count:** Menampilkan metrik kuantitas aktivitas (jumlah lamaran terkirim, lowongan yang disimpan, dll).
  - **Career Area Section:** Rekomendasi bidang karier yang cocok untuk pengguna.
  - **Klob Meter Section:** Status dan hasil singkat dari alat tes psikometri yang sudah diikuti.
  - **Kaleidosklob Section:** Rangkuman kalender event terdekat.
  - **Klob & Co Section:** Rekomendasi lowongan pekerjaan yang cocok (*klob*) dengan profil pengguna.
  - **Ensiklobedia Section:** Artikel-artikel edukasi karier pilihan.

---

## 3. Klob Meter (Alat Tes Psikometri & Karier)
Modul asesmen mandiri untuk mengidentifikasi minat, nilai kerja, gaya interaksi, dan potensi kepribadian karier pengguna.
- **Path/Route:** `/home/klob-meter`
- **Tujuan:** Mengukur potensi diri pengguna dan mencocokkannya dengan kriteria lowongan pekerjaan di database perusahaan.
- **Jenis Alat Tes & SOP Pengerjaan:**
  - **Minat Kerja (MK):** `/home/klob-meter/test/mk` (Melihat ketertarikan jenis pekerjaan).
  - **Nilai Kerja (NK):** `/home/klob-meter/test/nk` (Mengukur nilai-nilai utama yang dicari dalam bekerja).
  - **Kepribadian Kerja (KK):** `/home/klob-meter/test/kk` (Mengetahui kepribadian profesional pengguna).
  - **Gaya Interaksi (GI):** `/home/klob-meter/test/gi` (Menilai cara berkomunikasi dan berkolaborasi).
  - **Kompas Karier (Agregator Tes):** Seri tes khusus yang terdiri dari:
    - *Keingintahuan* (`/home/klob-meter/test/cur`)
    - *Pemaknaan Kerja* (`/home/klob-meter/test/mm`)
    - *Kegigihan* (`/home/klob-meter/test/gr`)
    - *Kerendahan Hati* (`/home/klob-meter/test/hum`)
    - *Pola Pikir* (`/home/klob-meter/test/min`)
    - *Kreativitas* (`/home/klob-meter/test/cre`)
    - *Tujuan Hidup* (`/home/klob-meter/test/pil`)
  - **Akhlak Test:** `/home/klob-meter/test/akhlak` (Untuk persiapan pemetaan nilai-nilai BUMN).
- **SOP Pengerjaan Tes:**
  1. Pengguna membuka menu **Klob Meter** dan memilih salah satu alat tes (misalnya Gaya Interaksi).
  2. Pengguna membaca petunjuk pengerjaan di halaman landing tes, lalu menekan tombol mulai.
  3. Pengguna menjawab rangkaian pertanyaan/kuesioner sesuai instruksi sebelum batas waktu berakhir.
  4. Setelah selesai, sistem akan mengarahkan pengguna ke halaman hasil (misal: `/home/klob-meter/test/gi/result`) untuk melihat analisis grafis kepribadian atau minat mereka.

---

## 4. Klob & Co (Portal Lowongan Kerja & Direktori Perusahaan)
Modul pencarian lowongan pekerjaan, penelusuran profil perusahaan, dan pencocokan (*compatibility matching*).
- **Path/Route:**
  - `/home/klob-and-co/position` (Cari Lowongan Kerja)
  - `/home/klob-and-co/corporate` (Cari Perusahaan)
  - `/job/:corporateName/:corporateId/:positionName/:jobvacancyId` (Detail Lowongan Kerja)
  - `/company/:corporateName/:corporateId` (Detail Profil Perusahaan)
  - `/validasi-lamaran-pekerjaan/:corporateName/:corporateId/:jobName/:jobId` (Validasi Kelengkapan Profil Sebelum Melamar)
- **Tujuan:** Menghubungkan pencari kerja dengan lowongan yang paling sesuai berdasarkan skor kecocokan profil Klob Meter.
- **SOP Melamar Pekerjaan:**
  1. Pengguna mencari pekerjaan di tab **Cari Lowongan** (menggunakan filter keyword, lokasi, status, tipe industri).
  2. Pada daftar lowongan, pengguna akan melihat persentase kecocokan (*match score*) dengan profil dirinya.
  3. Pengguna mengklik lowongan untuk membuka halaman detail. Di sana terdapat deskripsi pekerjaan, kriteria, dan tombol "Lamar Pekerjaan".
  4. Saat tombol diklik, sistem akan mengarahkan pengguna ke halaman `/validasi-lamaran-pekerjaan/...` untuk memverifikasi dokumen administrasi wajib (seperti KTP, NPWP, CV, dan dokumen pendukung lainnya).
  5. Setelah semua prasyarat terpenuhi, pengguna mengonfirmasi pengiriman lamaran.

---

## 5. Profil Pengguna & Kelengkapan CV (Career Profile Revamp)
Modul resume digital interaktif milik pengguna yang memuat riwayat pendidikan, profesional, dan administrasi.
- **Path/Route:** `/profile/:id` (dengan `/profile` redirects otomatis ke ID pengguna yang sedang login)
- **Tujuan:** Membangun resume digital lengkap yang akan dikirimkan ke perusahaan perekrut saat melamar pekerjaan.
- **Bagian-Bagian Profil:**
  - **Header & Ringkasan Diri:** Foto profil, banner, nama lengkap, kontak dasar, dan rangkasan diri singkat.
  - **Biodata Lengkap:** Data diri dasar, alamat, kewarganegaraan.
  - **Pengalaman Kerja:** Riwayat pekerjaan terdahulu, magang, status pekerjaan.
  - **Riwayat Pendidikan:** Riwayat sekolah, universitas, jurusan, IPK/GPA.
  - **Technical Skills:** Daftar keahlian teknis dan tingkat penguasaan bahasa.
  - **Sertifikasi & Penghargaan:** Kursus, lisensi profesional, serta sertifikat prestasi.
  - **Portofolio & Proyek:** Upload berkas file portofolio hasil karya dan detail projek.
  - **Organisasi & Referensi:** Riwayat berorganisasi serta kontak referensi profesional.
  - **Emergency Contact & Nuclear Family:** Informasi keluarga inti dan kontak darurat.
  - **Dokumen Administratif:** Unggahan dokumen resmi seperti KTP, NPWP, Ijazah, dan CV fisik (PDF).
  - **Progress Section:** Widget persentase yang menunjukkan tingkat kelengkapan profil pengguna menuju 100%.

---

## 6. Pembuat CV & Cetak CV (CV Builder)
Modul untuk menyusun CV fisik berbasis data profil digital yang sudah diisi pengguna.
- **Path/Route:**
  - `/resume/builder` (Halaman CV Builder)
  - `/cv-select-template` (Halaman Pemilihan Template CV)
  - `/cv-preview` (Pratinjau CV Sebelum Diunduh)
- **Tujuan:** Menghasilkan dokumen CV profesional siap cetak/unduh dalam format PDF.
- **SOP Membuat CV:**
  1. Pengguna masuk ke menu **CV Builder** dan memilih `/cv-select-template`.
  2. Memilih template desain yang diinginkan (misal: *Professional*, *Reguler*, *Simple*, *Experienced*, *Freshgrad*, *Freelance*, atau *Tech*).
  3. Menentukan bahasa output dokumen (Inggris atau Indonesia).
  4. Masuk ke halaman pratinjau `/cv-preview` untuk memverifikasi layout visual hasil ekspor PDF.
  5. Pengguna dapat mengunduh dokumen secara gratis (untuk template dasar) atau melakukan pembayaran/memasukkan kode voucher untuk mengunduh template premium.

---

## 7. Kalender Kegiatan Karier (Kaleidosklob)
- **Path/Route:** `/home/kaleidosklob`
- **Tujuan:** Menyajikan kalender kegiatan pengembangan diri seperti webinar, pelatihan, info beasiswa, magang, dan virtual job fair.
- **SOP Mengikuti Kegiatan:**
  1. Pengguna membuka halaman kalender Kaleidosklob.
  2. Memilih kategori acara atau tanggal tertentu pada kalender.
  3. Mengklik event detail untuk melihat penyelenggara, jadwal, link pendaftaran, atau langsung mendaftarkan diri dan menambahkan jadwal tersebut ke kalender eksternal (Google/Outlook Calendar).

---

## 8. Ensiklobedia (Media Belajar & Artikel)
- **Path/Route:** 
  - `/home/ensiklobedia` (Katalog Artikel)
  - `/detail-ensiklobedia/:goalID` (Halaman Baca Artikel/Materi)
- **Tujuan:** Menyediakan materi pembelajaran karir yang dikurasi dari content partner Klob.
- **SOP Pembelajaran:**
  1. Pengguna menjelajahi direktori materi pembelajaran berdasarkan topik (pengembangan diri, tips interview, kepemimpinan).
  2. Pengguna mengklik materi pilihan dan membaca atau menonton konten video yang terintegrasi di dalam halaman detail.

---

## 9. KlobFair (Virtual Job Fair & Event Kemitraan)
Halaman promosi khusus berskala besar yang dikustomisasi untuk acara bursa kerja virtual dari mitra korporat atau universitas.
- **Path/Route:** `/:subdomain` (secara dinamis memetakan domain klobfair mitra, contoh: `/chevron`, `/sdp-bsi`, `/rekrutmen-bankjatim`, `/rekrutmen-ptba`, dll)
- **Tujuan:** Menjadi gerbang pendaftaran event job fair interaktif (termasuk visualisasi 3D job fair jika diaktifkan).
- **Alur Kerja SOP:**
  1. Pengguna mengunjungi subdomain bursa kerja mitra (misal: `klob.id/sdp-bsi`).
  2. Pengguna melihat daftar lowongan khusus yang dibuka hanya untuk event bursa kerja tersebut.
  3. Pengguna mendaftarkan diri secara khusus pada event bursa kerja tersebut dan langsung melamar pekerjaan di sana dengan profil Klob.id mereka yang telah terintegrasi.

---

## 10. Keranjang Belanja & Pembayaran (Payment Gateway)
Modul transaksi keuangan untuk pembelian asesmen premium, template resume berbayar, atau paket sertifikasi.
- **Path/Route:** `/home/payment`
- **Tujuan:** Memproses pembayaran transaksi digital secara real-time via integrasi Midtrans.
- **SOP Pembelian:**
  1. Pengguna memilih template CV premium atau paket asesmen berbayar, lalu menekan tombol "Tambah ke Keranjang" atau "Beli Sekarang".
  2. Pengguna diarahkan ke halaman pembayaran `/home/payment` untuk meninjau invoice belanja dan memasukkan kode voucher jika ada.
  3. Pengguna melakukan checkout, memicu pemuatan Midtrans Script, dan memilih metode pembayaran (E-wallet, Virtual Account, Credit Card).
  4. Setelah pembayaran diverifikasi sukses oleh sistem, status pembelian aktif dan fitur premium dapat digunakan.

---
> [!TIP]
> **Skor Kompatibilitas Profil (RAG/Matching System):**
> Klob.id memiliki fitur unggulan pencocokan kecocokan profile. Ketika pengguna melamar pekerjaan di Klob & Co, sistem secara otomatis melakukan perhitungan persentase kecocokan (*match score*) antara data profil pengguna (dari hasil tes Klob Meter seperti Minat Kerja, Nilai Kerja, Kepribadian Kerja) dengan kriteria spesifikasi pekerjaan yang dimasukkan oleh recruiter di sisi employer (klob-corporate). Skor inilah yang membantu recruiter menyaring kandidat terbaik dengan lebih efisien.
